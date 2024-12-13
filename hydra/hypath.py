import shutil
import copy
from enum import Enum
import math
import json

from . import hynote
from . import hyrecord
from . import hymisc

# Boiled-down structure that divides a song into scored regions.
# Contains branches based on pathing decisions (i.e. skip vs. activate).
# Creating a ScoreGraph factors out the note-by-note scoring simulation
# so that when it's time for optimization, we're working with pre-scored chunks.
class ScoreGraph:
    

    
    def __init__(self, song):
        
        self.debug_run_backends = True
        
        self.base_track_head = ScoreGraphNode(hymisc.Timecode(song.tick_resolution, song.measure_map, song.tempo_map, 0), False)
        self.sp_track_head = ScoreGraphNode(hymisc.Timecode(song.tick_resolution, song.measure_map, song.tempo_map, 0), True)
        
        self.start = self.base_track_head
        pending_deacts = set([])
        
        self.acc_notecount = 0
        self.acc_basescore = 0
        self.acc_comboscore = 0
        self.acc_spscore = 0
        self.acc_soloscore = 0
        self.acc_accentscore = 0
        self.acc_ghostscore = 0
        self.combo = 0
        
        self.acc_sp_phrases = [] # timecodes, each gives 1 sp
        
        self.debug_total_basescore = 0
        
        self.acc_multsqueezes = []
        
        self.acc_latest_sp_time = None
        
        self.recent_deacts = []
        
        backend_history = [] # Timestamps back to -140ms
        self.live_backend_edges = [] # deactivation edges that are accepting scored timestamps up to +140ms
        for ts_i, timestamp in enumerate(song.sequence):
            
            self.recent_deacts = [tc for tc in self.recent_deacts if tc.offset_ms(timestamp.timecode) < 140]
            
            self.debug_total_basescore += timestamp.chord.debug_basescore()
            
            # handle any deacts that occur between timestamps
            gap_deacts = sorted([tc for tc in pending_deacts if tc < timestamp.timecode])

            for pending_deact in gap_deacts:
                # Update backend history (but there aren't any new ones)
                if self.debug_run_backends:
                    backend_history = [be for be in backend_history if be[0].timecode.offset_ms(timestamp.timecode) < 140]
                self.advance_tracks(pending_deact, None)
                self.add_deact_edge(backend_history)
                    
            # remove the deacts we just handled
            pending_deacts = set([tc for tc in pending_deacts if tc not in gap_deacts])
            
            self.acc_notecount += timestamp.chord.count()
            self.acc_soloscore += 100 * timestamp.chord.count() if timestamp.flag_solo else 0
            
            points_by_source = sourcescores(timestamp.chord, self.combo, True)
            worse_points = sourcescores(timestamp.chord, self.combo, True, reverse=True)
            
            comboscore = points_by_source['combo_note'] + points_by_source['combo_cymbal'] + points_by_source['combodynamic_note'] + points_by_source['combodynamic_cymbal']
            worse_comboscore = worse_points['combo_note'] + worse_points['combo_cymbal'] + worse_points['combodynamic_note'] + worse_points['combodynamic_cymbal']
            
            if comboscore != worse_comboscore:
                msq = hyrecord.HydraRecordMultSqueeze()
                msq.multiplier = to_multiplier(self.combo) + 1
                msq.chord = hyrecord.HydraRecordChord.from_chord(timestamp.chord)
                msq.points = comboscore - worse_comboscore
                self.acc_multsqueezes.append(msq)
            
            
            self.acc_basescore += points_by_source['base_note'] + points_by_source['base_cymbal'] + points_by_source['dynamic_cymbal']
            self.acc_comboscore += comboscore
            timestamp_spscore = points_by_source['sp_note'] + points_by_source['sp_cymbal'] + points_by_source['combosp_note'] + points_by_source['combosp_cymbal'] + points_by_source['spdynamic_note'] + points_by_source['spdynamic_cymbal'] + points_by_source['combospdynamic_note'] + points_by_source['combospdynamic_cymbal']
            self.acc_spscore += timestamp_spscore
            self.acc_accentscore += points_by_source['dynamic_note_accent']
            self.acc_ghostscore += points_by_source['dynamic_note_ghost']
            
            self.combo += timestamp.chord.count()
            
            sqout_scoring = sourcescores(timestamp.chord, self.combo, True, sqout=True)
            sqout_sp_points = sqout_scoring['sp_note'] + sqout_scoring['sp_cymbal'] + sqout_scoring['combosp_note'] + sqout_scoring['combosp_cymbal'] + sqout_scoring['spdynamic_note'] + sqout_scoring['spdynamic_cymbal'] + sqout_scoring['combospdynamic_note'] + sqout_scoring['combospdynamic_cymbal']
            
            _backend = (hyrecord.HydraRecordBackendSqueeze(timestamp.timecode, timestamp.chord, timestamp_spscore, sqout_sp_points), timestamp.flag_sp)
            
            # Add this chord's sp points to backends that will be fed to any deactivation that happens soon
            if self.debug_run_backends:
                backend_history = [be for be in backend_history if be[0].timecode.offset_ms(timestamp.timecode) < 140]
                backend_history.append(_backend)
            
            # Add this chord's sp points to any deactivation that happened recently
                
            #self.live_backend_edges = [e for e in self.live_backend_edges if e.dest.timecode.offset_ms(timestamp.timecode) < 140]
            if self.debug_run_backends:
                valid_backend_edges = []
                for e in self.live_backend_edges:
                    e_offset = e.dest.timecode.offset_ms(timestamp.timecode)
                    if e_offset < 140:
                        valid_backend_edges.append(e)
                        edge_backend = copy.copy(_backend)
                        edge_backend[0].offset_ms = e_offset
                        e.backends.append(edge_backend)
                        
                        if edge_backend[1]: # backend is also sp
                            offset = e.dest.timecode.offset_ms(edge_backend[0].timecode)
                            e.sqinout_time = min(e.sqinout_time, edge_backend[0].timecode)  if e.sqinout_time else edge_backend[0].timecode
                            e.sqinout_timing = min(e.sqinout_timing, offset) if e.sqinout_timing != None else offset
                            e.sqinout_amount += 1
                self.live_backend_edges = valid_backend_edges
                    
            if timestamp.flag_sp:
                # If any deacts are only the squeeze window away (140ms), keep them (SqOut)
                sqout_deacts = set([tc for tc in pending_deacts if timestamp.timecode.offset_ms(tc) < 140])
                
                # Extend pending deacts by 2 measures - but not past now + 8 (full sp meter)
                pending_deacts = set([min(tc.plusmeasure(2), timestamp.timecode.plusmeasure(8)) for tc in pending_deacts]).union(sqout_deacts)
                self.acc_sp_phrases.append(timestamp.timecode)
                self.acc_latest_sp_time = timestamp.timecode
                
                # Revive any recent deacts (SqIn)
                for tc in self.recent_deacts:
                    pending_deacts.add(tc.plusmeasure(2))
                
            # handle acts            
            if timestamp.flag_activation:
                self.advance_tracks(timestamp.timecode, timestamp.chord)
                self.add_act_edge(timestamp.chord, timestamp_spscore, timestamp.activation_fill_length_ticks)
                
                pending_deacts.add(timestamp.timecode.plusmeasure(4))
                pending_deacts.add(timestamp.timecode.plusmeasure(6))
                pending_deacts.add(timestamp.timecode.plusmeasure(8))
                
            # handle deacts
            if timestamp.timecode in pending_deacts:
                self.advance_tracks(timestamp.timecode, timestamp.chord)
                self.add_deact_edge(backend_history)
                pending_deacts.remove(timestamp.timecode)
                
                self.recent_deacts.append(timestamp.timecode)
                
            # Graph builder:
            #   sp phrases and their timecodes are acc'd and placed on advancement edges
            #   also, any sp times within 140ms of the edge's destination get put on that node as backend sp.
            # When a path tries to branch for deactivation, if there any saved sp times and the sp end time is 2 measures * the number of saved sp times,
            #   then the path is allowed to branch even though
            #   sp was refreshed. Instead, the deactivated path will start with sp equal to the saved sp times, and the latest activation
            #   will be marked as a SqOut using the earliest saved sp time. Also, the sq-out notes will have their sp scoring removed.
            #   The complementary path, which continued in sp, also gets marked SqIn for its latest activation.
            # When a path typically branches for deactivation, the continue-sp path is typically flagged for removal.
            #   However, if we look ahead 140 ms and find sp, the path gets to stay and it's marked SqIn.
            #   The complementary path, which deactivated, is marked SqOut.
            # Any time a path is marked SqIn or SqOut, it's also marked with the ms threshold that separates In from Out. (Usually 0ms)
            # To do: just flag a path for removal instead of testing SP conditions, since SqIn will have unusual SP conditions.
            
            # New plan: The graph builder will do the harder work of recognizing SqIn/SqOut.
            # Paths will just be able to read off of nodes whether that node has SqIn/SqOut information.
            
        self.advance_tracks(song.sequence[-1].timecode, song.sequence[-1].chord)
        

        
    def advance_tracks(self, timecode, chord):
        if self.base_track_head.timecode >= timecode: 
            return
            
        base_edge = ScoreGraphEdge()
        sp_edge = ScoreGraphEdge()
        
        base_edge.dest = ScoreGraphNode(timecode, False)
        sp_edge.dest = ScoreGraphNode(timecode, True)
            
        base_edge.dest.chord = chord
        sp_edge.dest.chord = chord
            
        base_edge.notecount = self.acc_notecount
        sp_edge.notecount = self.acc_notecount
        
        base_edge.basescore = self.acc_basescore
        base_edge.comboscore = self.acc_comboscore
        base_edge.spscore = 0
        base_edge.soloscore = self.acc_soloscore
        base_edge.accentscore = self.acc_accentscore
        base_edge.ghostscore = self.acc_ghostscore
        
        base_edge.sp_times = self.acc_sp_phrases
        
        sp_edge.basescore = self.acc_basescore
        sp_edge.comboscore = self.acc_comboscore
        sp_edge.spscore = self.acc_spscore
        sp_edge.soloscore = self.acc_soloscore
        sp_edge.accentscore = self.acc_accentscore
        sp_edge.ghostscore = self.acc_ghostscore
        
        base_edge.multsqueezes = copy.copy(self.acc_multsqueezes)
        sp_edge.multsqueezes = copy.copy(self.acc_multsqueezes)
        
        base_edge.latest_sp_time = self.acc_latest_sp_time
        sp_edge.latest_sp_time = self.acc_latest_sp_time
        
        self.acc_latest_sp_time = None
        
        self.acc_multsqueezes = []
        
        sp_edge.sp_times = self.acc_sp_phrases
        
        self.acc_notecount = 0
        self.acc_basescore = 0
        self.acc_comboscore = 0
        self.acc_spscore = 0
        self.acc_soloscore = 0
        self.acc_accentscore = 0
        self.acc_ghostscore = 0
        
        self.acc_sp_phrases = []
            
        self.base_track_head.adv_edge = base_edge
        self.sp_track_head.adv_edge = sp_edge
        
        self.base_track_head = base_edge.dest
        self.sp_track_head = sp_edge.dest
        
            
    def add_act_edge(self, frontend_chord, frontend_points, fill_length_ticks):

        
        act_edge = ScoreGraphEdge()
        act_edge.dest = self.sp_track_head
        
        act_edge.notecount = 0
        act_edge.basescore = 0
        act_edge.comboscore = 0
        act_edge.spscore = 0
        act_edge.soloscore = 0
        act_edge.accentscore = 0
        act_edge.ghostscore = 0
        
        act_edge.frontend = hyrecord.HydraRecordFrontendSqueeze(frontend_chord, frontend_points)
        
        act_edge.activation_fill_length_ticks = fill_length_ticks
        
        self.base_track_head.branch_edge = act_edge
        

        
    def add_deact_edge(self, prior_backends):
        deact_edge = ScoreGraphEdge()
        deact_edge.dest = self.base_track_head
        
        deact_edge.notecount = 0
        deact_edge.basescore = 0
        deact_edge.comboscore = 0
        deact_edge.spscore = 0
        deact_edge.soloscore = 0
        deact_edge.accentscore = 0
        deact_edge.ghostscore = 0
        
        
        
        # notes just prior to this deactivation, which are normally in sp but could be squeezed out
        for be in prior_backends:
            deact_edge.backends.append(copy.copy(be))
            deact_edge.backends[-1][0].offset_ms = deact_edge.dest.timecode.offset_ms(be[0].timecode)
            
            # Some checks that can be done here instead of every path doing it
            if be[1]: # backend is also sp
                offset = deact_edge.dest.timecode.offset_ms(be[0].timecode)
                deact_edge.sqinout_time = be[0].timecode
                deact_edge.sqinout_timing = min(deact_edge.sqinout_timing, offset) if deact_edge.sqinout_timing != None else offset
                deact_edge.sqinout_amount += 1
        
        #deact_edge.backends = prior_backends
        
        self.live_backend_edges.append(deact_edge)
        
        self.sp_track_head.branch_edge = deact_edge
        
    def traverse_print(self):
        unexplored = [self.start]
        visited = []
        
        while len(unexplored) > 0:
            node = unexplored.pop()
            visited.append(node)
            print(node)
            
            for edge in [node.adv_edge, node.branch_edge]:
                if edge != None and edge.dest not in visited and edge.dest not in unexplored:
                    unexplored.append(edge.dest)
        
# A graph node representing a point in the song and whether SP is active or not.
# The only possible edges are 1 prog edge leading farther into the song,
# or 1 branch node toggling SP.
class ScoreGraphNode:
    
    def __init__(self, timecode, is_sp):
        self.timecode = timecode

        self.adv_edge = None
        self.branch_edge = None
        self.is_sp = is_sp
        self.chord = None
        
    def __repr__(self):
        lines = [self.name()]
        if self.adv_edge:
            lines.append(self.adv_edge.__repr__())
        if self.branch_edge:
            lines.append(self.branch_edge.__repr__())
                    
        return '\n'.join(lines)
        
    def name(self):
        return f"{self.timecode.measurestr()}{' SP' if self.is_sp else ''}"
        
class ScoreGraphEdge:
        
    def __init__(self):
        # CH-style score breakdown
        self.basescore = None
        self.comboscore = None
        self.spscore = None
        self.soloscore = None
        self.accentscore = None
        self.ghostscore = None
        
        self.notecount = None
        self.sp_times = []
        
        self.dest = None
        
        self.frontend = None
        self.backends = []
        
        self.multsqueezes = []
        
        self.latest_sp_time = None
        self.activation_fill_length_ticks = None
        
        self.sqinout_time = None
        self.sqinout_timing = None
        self.sqinout_amount = 0

        
    def __repr__(self):
        return f" --> {self.dest.name()}, frontend = {self.frontend}"
    
    


class GraphPather:
    
    def __init__(self):
        self.paths = []
        
    def run(self, graph):
         
        self.paths = [GraphPath()]
        self.paths[0].currentnode = graph.start
        
        while any([not p.is_complete() for p in self.paths]):
            
            
            #print("=========\nNew round of updates.\n============")
            # Remove SP paths that ran out (they've spawned a deactivation path already)
            oldlen = len(self.paths)
            
            #for p in self.paths:
            #    print(f"\tPath removal test: p.currentnode.is_sp = {p.currentnode.is_sp}, p.currentnode.timecode = {p.currentnode.timecode}, p.sp_end_time = {p.sp_end_time}")
            
            self.paths = [p for p in self.paths if not (p.currentnode.is_sp and p.currentnode.timecode == p.sp_end_time)]
            #print(f"Removed {oldlen - len(self.paths)} paths.")
            
            # Advance paths
            for p in self.paths:
                p.advance()
                    
            # Proliferate paths (activate or deactivate)
            new_paths = []
            for p in self.paths:
                branch = p.branch()
                if branch != None:
                    new_paths.append(branch)
                    
            self.paths += new_paths
            
            # Cull paths (any that are strictly worse)
            
            
            self.prevpaths = self.paths
            self.paths = [p for p in self.paths if not any([p.strictly_worse(other) for other in self.paths])]
            
            # for removedpath in [p for p in self.prevpaths if p not in self.paths]:
                # if len(removedpath.record.activations) >= 3 and removedpath.record.activations[0].timecode.measures()[0] == 27 and removedpath.record.activations[1].timecode.measures()[0] == 47 and removedpath.record.activations[2].timecode.measures()[0] == 79:
                    # print("Target path removed:")
                    # for act in removedpath.record.activations:
                        # print(act)
                        # print(f"\tBackends:")
                        # if len(act.backends) == 0:
                            # print("\t\tNone")
                        # for be in act.backends:
                            # print(f'\t\t({be.timecode.measurestr()}, {be.chord}, {be.offset_ms}ms)')
                            
                        
            
        self.paths.sort(key=lambda p: p.record.optimal(), reverse=True)
        
        print(f"\nFound {len(self.paths)} paths.\n")
        for act in self.paths[0].record.activations:
            print(act)
            print(f"\tBackends:")
            if len(act.backends) == 0:
                print("\t\tNone")
            for be in act.backends:
                print(f'\t\t({be.timecode.measurestr()}, {be.chord}, {be.offset_ms}ms)')
        
            
class GraphPath:
    
    def __init__(self):
        self.record = hyrecord.HydraRecordPath()
        
        self.currentnode = None
        
        self.sp = 0
        self.currentskips = 0
        
        self.buffered_sqin_sp = 0 # sp that was applied to facilitate a sq-in, and needs to not be double counted
        
        self.sp_end_time = None
    
        self.latest_sp_time = None
        
    # Returns True if other has a conclusively better score, which requires both paths to be at the same timecode and same sp track.
    def strictly_worse(self, other):
        # Same time requirement
        self_time = self.currentnode.timecode if self.currentnode else None
        other_time = other.currentnode.timecode if other.currentnode else None
        
        
        if self_time != other_time:
            return False
        
        # Same sp requirement
        self_sp_active = self.currentnode.is_sp if self.currentnode else None
        other_sp_active = other.currentnode.is_sp if other.currentnode else None
        
        if self_sp_active != other_sp_active:
            return False 

        # Same sp value requirement
        self_sp_value = (self.sp_end_time if self_sp_active else self.sp) if self.currentnode else 0
        other_sp_value = (other.sp_end_time if other_sp_active else other.sp) if other.currentnode else 0
        
        # if self.record.optimal() < other.record.optimal() and self.sp <= other.sp:
            # print(f"{self.currentnode.timecode.measurestr()}: About to remove path:")
            # for a in self.record.activations:
                # print(f"\t{a.skips}\t{a.timecode.measurestr()}")
            # print(f"\t{self.record.optimal()}/{other.record.optimal()}, {self.sp}/{other.sp} ({self.record.optimal() < other.record.optimal() and self.sp <= other.sp})")
        
        return self.record.optimal() < other.record.optimal() and self_sp_value <= other_sp_value
        
    # Develop along the edge that leads farther into the song.
    # Always moves a path closer to being complete, unless it's already complete.
    def advance(self):
        #print("Path advancing:")
        
        if self.is_complete():
            #print("\tOops, I was already done.")
            return
        
        #print(f"\tI'm at {self.currentnode.timecode.measurestr()} and SP is {'' if self.currentnode.is_sp else 'in'}active...")
        
        if len(self.record.activations) >= 3 and self.record.activations[0].timecode.measures()[0] == 27 and self.record.activations[1].timecode.measures()[0] == 47 and self.record.activations[2].timecode.measures()[0] == 79:
            print("Target path advancing.")
        
        adv_edge = self.currentnode.adv_edge
        if adv_edge:
            self.record.score_base += adv_edge.basescore
            self.record.score_combo += adv_edge.comboscore
            self.record.score_sp += adv_edge.spscore
            self.record.score_solo += adv_edge.soloscore
            self.record.score_accents += adv_edge.accentscore
            self.record.score_ghosts += adv_edge.ghostscore
            #print(f"\tGoing to {adv_edge.dest.timecode.measurestr()}.")
            if self.currentnode.is_sp:
                # Path is in SP: Immediately "spend" SP bars and adjust the sp end time
                #print(f"\tSP: {self.sp} + {len(adv_edge.sp_times)} = {min(max(0, self.sp + len(adv_edge.sp_times)), 4)}.")
                
                for sptc in adv_edge.sp_times:
                    if self.buffered_sqin_sp > 0:
                        self.buffered_sqin_sp -= 1
                    else:
                        self.sp_end_time = min(self.sp_end_time.plusmeasure(2), sptc.plusmeasure(8))
                
            else:
                # Path isn't in SP: Add SP bars
               # print(f"\tSP: {self.sp} + {len(adv_edge.sp_times)} = {min(max(0, self.sp + len(adv_edge.sp_times)), 4)}.")
                self.sp = min(self.sp + len(adv_edge.sp_times), 4)
 
            self.record.multsqueezes += adv_edge.multsqueezes
            
            if adv_edge.latest_sp_time:
                self.latest_sp_time = adv_edge.latest_sp_time
            
            self.currentnode = adv_edge.dest
                    
            
        else:
            #print("\tReached the end actually, achieving enlightenment.")
            self.currentnode = None
   
    # Use the edge that changes SP state (an activation or deactivation).
    # Returns a new path copy where the branch was taken.
    def branch(self):        
        #print("Path branching:")
        if self.is_complete():
            #print("\tOops, I was already done.")
            return
        if len(self.record.activations) >= 3 and self.record.activations[0].timecode.measures()[0] == 27 and self.record.activations[1].timecode.measures()[0] == 47 and self.record.activations[2].timecode.measures()[0] == 79:
            print("Target path branching.")
        #print(f"\tI'm at {self.currentnode.timecode.measurestr()} and SP is {'' if self.currentnode.is_sp else 'in'}active...")
        
        br_edge = self.currentnode.branch_edge
        if not br_edge:
            #print("\tOops, branch edge not found.")
            return
            
        # Check conditions for activation
        if br_edge.dest.is_sp and (self.sp < 2 or self.sp == 2 and self.latest_sp_time.ticks + 2*br_edge.activation_fill_length_ticks > self.currentnode.timecode.ticks):
            #print(f"\tActivation conditions not met: sp = {self.sp}")
            return
        
        # Check conditions for deactivation
        sq_out = False
        if not br_edge.dest.is_sp and br_edge.dest.timecode != self.sp_end_time:
            # Normal conditions for deactivation not met, but maybe a SqOut is possible
            if not br_edge.dest.is_sp and br_edge.dest.timecode.plusmeasure(2 * br_edge.sqinout_amount) == self.sp_end_time:
                sq_out = True
                #print("\tSqOut conditions met")
            else:
                #print(f"\tDeactivation conditions not met: my sp end time is {self.sp_end_time.measurestr()}")
                return
        
        new_path = GraphPath()
        new_path.record = copy.deepcopy(self.record)
        new_path.currentnode = br_edge.dest
        
        # Deactivated paths have 0 sp, and activated paths immediately "spend" the sp and just know what time the sp ends.
        new_path.sp = br_edge.sqinout_amount if sq_out else 0
        
        if br_edge.dest.is_sp:
            # Activation
            #print("\tActivating!")
            new_path.record.activations.append(hyrecord.HydraRecordActivation())
            new_path.record.activations[-1].skips = self.currentskips
            new_path.record.activations[-1].timecode = self.currentnode.timecode
            new_path.record.activations[-1].chord = hyrecord.HydraRecordChord.from_chord(self.currentnode.chord)
            new_path.record.activations[-1].sp_meter = self.sp
            
            new_path.record.activations[-1].frontend = br_edge.frontend
            new_path.record.score_sp += br_edge.frontend.points
            
            
            new_path.sp_end_time = br_edge.dest.timecode.plusmeasure(2 * self.sp)
            
            #print(f"\tNewly-branched path has an sp end time of {new_path.sp_end_time} (its current time is {new_path.currentnode.timecode})")
            
            self.currentskips += 1
        
        else:
            # Deactivation
            #print("\tDeactivating!")
            new_path.sp_end_time = None
            
            new_path.record.activations[-1].backends = [be[0] for be in br_edge.backends]
            
            if sq_out:
                new_path.record.activations[-1].sqinouts.append('-')
                self.record.activations[-1].sqinouts.append('+')
                
                # Adjust sq-out scoring (basically an altered backend calculation)
                # When a backend is after the sq-out chord but before current, it's been already counted, so it needs to be subtracted.
                # When a backend IS the sq-out chord and being subtracted, only subtract the least valuable note.
                for be,be_sp in br_edge.backends:
                    if be.timecode >= br_edge.sqinout_time and be.timecode <= new_path.currentnode.timecode:
                        new_path.record.score_sp -= be.points
                    
                    # And add back in sqout points (lol) if this is the exact sqout chord
                    if be.timecode == br_edge.sqinout_time and be.timecode <= new_path.currentnode.timecode:
                        new_path.record.score_sp += be.sqout_points
            else:
                # Typical deactivation - a SqIn may be possible, which would save self from being removed imminently
                if br_edge.sqinout_amount > 0:
                    print("\tSpecial condition for late SqIn occurred.")
                    new_path.record.activations[-1].sqinouts.append('-')
                    self.record.activations[-1].sqinouts.append('+')
                    # self got here by being at its sp end time, but now it can be extended.
                    self.sp_end_time = self.sp_end_time.plusmeasure(2 * br_edge.sqinout_amount)
                    self.buffered_sqin_sp = br_edge.sqinout_amount
        
        return new_path
            
    def is_complete(self):
        return self.currentnode == None
     
# Arranges a chord's points by every possible combination of score modifiers.
# Looks like a lot but allows for any kind of score breakdown or "order of operations" on the game's score multipliers.
def sourcescores(chord, combo, sp_active, reverse=False, sqout=False):
    
    points_by_source = {
        'base_note': 0,             'base_cymbal': 0,
        'combo_note': 0,            'combo_cymbal': 0,
        'sp_note': 0,               'sp_cymbal': 0,
        'combosp_note': 0,          'combosp_cymbal': 0,
        'dynamic_note_accent': 0,   'dynamic_cymbal': 0,
        'dynamic_note_ghost': 0,
        'combodynamic_note': 0,     'combodynamic_cymbal': 0,
        'spdynamic_note': 0,        'spdynamic_cymbal': 0,
        'combospdynamic_note': 0,   'combospdynamic_cymbal': 0}
    
    # ew, fix asap
    if sqout:
        reverse = True
    
    ordering = sorted(chord.notes(), key=lambda n: n.basescore(), reverse=reverse)
    
    for i,note in enumerate(ordering):
        combo += 1
        combo_multiplier = to_multiplier(combo)
        
        basevalue = 50
        cymbvalue = 15
        
        if sqout and i == len(ordering) - 1:
            sp_active = False

        points_by_source['base_note'] += basevalue
        points_by_source['base_cymbal'] += cymbvalue if note.is_cymbal() else 0
        points_by_source['combo_note'] += basevalue * (combo_multiplier - 1)
        points_by_source['combo_cymbal'] += cymbvalue * (combo_multiplier - 1) if note.is_cymbal() else 0
        points_by_source['sp_note'] += basevalue if sp_active else 0
        points_by_source['sp_cymbal'] += cymbvalue if note.is_cymbal() and sp_active else 0
        points_by_source['combosp_note'] += basevalue * (combo_multiplier - 1) if sp_active else 0
        points_by_source['combosp_cymbal'] += cymbvalue * (combo_multiplier - 1) if note.is_cymbal() and sp_active else 0
        points_by_source['dynamic_note_accent'] += basevalue if note.is_accent() else 0
        points_by_source['dynamic_note_ghost'] += basevalue if note.is_ghost() else 0
        points_by_source['dynamic_cymbal'] += cymbvalue if note.is_cymbal() and note.is_dynamic() else 0
        points_by_source['combodynamic_note'] += basevalue * (combo_multiplier - 1) if note.is_dynamic() else 0
        points_by_source['combodynamic_cymbal'] += cymbvalue * (combo_multiplier - 1) if note.is_cymbal() and note.is_dynamic() else 0
        points_by_source['spdynamic_note'] += basevalue if sp_active and note.is_dynamic() else 0
        points_by_source['spdynamic_cymbal'] += cymbvalue if note.is_cymbal() and sp_active and note.is_dynamic() else 0
        points_by_source['combospdynamic_note'] += basevalue * (combo_multiplier - 1) if sp_active and note.is_dynamic() else 0
        points_by_source['combospdynamic_cymbal'] += cymbvalue * (combo_multiplier - 1) if note.is_cymbal() and sp_active and note.is_dynamic() else 0
    
    return points_by_source
     
# To do: A better name that reflects that *this* is the part that is simulating score gains and SP behavior.
class Path:
    
    uid = 1
    
    def __init__(self):
    
        # Score not including dynamics or star power and missing all point squeezes
        self.basescore = 0
        self.basedynamics = 0
        # Score from the star power multiplier
        self.spscore = 0
        
        self.solobonus = 0
        
        self.debug_id = 0
        
        # Skips/activations update these
        self.current_skips = 0
        self.skipped_quantum_fill = None
        self.activations = []
        
        self.multiplier_squeezes = []
        self.activation_squeezes = []
        self.backend_squeezes = []
        
        # Gameplay variables
        self.sp_meter = 0.0 # 0.0 to 1.0
        self.sp_active = False
        # todo: only use "timestamp" for time or measures. These are more like snapshots
        self.chord_sp_timestamp = False
        self.chord_sp_border_timestamp = False
        self.sp_just_ended = False
        
        
        self.latest_timestamp_time = 0.0
        self.latest_timestamp_measure = 0
        
        self.sp_ready_time = None
        self.sp_ready_measure = None
        self.sp_ready_measure_earlyhit = None
        self.sp_ready_measure_latehit = None
        self.sp_ready_beat = None
        self.sp_ready_beat_earlyhit = None
        self.sp_ready_beat_latehit = None
        
        self.combo = 0

        
    def __str__(self):
        return f"Path {self.debug_id}, {[a.skips for a in self.activations]} + {self.current_skips}, {self.get_best_total_score()}, SP={self.sp_meter}, active SP={self.sp_active}"
        
    # A path is strictly better if it has a better score and equal or more star power while in the same star power state and same timestamp.
    # This function returns True (self is better), False (other is better), or None (inconclusive).
    # When final is True, stored sp has no value
    def strictly_compare(self, other, final=False):        
        if self.sp_active != other.sp_active or self.latest_timestamp_time != other.latest_timestamp_time:
            return None
        return self.get_best_total_score() > other.get_best_total_score() and (final or self.sp_meter >= other.sp_meter)
            
    def quick_match(self, skips):
        return len(skips) == len(self.activations) and all([self.activations[i].skips == skips[i] for i in range(len(skips))])
        

    
    
    
    def get_best_total_score(self):
        return self.basescore + self.solobonus + self.basedynamics + self.spscore + sum([s.extrascore for s in self.multiplier_squeezes]) + sum([s.extrascore for s in self.activation_squeezes]) + sum([s.extrascore for s in self.backend_squeezes]) 
    
    # FCing and hitting the correct path but missing all squeezes and dynamics
    def get_worst_total_score(self):
        return self.basescore + self.solobonus + self.spscore
    
    def push_timestamp(self, timestamp):
        # Timestamp comes both with elapsed time and a chord.
        
        timestamp_is_sp_border = False
        
                
        # spend sp
        if self.sp_active:
            self.sp_meter -= (timestamp.measure - self.latest_timestamp_measure)/8.0
            # to do: it might be possible to make this floating point error less impactful but it requires a refactor on how measures are calculated/expressed
            # resolution of this error window: 1/128th of a measure
            if self.sp_meter <= 0.0009765625:
                self.sp_meter = 0.0
                self.sp_active = False
                timestamp_is_sp_border = True
                
                
        new_paths = []
        

        
        # Multiplier squeeze: In a chord that straddles a multiplier, hit lower-value notes first.
        multiplier_squeeze = MultiplierSqueeze.from_context(timestamp.chord, self.combo, self.sp_active or timestamp_is_sp_border)
        if multiplier_squeeze != None and not timestamp.flag_activation:
            # If a chord is both a multiplier squeeze and an activation squeeze (not likely), just treat it as an activation squeeze
            self.multiplier_squeezes.append(multiplier_squeeze)
        
        # Add score for this timestamp
        chordscore_no_dynamics = comboscore(timestamp.chord, self.combo, reverse=True, no_dynamics=True)
        
        # SP and squeeze calculations will assume dynamics are being hit.
        chordscore = comboscore(timestamp.chord, self.combo, reverse=True)
        
        self.combo += timestamp.chord.count()
        
        self.basescore += chordscore_no_dynamics
        self.basedynamics += chordscore - chordscore_no_dynamics
        
        if timestamp_is_sp_border:
            # Backend squeeze: Ranges from whole chord not in sp (this score has already been applied) to fully in sp.
            backend_squeeze = BackendSqueeze(chordscore)
            self.activations[-1].backend_squeeze = backend_squeeze
            self.backend_squeezes.append(backend_squeeze)
        elif self.sp_active:
            # Regular sp chord
            self.spscore += chordscore
        
        
        
        if timestamp.flag_activation:
            
            # First condition for activations: not already in star power and has enough star power
            if not self.sp_active and self.sp_meter >= 0.5:
            
                # Even if SP is ready to activate, it has to be ready for a certain length of time before fills start to appear.
                # This time (in beats) is measured in realtime, so it's influenced by calibration and player timing.
                
                threshold_difference_beats = timestamp.activation_fill_start_beat - self.sp_ready_beat - 4.0
                
                if threshold_difference_beats >= 0:
                    threshold_offset_ms = threshold_difference_beats / (self.sp_ready_beat_latehit - self.sp_ready_beat) * 70
                else:
                    threshold_offset_ms = threshold_difference_beats / (self.sp_ready_beat - self.sp_ready_beat_earlyhit) * 70
                
                calibration_ms = 0 #-5
                threshold_offset_ms += calibration_ms
                
                offset_limit = 50
                is_timing_sensitive = abs(threshold_offset_ms) < offset_limit
                
                # Forced early fill activation is a bifurcation, unlike regular activations
                
                # to do: rewrite this first case so skipping is the main path and the activation is the new path
                # to do: an "activate" operation on any path
                
                if threshold_offset_ms >= 0:
                    # We're choosing between skipping or activating.
                    # With the way fills are scored, there's no value in forcing this fill to not appear, which is harder.
                    
                    # With normal timing the fill has enough time to appear, which means it's skippable.
                    # When this is true, an activation is also possible (see next block), but not necessarily vice versa.
                    skip_option = copy.deepcopy(self)
                    skip_option.debug_id = Path.uid
                    Path.uid += 1
                    skip_option.current_skips += 1
                    if is_timing_sensitive:
                        # Whenever the next activation is logged, we'll note that the first skip was timing sensitive.
                        skip_option.skipped_quantum_fill = CalibrationFill(0, threshold_offset_ms) # Skipped but may not appear
                    new_paths.append(skip_option)
                
                    #print(f"\tActivating.")
                    # The fill can appear either normally or with early timing, so it's activatable.
                    self.sp_active = True
                    
                    self.activations.append(Activation(timestamp.chord, self.current_skips, self.sp_meter, timestamp.measure))
                    if self.skipped_quantum_fill != None:
                        self.skipped_quantum_fill.skips_with_fill += self.current_skips
                        self.activations[-1].quantum_fill = self.skipped_quantum_fill
                        self.skipped_quantum_fill = None
                    elif is_timing_sensitive:
                        self.activations[-1].quantum_fill = CalibrationFill(0, threshold_offset_ms) # Activated but may not appear
                    self.sp_ready_time = None
                    self.sp_ready_measure = None
                    self.sp_ready_measure_earlyhit = None
                    self.sp_ready_measure_latehit = None
                    self.sp_ready_beat = None
                    self.sp_ready_beat_earlyhit = None
                    self.sp_ready_beat_latehit = None
                    self.current_skips = 0
                    # The activation chord was already scored, but 1 or more notes are actually under the sp that just activated.
                    # Add the bare minimum (the activation note) to non-squeeze scoring.
                    self.spscore += timestamp.chord.get_activation_note_basescore()*to_multiplier(self.combo)
                    
                    activation_squeeze = ActivationSqueeze.from_context(timestamp.chord, self.combo)
                    if activation_squeeze != None:
                        self.activation_squeezes.append(activation_squeeze)
                        self.activations[-1].activation_squeeze = activation_squeeze
                
                
                elif threshold_offset_ms > -offset_limit:
                    # The fill can be forced to appear. We're choosing between doing nothing and forcing it to appear AND activating.
                    # With the way fills are scored, there's no value in forcing this fill to appear, which is harder, just to skip it.
                    # However, that may still happen accidentally.
                    forced_early_option = copy.deepcopy(self)
                    forced_early_option.debug_id = Path.uid
                    Path.uid += 1
                    forced_early_option.sp_active = True
                    forced_early_option.activations.append(Activation(timestamp.chord, forced_early_option.current_skips, forced_early_option.sp_meter, timestamp.measure))
                    forced_early_option.activations[-1].quantum_fill = CalibrationFill(0, threshold_offset_ms) # Activated, forced to appear
                    forced_early_option.sp_ready_time = None
                    forced_early_option.sp_ready_measure = None
                    forced_early_option.sp_ready_measure_earlyhit = None
                    forced_early_option.sp_ready_measure_latehit = None
                    forced_early_option.sp_ready_beat = None
                    forced_early_option.sp_ready_beat_earlyhit = None
                    forced_early_option.sp_ready_beat_latehit = None
                    forced_early_option.current_skips = 0
                    
                    # The activation chord was already scored, but 1 or more notes are actually under the sp that just activated.
                    # Add the bare minimum (the activation note) to non-squeeze scoring.
                    forced_early_option.spscore += timestamp.chord.get_activation_note_basescore()*to_multiplier(forced_early_option.combo)
                    
                    activation_squeeze = ActivationSqueeze.from_context(timestamp.chord, forced_early_option.combo)
                    if activation_squeeze != None:
                        forced_early_option.activation_squeezes.append(activation_squeeze)
                        forced_early_option.activations[-1].activation_squeeze = activation_squeeze
                    
                    forced_early_option.latest_timestamp_time = timestamp.time
                    forced_early_option.latest_timestamp_measure = timestamp.measure
                    new_paths.append(forced_early_option)
                    self.skipped_quantum_fill = CalibrationFill(1, threshold_offset_ms) # Doesn't appear but may appear and be skipped

                    
        if timestamp.flag_sp:
            
            if timestamp_is_sp_border:
                # this path will be an sp extension; spawn a new path where the sp expires.
                sq_out = copy.deepcopy(self)
                sq_out.sp_meter = 0.25
                # there was a brand-new backend squeeze; reduce it by the minimum 1 note that must be left out of sp
                sq_out.backend_squeezes[-1].extrascore -= timestamp.chord.point_spread()[0]*to_multiplier(self.combo)
                sq_out.activations[-1].phrase_squeeze = "Out"
                new_paths.append(sq_out)

                self.activations[-1].phrase_squeeze = "In"
                # reactivate 
                self.sp_active = True
                self.sp_meter = 0.25
            else:
                # add sp
                self.sp_meter = min(self.sp_meter + 0.25, 1.0)
            
                if self.sp_meter == 0.5 and not self.sp_active:
                    # to do: save the whole timestamp as sp_ready_timestamp instead of copying multiple values from it
                    self.sp_ready_time = timestamp.time
                    self.sp_ready_measure = timestamp.measure
                    self.sp_ready_measure_earlyhit = timestamp.measure_earlyhit
                    self.sp_ready_measure_latehit = timestamp.measure_latehit
                    self.sp_ready_beat = timestamp.beat
                    self.sp_ready_beat_earlyhit = timestamp.beat_earlyhit
                    self.sp_ready_beat_latehit = timestamp.beat_latehit
        
        if timestamp.flag_solo:
            self.solobonus += 100 * timestamp.chord.count()
        
        self.latest_timestamp_time = timestamp.time
        self.latest_timestamp_measure = timestamp.measure
        
        return new_paths
    

def comboscore(chord, combo, reverse=False, no_dynamics=False):
    mx_thresholds = [10,20,30]
    multiplier = to_multiplier(combo)
    chord_points = 0
    for note_points in chord.point_spread(reverse, no_dynamics):
        combo += 1
        if combo in mx_thresholds:
            multiplier += 1
    
        chord_points += note_points * multiplier
        
    return chord_points    
    
def dynamicscores(chord, combo):
    s = {'ghosts': 0, 'accents': 0, 'base': 0}
    
    mx_thresholds = [10,20,30]
    multiplier = to_multiplier(combo)
    for note in sorted(chord.notes(), key=lambda n: n.basescore()):
        combo += 1
        if combo in mx_thresholds:
            multiplier += 1
        
        if note.is_ghost():
            s['ghosts'] += note.basescore() * multiplier
            
            if note.is_cymbal():
                # CH does this for some reason
                s['ghosts'] -= 15
                s['base'] += 15
            
        if note.is_accent():
            s['accents'] += note.basescore() * multiplier
            
            if note.is_cymbal():
                # CH does this for some reason
                s['ghosts'] -= 15
                s['base'] += 15
        
    return s    
    
def to_multiplier(combo):
    if combo < 10:
        return 1
    elif combo < 20:
        return 2
    elif combo < 30:
        return 3
    else:
        return 4
    
# To do: this are now path details rather than logging related
class Activation:
    
    def __init__(self, chord, skips, sp, measure):
        self.chord = chord
        self.skips = skips
        self.sp = sp
        self.measure = measure
        self.activation_squeeze = None
        self.backend_squeeze = None
        self.phrase_squeeze = None # todo better data structure for this tristate (None, In, Out)
        self.quantum_fill = None
        
# A chord, the multiplier the chord hits, the number of notes that can be squeezed, and the associated point difference.
class MultiplierSqueeze:
    
    def __init__(self, chord, multiplier, squeeze_count, extrascore):
        self.chord = chord
        self.multiplier = multiplier
        self.squeeze_count = squeeze_count
        self.extrascore = extrascore
        
    @staticmethod
    def from_context(chord, combo, sp_active):
        best_points = comboscore(chord, combo)
        worst_points = comboscore(chord, combo, reverse=True)
        
        if sp_active:
            best_points *= 2
            worst_points *= 2
        
        if best_points != worst_points:
            squeeze_count = (combo + chord.count()) % 10 + 1
            return MultiplierSqueeze(chord, to_multiplier(combo), squeeze_count, best_points - worst_points)
            
        return None

# skips_with_fill is the 'E number' in path notation.
# offset_to_flip_ms is the threshold where the fill no longer appears, reducing skips by 1.
class CalibrationFill:

    def __init__(self, skips_with_fill, offset_to_flip_ms):
        self.skips_with_fill = skips_with_fill
        self.offset_to_flip_ms = offset_to_flip_ms

class ActivationSqueeze:
    
    def __init__(self, chord, extrascore):
        self.chord = chord
        self.extrascore = extrascore
        
    @staticmethod
    def from_context(chord, combo):
        # best points: entire chord is under sp
        best_points = comboscore(chord, combo) * 2
        
        # worst points: only activation note is under sp; 2x it by adding it again
        worst_points = comboscore(chord, combo) + chord.get_activation_note_basescore()*to_multiplier(combo + chord.count())
        
        if best_points != worst_points:
            return ActivationSqueeze(chord, best_points - worst_points)
        
        return None

class BackendSqueeze:
    
    def __init__(self, extrascore):
        self.extrascore = extrascore


# Maintains multiple path objects and feeds song data into them.
# Paths only know about themselves; Optimizer can compare paths and handle when a branching choice occurs in a path.
class Optimizer:

    def __init__(self):
        # Gameplay simulations, each with different scores and a description of the gameplay choices it took (i.e. which spots it deployed star power).
        self.paths = [Path()]


    # Reduce the number of paths to analyze by removing paths that are strictly worse than another path.
    # When final is True, stored sp has no value.
    def remove_strictly_worse_paths(self, final=False):
        path_ranking = sorted(self.paths, key=lambda p: -p.get_best_total_score())
        bad_paths_i = []
        for i in range(len(path_ranking)):
            path_a = path_ranking[i]
            for j in range(i + 1, len(path_ranking)):
                path_b = path_ranking[j]
                if path_a.strictly_compare(path_b, final):
                    bad_paths_i.append(j)
                    
        self.paths = [p for i,p in enumerate(path_ranking) if i not in bad_paths_i]

    # Process a song.
    def run(self, song):
        for timestamp in song.sequence:
            self.read_timestamp(timestamp)
        self.remove_strictly_worse_paths(final=True)

    def read_timestamp(self, timestamp):
        new_paths = []

        for p in self.paths:
            bifurcations = p.push_timestamp(timestamp)
            new_paths += bifurcations
            
        self.paths += new_paths
        self.remove_strictly_worse_paths()




