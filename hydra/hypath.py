import shutil
import copy
import math
import json
from enum import Enum

from . import hynote
from . import hyrecord
from . import hymisc


class ScoreGraph:
    """Description of a song in terms of pathing choices and outcomes.
    
    Consists of nodes representing timecodes for the song and edges
    representing either getting further in the song (advancing) or
    switching between inactive and active SP (branching).
    
    To that end, the nodes form two tracks: the normal track and SP
    track. There are only branch edges between the tracks where it's
    possible to activate (with a fill) or deactivate (run out of) SP.
    
    Edges store information about what is gained (mainly points and SP)
    from taking that edge.
    
    Advancing down a track gets further in the song and accrues points.
    Branching does not advance time, but possibly accrues features like
    backends which are specific to the act of toggling SP.
    
    Because "your current SP" isn't encoded on the graph, not every path
    through it is a valid path for the song. However, the graph contains
    all the info needed to go from start to finish while tracking sp, in
    order to explore valid paths through the song.
    
    """
    def __init__(self, song):
        """Depends on hysong.Song, for all intents and purposes"""
        self.songhash = song.songhash
        
        start_time = song.start_time()
        self.base_track_head = ScoreGraphNode(start_time, False)
        self.sp_track_head = ScoreGraphNode(start_time, True)
        
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
        
        self.acc_sp_phrases = [] # array of (timecode, map of timecodes: extended timecodes factoring cap into account)
        
        self.debug_total_basescore = 0
        
        self.acc_multsqueezes = []
        
        self.acc_latest_sp_time = None
        
        self.recent_deacts = []
        
        backend_history = [] # Timestamps back to -140ms
        self.live_backend_edges = [] # deactivation edges that are accepting scored timestamps up to +140ms
        for ts_i, timestamp in enumerate(song.sequence):
            
            self.recent_deacts = [tc for tc in self.recent_deacts if timestamp.timecode.ms - tc.ms < 140]
            
            self.debug_total_basescore += timestamp.chord.debug_basescore()
            
            # handle any deacts that occur between timestamps
            gap_deacts = sorted([tc for tc in pending_deacts if tc < timestamp.timecode])

            for pending_deact in gap_deacts:
                # Update backend history (but there aren't any new ones)
                backend_history = [be for be in backend_history if timestamp.timecode.ms - be[0].timecode.ms < 140]
                self.advance_tracks(pending_deact, None)
                self.add_deact_edge(backend_history, song)
                if timestamp.timecode.ms - pending_deact.ms < 140:
                    self.recent_deacts.append(pending_deact)
                    
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
                msq.squeezecount = (self.combo + timestamp.chord.count()) % 10 + 1
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
            backend_history = [be for be in backend_history if timestamp.timecode.ms - be[0].timecode.ms < 140]
            backend_history.append(_backend)
            
            # Add this chord's sp points to any deactivation that happened recently
                
            #self.live_backend_edges = [e for e in self.live_backend_edges if e.dest.timecode.offset_ms(timestamp.timecode) < 140]
            valid_backend_edges = []
            for e in self.live_backend_edges:
                e_offset = timestamp.timecode.ms - e.dest.timecode.ms
                if e_offset < 140:
                    valid_backend_edges.append(e)
                    edge_backend = copy.copy(_backend)
                    edge_backend[0].offset_ms = e_offset
                    e.backends.append(edge_backend)
                    
                    if edge_backend[1]: # backend is also sp
                        offset = edge_backend[0].timecode.ms - e.dest.timecode.ms
                        e.sqinout_time = min(e.sqinout_time, edge_backend[0].timecode)  if e.sqinout_time else edge_backend[0].timecode
                        e.sqinout_timing = min(e.sqinout_timing, offset) if e.sqinout_timing != None else offset
                        e.sqinout_amount += 1
                        e.sqinout_indicator_time = e.sqinout_indicator_time.plusmeasure(2, song)
            self.live_backend_edges = valid_backend_edges
                    
            if timestamp.flag_sp:
                # If any deacts are only the squeeze window away (140ms), keep a non-extended copy of them (SqOut)
                sqout_deacts = set([tc for tc in pending_deacts if tc.ms - timestamp.timecode.ms < 140])
                
                # Deact timecodes that can be extended by this sp: current pending deacts as well as very recently handled deacts (SqIn)
                extendable_tcs = pending_deacts.union(set(self.recent_deacts))
                
                # Deact timecodes after extension: end time + 2 measures or capped at now + 8 measures
                extension_map = {tc: min(tc.plusmeasure(2, song), timestamp.timecode.plusmeasure(8, song)) for tc in extendable_tcs}
                
                # Update deacts
                pending_deacts = set(extension_map.values()).union(sqout_deacts)
                
                # Save info on the graph
                self.acc_sp_phrases.append((timestamp.timecode, extension_map))
                self.acc_latest_sp_time = timestamp.timecode
                
                
            # handle acts            
            if timestamp.flag_activation:
                self.advance_tracks(timestamp.timecode, timestamp.chord)
                self.add_act_edge(timestamp.chord, timestamp_spscore, timestamp.activation_fill_length_ticks, song)
                
                pending_deacts.add(timestamp.timecode.plusmeasure(4, song))
                pending_deacts.add(timestamp.timecode.plusmeasure(6, song))
                pending_deacts.add(timestamp.timecode.plusmeasure(8, song))
                
            # handle deacts
            if timestamp.timecode in pending_deacts:
                self.advance_tracks(timestamp.timecode, timestamp.chord)
                self.add_deact_edge(backend_history, song)
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
        
            
    def add_act_edge(self, frontend_chord, frontend_points, fill_length_ticks, song):

        
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
        
        act_edge.activation_initial_end_times = {sp: act_edge.dest.timecode.plusmeasure(2 * sp, song) for sp in [2, 3, 4]}
        
        
        self.base_track_head.branch_edge = act_edge
        

        
    def add_deact_edge(self, prior_backends, song):
        deact_edge = ScoreGraphEdge()
        deact_edge.dest = self.base_track_head
        
        deact_edge.notecount = 0
        deact_edge.basescore = 0
        deact_edge.comboscore = 0
        deact_edge.spscore = 0
        deact_edge.soloscore = 0
        deact_edge.accentscore = 0
        deact_edge.ghostscore = 0
        
        deact_edge.sqinout_indicator_time = deact_edge.dest.timecode
        
        # notes just prior to this deactivation, which are normally in sp but could be squeezed out
        for be in prior_backends:
            deact_edge.backends.append(copy.copy(be))
            deact_edge.backends[-1][0].offset_ms = be[0].timecode.ms - deact_edge.dest.timecode.ms
            
            # Some checks that can be done here instead of every path doing it
            if be[1]: # backend is also sp
                offset = be[0].timecode.ms - deact_edge.dest.timecode.ms
                deact_edge.sqinout_time = be[0].timecode
                deact_edge.sqinout_timing = min(deact_edge.sqinout_timing, offset) if deact_edge.sqinout_timing != None else offset
                deact_edge.sqinout_amount += 1
                deact_edge.sqinout_indicator_time = deact_edge.sqinout_indicator_time.plusmeasure(2, song)
        
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
        self.sqinout_indicator_time = None

        
    def __repr__(self):
        return f" --> {self.dest.name()}, frontend = {self.frontend}"
    
    
class GraphPather:
    """Responsible for creating multiple paths and for creating hyrecords.
    
    Reads ScoreGraphs; stores a hyrecord for the latest graph that was read.
    
    """
    def __init__(self):
        self.record = hyrecord.HydraRecord()
        
    def read(self, graph):
        paths = [GraphPath()]
        paths[0].currentnode = graph.start
        
        while any([not p.is_complete() for p in paths]):
            # Advance paths
            for p in paths:
                p.advance()
                    
            # Branch paths if possible (activate or deactivate)
            new_paths = []
            terminated_paths = []
            for p in paths:
                terminated, branchpath = p.branch()
                if terminated:
                    terminated_paths.append(p)
                if branchpath:
                    new_paths.append(branchpath)
                    
            # Update the path list with branching results
            paths = [p for p in paths if p not in terminated_paths] + new_paths
            
            # Pruning: removing paths that are strictly worse.
            # Customization of this rule, coming soon.
            # Also maybe something better than this n^2 thing.
            paths = [p for p in paths if not any([p.strictly_worse(other) for other in paths])]

        # Order the completed paths by score
        paths.sort(key=lambda p: p.record.totalscore(), reverse=True)
    
        # Paths already built their HydraRecordPaths; add them to our hyrecord
        for path in paths:
            # Fix chords - to do: Fix it at the source
            for act in path.record.activations:
                if act.frontend:
                    act.frontend.chord = hyrecord.HydraRecordChord.from_chord(act.frontend.chord)
                for be in act.backends:
                    be.chord = hyrecord.HydraRecordChord.from_chord(be.chord)
            
            # Save optimal for convenience (it's just the sum of the other scores)
            path.record.ref_totalscore = path.record.totalscore()
            
            self.record.paths.append(path.record)

        # Fill out more fields on hyrecord
        #self.record.hyhash = graph.songhash

class GraphPath:
    """Quick early note:
    
    This class should do as little work as possible as it navigates the
    score graph. Any time that a GraphPath is *building* something, move
    it to ScoreGraph if at all possible.
    
    """
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
        
        return self.record.totalscore() < other.record.totalscore() and self_sp_value <= other_sp_value
        
    # Develop along the edge that leads farther into the song.
    # Always moves a path closer to being complete, unless it's already complete.
    def advance(self):
        #print("Path advancing:")
        
        if self.is_complete():
            #print("\tOops, I was already done.")
            return
        
        adv_edge = self.currentnode.adv_edge
        if adv_edge:
            self.record.score_base += adv_edge.basescore
            self.record.score_combo += adv_edge.comboscore
            self.record.score_sp += adv_edge.spscore
            self.record.score_solo += adv_edge.soloscore
            self.record.score_accents += adv_edge.accentscore
            self.record.score_ghosts += adv_edge.ghostscore
            
            self.record.notecount += adv_edge.notecount
            
            #print(f"\tGoing to {adv_edge.dest.timecode.measurestr()}.")
            # Applying SP on this edge
            if self.currentnode.is_sp:
                # Path is in SP: Immediately "spend" SP bars and adjust the sp end time
                #print(f"\tSP: {self.sp} + {len(adv_edge.sp_times)} = {min(max(0, self.sp + len(adv_edge.sp_times)), 4)}.")
                
                # Handling each sp individually since SP capping is based on each one's particular time
                # To do: Find a way to store the plusmeasures on the graph
                # The sp_times can be a tuple with the sp time and the sp time + 8 measures
                # The sp extension is actually the same as the pending_deact extensions in ScoreGraph so let's use those
                for sptc, extension_map in adv_edge.sp_times:
                    if self.buffered_sqin_sp > 0:
                        self.buffered_sqin_sp -= 1
                    else:
                        self.sp_end_time = extension_map[self.sp_end_time]
                
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
        """Create a new path if possible, to represent changing from SP to 
        non-SP or vice versa.
        
        For example, if this path is at an activation point, then the new
        branch path represents activating here, while the existing path
        will continue to represent inactive SP.
        
        returns terminated, new_path
        
        terminated: True when the new branch path is the only valid option,
        which is usually the case when SP deactivates.
        
        new_path: A new path which is like a clone of this path except it has
        taken the branch edge here.
        
        """
        #print("Path branching:")
        if self.is_complete():
            #print("\tOops, I was already done.")
            return False, None

        #print(f"\tI'm at {self.currentnode.timecode.measurestr()} and SP is {'' if self.currentnode.is_sp else 'in'}active...")
        
        br_edge = self.currentnode.branch_edge
        if not br_edge:
            #print("\tOops, branch edge not found.")
            return False, None
            
        # Check conditions for activation
        if br_edge.dest.is_sp and (self.sp < 2 or self.sp == 2 and self.latest_sp_time.ticks + 2*br_edge.activation_fill_length_ticks > self.currentnode.timecode.ticks):
            #print(f"\tActivation conditions not met: sp = {self.sp}")
            return False, None
        
        # Check conditions for deactivation
        sq_out = False
        if not br_edge.dest.is_sp and br_edge.dest.timecode != self.sp_end_time:
            # This path is deactivating later, but maybe we can tell the only sp time left was squeezed in, in which case we can squeeze it out.
            if br_edge.sqinout_indicator_time == self.sp_end_time:
                sq_out = True
                #print("\tSqOut conditions met")
            else:
                #print(f"\tDeactivation conditions not met: my sp end time is {self.sp_end_time.measurestr()}")
                return False, None
        
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
            
            new_path.sp_end_time = br_edge.activation_initial_end_times[self.sp]
            
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
                # Typical deactivation
                
                # If a backend is only a few ms away, just add it in for free without calling it a double squeeze
                for be,be_sp in br_edge.backends:
                    if be.offset_ms > 0 and be.offset_ms < 3:
                        new_path.record.score_sp += be.points

                # SqIn may be possible, which would save self from being removed imminently
                if br_edge.sqinout_amount > 0:
                    print("\tSpecial condition for late SqIn occurred.")
                    new_path.record.activations[-1].sqinouts.append('-')
                    self.record.activations[-1].sqinouts.append('+')
                    # self got here by being at its sp end time, but now it can be extended.
                    self.sp_end_time = br_edge.sqinout_indicator_time
                    self.buffered_sqin_sp = br_edge.sqinout_amount
        
        terminated = self.currentnode.is_sp and self.currentnode.timecode == self.sp_end_time
        return terminated, new_path
            
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
    
def to_multiplier(combo):
    if combo < 10:
        return 1
    elif combo < 20:
        return 2
    elif combo < 30:
        return 3
    else:
        return 4
    