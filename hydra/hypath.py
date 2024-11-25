import shutil
import mido
import copy
from enum import Enum
import math
import re

from . import hynote
from . import hylog

# base note: 50
# cymbal: 65
# dynamic: 2x

# solo bonus: +100 per solo note

# The lengths of activation fills are just visual and only the activation chord needs to be considered.
# Activation notes are autoplayed; skipping activations does not affect base score / combo.

# Multiplier squeeze: In a chord that straddles a multiplier, hit lower-value notes first.
#   Also known as squeezing cymbals or dynamics.
# Activation squeeze: In a chord with an activation note, hit the activation note first.
#   Also known as a frontend squeeze.
#   Can happen at the same time as multiplier squeezes, but not only is it rare, it's also safe to assume the activation squeeze takes priority.
# Backend squeeze: For a chord that happens exactly when active SP ends, hit early to fit the chord in SP.
# Path squeeze in: For an SP phrase that completes exactly when active SP ends, hit early to extend SP.
# Path squeeze out: For an SP phrase that completes exactly when active SP ends, hit late to avoid extending SP.
#   Reduces the effectiveness of backend squeezes by 1 note.

# SP modifier: 116
# Fill modifier: 120-124
# Solo modifier: 103

# To do: A better name that reflects that *this* is the part that is simulating score gains and SP behavior.
class Path:
    # Once 50% sp is gained, since upcoming notes are already on screen, a fill has to start after this lockout in order to appear.
    fill_lockout_seconds = 1.8
    
    # For a fill to appear, there needs to be this many measures between gaining 50% SP and the start of the fill.
    fill_lockout_measures = 1.0
    
    uid = 1
    
    # Fills close to the window might be able to be influenced by early/late hits?
    
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
        self.activation_records = []
        
        # Details about every single fill the path encountered.
        self.fill_records = []
        
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
        
        self.chord_log = []
        
    def __str__(self):
        return f"Path {self.debug_id}, {[a.skips for a in self.activation_records]} + {self.current_skips}, {self.get_best_total_score()}, SP={self.sp_meter}, active SP={self.sp_active}"
        
    # A path is strictly better if it has a better score and equal or more star power while in the same star power state and same timestamp.
    # This function returns True (self is better), False (other is better), or None (inconclusive).
    # When final is True, stored sp has no value
    def strictly_compare(self, other, final=False):        
        if self.sp_active != other.sp_active or self.latest_timestamp_time != other.latest_timestamp_time:
            return None
        return self.get_best_total_score() > other.get_best_total_score() and (final or self.sp_meter >= other.sp_meter)
            
    def quick_match(self, skips):
        return len(skips) == len(self.activation_records) and all([self.activation_records[i].skips == skips[i] for i in range(len(skips))])
        
    def report(self, output):
        
        #for l in self.chord_log:
        #   l.report(output)
        
        #for f in self.fill_records:
        #    f.report(output)
        
        output.write("\t\tActivations:\n")
        if len(self.activation_records) == 0:
            output.write("\t\t\tNone\n")
        
        for r in self.activation_records:
            r.report(output)
        
        output.write("\t\tMultiplier squeezes:\n")
        if len(self.multiplier_squeezes) == 0:
            output.write("\t\t\tNone\n")
        
        for ms in self.multiplier_squeezes:
            ms.report(output)
        
        output.write("\n\t\tSummary:\n")
        output.write(f"\n\t\t\tBase score: {self.basescore}\n")
        output.write(f"\t\t\tSolo bonus: {self.solobonus}\n")
        output.write(f"\t\t\tStar power: +{self.spscore}\n")
        
        output.write(f"\n\t\t\tDynamics: +{self.basedynamics}\n")
        output.write(f"\t\t\tMultiplier squeezes: +{sum([s.extrascore for s in self.multiplier_squeezes])}\n")
        output.write(f"\t\t\tActivation squeezes: +{sum([s.extrascore for s in self.activation_squeezes])}\n")
        output.write(f"\t\t\tBackend squeezes: +{sum([s.extrascore for s in self.backend_squeezes])}\n")
        
        output.write(f"\n\t\t\tMinimum score:{' '*(10 - len(str(self.get_worst_total_score())))}{self.get_worst_total_score()}\n")
        output.write(f"\t\t\tPerfect score:{' '*(10 - len(str(self.get_best_total_score())))}{self.get_best_total_score()}\n")
    
    
    def get_best_total_score(self):
        return self.basescore + self.solobonus + self.basedynamics + self.spscore + sum([s.extrascore for s in self.multiplier_squeezes]) + sum([s.extrascore for s in self.activation_squeezes]) + sum([s.extrascore for s in self.backend_squeezes]) 
    
    # FCing and hitting the correct path but missing all squeezes and dynamics
    def get_worst_total_score(self):
        return self.basescore + self.solobonus + self.spscore
    
    def push_timestamp(self, timestamp):
        # Timestamp comes both with elapsed time and a chord.
        
        timestamp_is_sp_border = False
        
        chord_log_features = []
                
        # spend sp
        if self.sp_active:
            self.sp_meter -= (timestamp.measure - self.latest_timestamp_measure)/8.0
            # to do: it might be possible to make this floating point error less impactful but it requires a refactor on how measures are calculated/expressed
            # resolution of this error window: 1/128th of a measure
            if self.sp_meter <= 0.0009765625:
                self.sp_meter = 0.0
                self.sp_active = False
                timestamp_is_sp_border = True
                
            chord_log_features.append(f"active sp = {self.sp_meter}")
                
        new_paths = []
        

        
        # Multiplier squeeze: In a chord that straddles a multiplier, hit lower-value notes first.
        multiplier_squeeze = timestamp.chord.get_multiplier_squeeze(self.combo, self.sp_active or timestamp_is_sp_border)
        if multiplier_squeeze != None and not timestamp.flag_activation:
            # If a chord is both a multiplier squeeze and an activation squeeze (not likely), just treat it as an activation squeeze
            self.multiplier_squeezes.append(multiplier_squeeze)
            chord_log_features.append("multiplier squeeze")
        
        # Add score for this timestamp
        chordscore_no_dynamics = timestamp.chord.comboscore(self.combo, reverse=True, no_dynamics=True)
        
        # SP and squeeze calculations will assume dynamics are being hit.
        chordscore = timestamp.chord.comboscore(self.combo, reverse=True)
        
        self.combo += timestamp.chord.count()
        
        self.basescore += chordscore_no_dynamics
        self.basedynamics += chordscore - chordscore_no_dynamics
        
        if timestamp_is_sp_border:
            # Backend squeeze: Ranges from whole chord not in sp (this score has already been applied) to fully in sp.
            backend_squeeze = hylog.BackendSqueeze(chordscore)
            self.activation_records[-1].backend_squeeze = backend_squeeze
            self.backend_squeezes.append(backend_squeeze)
            chord_log_features.append("sp - backend squeeze")
        elif self.sp_active:
            # Regular sp chord
            self.spscore += chordscore
            chord_log_features.append("sp")
        
        
        
        if timestamp.flag_activation:
            assert(timestamp.activation_fill_length_seconds != None)
            
            # 3 possible outcomes for a fill:
            # - Skip (fill appears and is not taken)
            # - Take (fill appears and is activated)
            # - Ignore (fill doesn't appear at all and doesn't count towards the path's skips)
            # For some fills, player late/early input can change a fill from Skip/Take to Ignore and vice versa.
            # So really we can count up the possible bifurcations for every fill when sp is ready:
            # Fills that normally appear:
            # - Normally appears, and is skipped
            # - Normally appears, and is taken
            # - Forced to not appear
            #       Doesn't need to be considered: because of equal scoring, is redundant with "normally appears and is skipped"
            # Fills that normally don't appear:
            # - Normally doesn't appear
            #       Has no impact on the path.
            # - Forced to appear, and is skipped
            #       Doesn't need to be considered: because of equal scoring, is redundant with "normally doesn't appear"
            # - Forced to appear, and is taken
            #       This is the special case where an early activation is available with special input timing.
            
            
            
            self.fill_records.append(hylog.FillRecord(timestamp.measure, self.sp_active, self.sp_meter))
            
            if self.sp_active:
                self.fill_records[-1].result = "Non-appearing (SP already active)"
            elif self.sp_meter < 0.5:
                self.fill_records[-1].result = "Non-appearing (not enough SP)"
            
            
            # First condition for activations: not already in star power and has enough star power
            if not self.sp_active and self.sp_meter >= 0.5:
                
                self.fill_records[-1].sp_age_time = timestamp.time - timestamp.activation_fill_length_seconds - self.sp_ready_time
                self.fill_records[-1].sp_age_measures = timestamp.activation_fill_start_measure - self.sp_ready_measure
            
                # Even if SP is ready to activate, it has to be ready for a certain length of time before fills start to appear.
                # This time (in beats) is measured in realtime, so it's influenced by calibration and player timing.
                
                threshold_difference_beats = timestamp.activation_fill_start_beat - self.sp_ready_beat - 4.0
                self.fill_records[-1].threshold_beats = threshold_difference_beats
                
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
                    skip_log_features = copy.deepcopy(chord_log_features)
                    skip_log_features.append("Skipped fill")
                    skip_option.current_skips += 1
                    skip_option.chord_log.append(hylog.ChordLogEntry(timestamp.chord, skip_log_features, timestamp.measure))
                    if is_timing_sensitive:
                        # Whenever the next activation is logged, we'll note that the first skip was timing sensitive.
                        skip_option.skipped_quantum_fill = hylog.QuantumFill(0, threshold_offset_ms) # Skipped but may not appear
                        skip_log_features.append("Timing sensitive")
                    skip_option.fill_records[-1].result = "Skipped"
                    new_paths.append(skip_option)
                
                    #print(f"\tActivating.")
                    # The fill can appear either normally or with early timing, so it's activatable.
                    self.sp_active = True
                    
                    chord_log_features.append("activation")
                    self.activation_records.append(hylog.ActivationRecord(timestamp.chord, self.current_skips, self.sp_meter, timestamp.measure))
                    if self.skipped_quantum_fill != None:
                        self.skipped_quantum_fill.skips_with_fill += self.current_skips
                        self.activation_records[-1].quantum_fill = self.skipped_quantum_fill
                        self.skipped_quantum_fill = None
                    elif is_timing_sensitive:
                        chord_log_features.append("Timing sensitive")
                        self.activation_records[-1].quantum_fill = hylog.QuantumFill(0, threshold_offset_ms) # Activated but may not appear
                    self.sp_ready_time = None
                    self.sp_ready_measure = None
                    self.sp_ready_measure_earlyhit = None
                    self.sp_ready_measure_latehit = None
                    self.sp_ready_beat = None
                    self.sp_ready_beat_earlyhit = None
                    self.sp_ready_beat_latehit = None
                    self.current_skips = 0
                    self.fill_records[-1].result = "Activated"
                    # The activation chord was already scored, but 1 or more notes are actually under the sp that just activated.
                    # Add the bare minimum (the activation note) to non-squeeze scoring.
                    self.spscore += timestamp.chord.get_activation_note_basescore()*hynote.to_multiplier(self.combo)
                    
                    activation_squeeze = timestamp.chord.get_activation_squeeze(self.combo)
                    if activation_squeeze != None:
                        self.activation_squeezes.append(activation_squeeze)
                        self.activation_records[-1].activation_squeeze = activation_squeeze
                        chord_log_features.append("sp - activation squeeze")
                    else:
                        chord_log_features.append("sp")
                
                
                elif threshold_offset_ms > -offset_limit:
                    # The fill can be forced to appear. We're choosing between doing nothing and forcing it to appear AND activating.
                    # With the way fills are scored, there's no value in forcing this fill to appear, which is harder, just to skip it.
                    # However, that may still happen accidentally.
                    forced_early_option = copy.deepcopy(self)
                    forced_early_option.debug_id = Path.uid
                    Path.uid += 1
                    forced_early_log_features = copy.deepcopy(chord_log_features)
                    forced_early_log_features.append("Forced early activation")
                    forced_early_option.sp_active = True
                    forced_early_option.activation_records.append(hylog.ActivationRecord(timestamp.chord, forced_early_option.current_skips, forced_early_option.sp_meter, timestamp.measure))
                    forced_early_option.activation_records[-1].quantum_fill = hylog.QuantumFill(0, threshold_offset_ms) # Activated, forced to appear
                    forced_early_option.sp_ready_time = None
                    forced_early_option.sp_ready_measure = None
                    forced_early_option.sp_ready_measure_earlyhit = None
                    forced_early_option.sp_ready_measure_latehit = None
                    forced_early_option.sp_ready_beat = None
                    forced_early_option.sp_ready_beat_earlyhit = None
                    forced_early_option.sp_ready_beat_latehit = None
                    forced_early_option.current_skips = 0
                    forced_early_option.fill_records[-1].result = "Activated (forced to appear)"
                    
                    # The activation chord was already scored, but 1 or more notes are actually under the sp that just activated.
                    # Add the bare minimum (the activation note) to non-squeeze scoring.
                    forced_early_option.spscore += timestamp.chord.get_activation_note_basescore()*hynote.to_multiplier(forced_early_option.combo)
                    
                    activation_squeeze = timestamp.chord.get_activation_squeeze(forced_early_option.combo)
                    if activation_squeeze != None:
                        forced_early_option.activation_squeezes.append(activation_squeeze)
                        forced_early_option.activation_records[-1].activation_squeeze = activation_squeeze
                        forced_early_log_features.append("sp - activation squeeze")
                    else:
                        forced_early_log_features.append("sp")
                
                    forced_early_log_features.append(f"{chordscore}")
                    forced_early_option.chord_log.append(hylog.ChordLogEntry(timestamp.chord, forced_early_log_features, timestamp.measure))
                    
                    forced_early_option.latest_timestamp_time = timestamp.time
                    forced_early_option.latest_timestamp_measure = timestamp.measure
                    new_paths.append(forced_early_option)
                    self.fill_records[-1].result = "Non-appearing (too soon after getting SP)"
                    self.skipped_quantum_fill = hylog.QuantumFill(1, threshold_offset_ms) # Doesn't appear but may appear and be skipped
                else:
                    self.fill_records[-1].result = "Non-appearing (too soon after getting SP)"
                    
        if timestamp.flag_sp:
            
            if timestamp_is_sp_border:
                # this path will be an sp extension; spawn a new path where the sp expires.
                sq_out = copy.deepcopy(self)
                sq_out_log_features = copy.deepcopy(chord_log_features)
                sq_out_log_features.append("sq-out +25% sp")
                sq_out.chord_log.append(hylog.ChordLogEntry(timestamp.chord, sq_out_log_features,timestamp.measure))
                sq_out.sp_meter = 0.25
                # there was a brand-new backend squeeze; reduce it by the minimum 1 note that must be left out of sp
                sq_out.backend_squeezes[-1].extrascore -= timestamp.chord.point_spread()[0]*hynote.to_multiplier(self.combo)
                sq_out.activation_records[-1].phrase_squeeze = "Out"
                new_paths.append(sq_out)

                chord_log_features.append("sq-in sp extension")
                self.activation_records[-1].phrase_squeeze = "In"
                # reactivate 
                self.sp_active = True
                self.sp_meter = 0.25
            else:
                # add sp
                if self.sp_active:
                    chord_log_features.append("sp extension")
                
                chord_log_features.append("+25% sp")
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
            chord_log_features.append("solo")
            self.solobonus += 100 * timestamp.chord.count()
        chord_log_features.append(f"{chordscore}")
        self.chord_log.append(hylog.ChordLogEntry(timestamp.chord, chord_log_features, timestamp.measure))
        
        self.latest_timestamp_time = timestamp.time
        self.latest_timestamp_measure = timestamp.measure
        
        return new_paths
    

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
        
    # Print results.
    def report(self, output):
        path_ranking = sorted(self.paths, key=lambda p: -p.get_best_total_score())
        best_score = path_ranking[0].get_best_total_score()

        best_paths = [p for p in self.paths if p.get_best_total_score() == best_score]
        
        for i,p in enumerate(best_paths):
            output.write(f'\n\tOptimal path {i+1}:\n')
            p.report(output)

    def report_fills(self, name, valid_file, invalid_file):
        path_ranking = sorted(self.paths, key=lambda p: -p.get_best_total_score())
        best_score = path_ranking[0].get_best_total_score()

        best_path = [p for p in self.paths if p.get_best_total_score() == best_score][0]
        
        for f in best_path.fill_records:
            if f.sp_age_time != None and f.sp_age_measures != None:
                rowstr = f"{name};{f.measure};{f.sp_age_time};{f.sp_age_measures};{f.result}"
                if f.result.startswith("Non-appearing"):
                    invalid_file.write(f"{rowstr}\n")
                else:
                    valid_file.write(f"{rowstr}\n")
        
    def read_timestamp(self, timestamp):
        
        # to do: paths need to know if a chord is in sp and if a chord is on an sp border
        new_paths = []
        #print(f"----------")
        for p in self.paths:
            #print(f"{p.debug_id}:\t{[a.skips for a in p.activation_records]} + {p.current_skips}")
            bifurcations = p.push_timestamp(timestamp)
            new_paths += bifurcations
            
        self.paths += new_paths
        
        self.remove_strictly_worse_paths()



class SongTimestamp:
    
    def __init__(self):
        # Timing from start of the song
        self.time = 0.0
        self.measure = 0.0
        self.beat = 0.0
        
        self.beat_earlyhit = None
        self.beat_latehit = None
        
        self.measure_earlyhit = None
        self.measure_latehit = None
        
        # Notes
        self.chord = None
        
        # Flags
        self.flag_activation = False
        self.flag_solo = False
        self.flag_sp = False
        
        # to do: completely linked to flag_activation, could be simplified?
        self.activation_fill_length_seconds = None
        self.activation_fill_start_measure = None
        self.activation_fill_start_beat = None
        
        # Meter
        self.tempo = None
        self.ts_numerator = None
        self.ts_denominator = None

# Common and streamlined format for the optimizer to run through.
# The main structure is an ordered sequence of timestamps. Each timestamp contains all the notes and markers happening at that time.
# Most events are attached to chords, but a few aren't: Activation fill starts.
# To do: Move grants sp, is activation, etc. from chord to timestamp.
class Song:
    
    def __init__(self):
        self.sequence = []
        
        self.note_count = 0
        self.ghost_count = 0
        self.accent_count = 0
        self.solo_note_count = 0
        
        self.generated_fills = False
    
    def report(self, output):
        
        
        if self.generated_fills:
            output.write(f"\n\t**Warning: This chart uses auto-generated fills, please double check correctness.\n")

        
        output.write(f"\n\tNotes: {self.note_count}\n")

        if self.solo_note_count > 0:
            output.write(f"\n\tSolo bonus: {100 * self.solo_note_count}\n")
            
    # If a chart has no drum fills, add them at measure 3 + 4n, half a measure long, if there's a chord there.
    # To do: The details of this rule need to be explored
    def check_activations(self):
        if all([not timestamp.flag_activation for timestamp in self.sequence]):
            self.generated_fills = True
            leadin_ts_numerator = self.sequence[0].ts_numerator
            leadin_ts_denominator = self.sequence[0].ts_denominator
            for timestamp in self.sequence:
                assert(timestamp.ts_numerator != None)
                assert(timestamp.ts_denominator != None)
                if abs(round(timestamp.measure) - timestamp.measure) < 0.00001 and (round(timestamp.measure) - 3) % 4 == 0 and timestamp.chord != None and not timestamp.flag_sp:
                    timestamp.flag_activation = True
                    timestamp.activation_fill_start_measure = timestamp.measure - 0.5
                    timestamp.activation_fill_length_seconds = 60.0 / timestamp.tempo * (leadin_ts_numerator / 2) * (4/leadin_ts_denominator)
                    timestamp.activation_fill_start_beat = timestamp.beat - (leadin_ts_numerator / 2) * (4/leadin_ts_denominator)
                leadin_ts_numerator = timestamp.ts_numerator
                leadin_ts_denominator = timestamp.ts_denominator

# Converts midi files to a common format for path analysis
class MidiParser:
    
    def __init__(self):
        # Song format that we're building up with timestamps
        self.song = None
        
        # The current timestamp, which due to a few retroactive modifiers isn't fully determined until we've hit the next chord in a future timestamp.
        # Some useless midi timepoints (like ones that only have note-offs for drum notes) won't become timestamps.
        self.timestamp = SongTimestamp()
        
        self.elapsed_time = 0.0
        self.elapsed_measures = 0.0
        self.elapsed_beats = 0.0
        self.ticks_per_beat = None
        
        # A fill ended, so the next chord will be marked as an activation (but we need to wait for it to be finalized).
        self.fill_primed = False
        # We started a fill, so we expect an activation timestamp in the future and when we set it we'll save this info to it.
        self.fill_start_time = None
        self.fill_start_measure = None
        
        # The next encountered chord will cause the current timestamp to finalize. 
        self.push_primed = False
        
        # Current state of markers that apply to all chords in their range
        self.tom_flags = {98:False, 99:False, 100:False}
        self.solo_active = False
        self.disco_flip = False
        
        # Current state of params that affect time
        self.tempo = None
        self.ts_numerator = 4
        self.ts_denominator = 4
    
    def push_timestamp(self):
        assert(self.song != None)
        assert(self.timestamp != None)
        assert(self.push_primed)
        
        self.push_primed = False
        
        if self.timestamp.chord == None or self.timestamp.chord.count() == 0:
            assert(len(self.song.sequence) == 0)
            self.timestamp = SongTimestamp()
            return
            
        # Update song-wide info
        self.song.note_count += self.timestamp.chord.count()
        self.song.ghost_count += self.timestamp.chord.ghost_count()
        self.song.accent_count += self.timestamp.chord.accent_count()
        if self.timestamp.flag_solo:
            self.song.solo_note_count += self.timestamp.chord.count()
        
        # Add timestamp to song
        self.song.sequence.append(self.timestamp)
        
        self.timestamp = SongTimestamp()
        
    def read_message(self, msg):
        
        # Message has moved time forward.
        if msg.time != 0:
            
            if not self.push_primed:
                # Timestamp will push when we hit the next note.
                self.push_primed = True
                
                # Apply fleeting modifiers like toms, solo, and disco flip.
                if self.timestamp.chord:
                    self.timestamp.chord.apply_cymbals(not self.tom_flags[98], not self.tom_flags[99], not self.tom_flags[100])
                    
                    if self.disco_flip:
                        self.timestamp.chord.apply_disco_flip()
                self.timestamp.flag_solo = self.solo_active
                
                # The actual time stamp.
                self.timestamp.time = self.elapsed_time
                self.timestamp.measure = 1 + self.elapsed_measures
                self.timestamp.beat = self.elapsed_beats
                
                self.timestamp.tempo = self.tempo
                self.timestamp.ts_numerator = self.ts_numerator
                self.timestamp.ts_denominator = self.ts_denominator
                
                # Timestamps if hit as early/late as possible.
                # Will use the time signature at the timestamp - there will be slight error if the time signature changes too close to it.
                max_offset_seconds = 0.070
                ticks_per_measure = self.ticks_per_beat * self.ts_numerator * (4/self.ts_denominator)
                max_offset_measures = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / ticks_per_measure
                
                self.timestamp.measure_earlyhit = self.timestamp.measure - max_offset_measures
                self.timestamp.measure_latehit = self.timestamp.measure + max_offset_measures
                
                max_offset_beats = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / self.ticks_per_beat
                self.timestamp.beat_earlyhit = self.timestamp.beat - max_offset_beats
                self.timestamp.beat_latehit = self.timestamp.beat + max_offset_beats
                
            if self.fill_primed:
                self.timestamp.flag_activation = True
                self.timestamp.activation_fill_length_seconds = self.timestamp.time - self.fill_start_time
                self.timestamp.activation_fill_start_measure = self.fill_start_measure
                self.timestamp.activation_fill_start_beat = self.fill_start_beat
                self.fill_primed = False
                self.fill_start_time = None
                self.fill_start_measure = None
                self.fill_start_beat = None
                
            # Update time.
            ticks_per_measure = self.ticks_per_beat * self.ts_numerator * (4/self.ts_denominator)
            msg_measures = mido.second2tick(msg.time, self.ticks_per_beat, self.tempo) / ticks_per_measure
            
            self.elapsed_time += msg.time
            self.elapsed_measures += msg_measures
            self.elapsed_beats += mido.second2tick(msg.time, self.ticks_per_beat, self.tempo) / self.ticks_per_beat
        
        # Text marker to begin disco flip - interpret Red as YellowCym and YellowCym as Red
        if msg.type == 'text' and re.fullmatch(r'\[mix.3.drums\d?d\]', msg.text):
            self.disco_flip = True

        # Text marker to end disco flip
        if msg.type == 'text' and re.fullmatch(r'\[mix.3.drums\d?\]', msg.text):
            self.disco_flip = False
        
        # Current tempo
        if msg.type in ['set_tempo']:
            self.tempo = msg.tempo
            
        # Time signature
        if msg.type in ['time_signature']:
            self.ts_numerator = msg.numerator
            self.ts_denominator = msg.denominator
            
        if msg.type in ['note_on', 'note_off']:
            note_started = msg.type == 'note_on' and msg.velocity > 0
            note_ended = msg.type == 'note_off' or msg.type == 'note_on' and msg.velocity == 0
            
            match msg.note:
                
                # Fill - endpoint marks an activation chord
                case 120:
                    if note_started:
                        # The fill won't appear if it starts too close to gaining 50% sp (or else it'd risk being already in view)
                        self.fill_start_time = self.elapsed_time
                        self.fill_start_measure = 1 + self.elapsed_measures
                        self.fill_start_beat = self.elapsed_beats
                    if note_ended:
                        # When time advances, the current chord can be marked as an activation.
                        self.fill_primed = True
                        
                # SP phrase - endpoint modifies the current chord
                case 116: 
                    # Only bother with the ends of phrases
                    # To do: like fills, weirdness if sp marker ends at the same time as a new chord
                    if note_ended:
                        self.timestamp.flag_sp = True

                # Solo marker
                case 103:
                    if note_ended:
                        self.solo_active = False
                    if note_started:
                        self.solo_active = True
                    
                # Tom markers
                case 110 | 111 | 112:
                    if note_ended:
                        self.tom_flags[msg.note - 12] = False
                    if note_started:
                        self.tom_flags[msg.note - 12] = True
                        
                # Notes
                case 95 | 96 | 97 | 98 | 99 | 100:
                    if note_started:
                        if self.push_primed:
                            self.push_timestamp()

                        # Add to current chord - tom status will apply later
                        if not self.timestamp.chord:
                            self.timestamp.chord = hynote.Chord()
                        self.timestamp.chord.add_note(msg.note, msg.velocity)
        
    def parsefile(self, filename):
        assert(filename.endswith(".mid"))
        
        mid = mido.MidiFile(filename)
        self.ticks_per_beat = mid.ticks_per_beat

        # Remove other instruments while keeping events and any un-named or generic tracks
        for t in mid.tracks:
            is_nondrum_instrument = t.name.startswith("PART") and t.name != "PART DRUMS"
            is_harmony_track = t.name in ["HARM1", "HARM2", "HARM3"]
            if is_nondrum_instrument or is_harmony_track:
                t.clear()
                
        self.song = Song()
        
        for m in mid:
            self.read_message(m)
        self.push_timestamp()
        
        return self.song

class ChartSection:
    
    def __init__(self):
        self.name = None
        self.data = {}
        
    def report(self):
        print(self.name)
        print("{")
        for k in self.data:
            print(f"\t{k} = {self.data[k]}")
        print("}")


class ChartDataEntry:
    
    def __init__(self, keystr, valuestr):
        keystr = keystr.strip()
        valuestr = valuestr.strip()
        
        self.key_name = None
        self.key_tick = None
        
        self.property = None
        
        self.ts_numerator = None
        self.ts_denominator = None
        
        self.tempo_bpm = None
        
        self.textevent = None
        self.flagevent = None
        
        self.notevalue = None
        self.notelength = None
        
        self.phrasevalue = None
        self.phraselength = None
        
        self.solo_start = False
        self.solo_end = False
        
        self.discoflip_enable = False
        self.discoflip_disable = False
        self.discoflip_difficulty = None
        
        try:
            self.key_tick = int(keystr)
        except ValueError:
            self.key_name = keystr
        
        # Interpret valuestr
        tokens = valuestr.split()
        if not self.is_tick_data():
            # Single value for a named property (i.e. Song properties)
            try:
                self.property = int(valuestr)
            except ValueError:
                self.property = valuestr
        elif tokens[0] == "TS":
            # Time signature
            assert(2 <= len(tokens) <= 3)
            self.ts_numerator = int(tokens[1])
            self.ts_denominator = 2**int(tokens[2]) if len(tokens) == 3 else 4
        elif tokens[0] == "B":
            # BPM
            assert(len(tokens) == 2)
            self.tempo_bpm = int(tokens[1]) / 1000.0
        elif tokens[0] == "E":
            # Event
            lyric_events = ['lyric', 'phrase_start', 'phrase_end']
            anim_events = ['Default', 'crowd_normal', 'crowd_clap', 'crowd_noclap', 'crowd_intense', 'crowd_realtime', 'crowd_mellow', '[idle]', '[idle_realtime]', '[idle_intense]', '[map_HandMap_Default]', '[map_HandMap_DropD]', '[map_HandMap_DropD2]', '[map_StrumMap_Default]', '[map_StrumMap_Pick]', '[play]', '[intense]']
            structure_events = ['section',  'music_start', 'music_end', 'end']
            if tokens[1].strip('"') in lyric_events + anim_events + structure_events:
                # Various events we have no use for
                self.textevent = ' '.join(tokens[1:])
            elif tokens[1] == "solo":
                self.solo_start = True
            elif tokens[1] == "soloend":
                self.solo_end = True
            elif re.fullmatch(r'\[mix.\d.drums\d?\]', tokens[1]):
                self.discoflip_disable = True
                self.discoflip_difficulty = tokens[1][5]
            elif re.fullmatch(r'\[mix.\d.drums\d?d\]', tokens[1]):
                self.discoflip_enable = True
                self.discoflip_difficulty = tokens[1][5]
            else:
                raise NotImplementedError(f"Unknown Event data value in entry: {self.key()} = {valuestr}")
        elif tokens[0] == "N":
            # Note
            assert(len(tokens) == 3)
            self.notevalue = int(tokens[1])
            self.notelength = int(tokens[2])
        elif tokens[0] == "S":
            # Phrase (sp, activation fill, roll lane)
            assert(len(tokens) == 3)
            self.phrasevalue = int(tokens[1])
            self.phraselength = int(tokens[2])
        elif tokens[0] == "A":
            # Anchored BPM (ignored in game)
            pass
        else:
            # Ensures there isn't anything we're missing.
            raise NotImplementedError(f"Unknown data value in entry: {self.key()} = {valuestr}")

    def is_property(self):
        return self.property != None

    def is_tick_data(self):
        return self.key_tick != None

    def key(self):
        return self.key_tick if self.is_tick_data() else self.key_name
        

class ChartParser:
    
    def __init__(self):
        self.song = None
        self.sections = {}
        
        # Ticks per quarter note
        self.resolution = None
        
    # Loads the chartfile's sections from text form so they can be accessed easily.
    # Also converts from text values to more useful structures.
    # Also combines multi values within the same section.
    def load_sections(self, charttxt):
        wip_section = None
        block_depth = 0 # Should only be 0 or 1...
        for line in charttxt:
            if wip_section:
                if line.rstrip() == "{":
                    assert(block_depth == 0)
                    block_depth = 1
                elif line.rstrip() == "}":
                    assert(block_depth == 1)
                    block_depth = 0
                    self.sections[wip_section.name] = wip_section
                    wip_section = None
                else:
                    assert(block_depth == 1)
                    lhs = line.split('=')[0].strip()
                    rhs = line.split('=')[1].strip()
                    
                    dataentry = ChartDataEntry(lhs, rhs)
                    
                    if dataentry.key() in wip_section.data:
                        wip_section.data[dataentry.key()].append(dataentry)
                    else:
                        wip_section.data[dataentry.key()] = [dataentry]
            else:
                assert(block_depth == 0)
                # start a new section
                wip_section = ChartSection()
                wip_section.name = re.findall(r'\[.*\]', line)[0][1:-1]
            
            
    # Tick from start of song -> Time from start of song
    def tick_to_time(self, tick):
        current_time = 0.0
        current_tick = 0
        current_bpm = 120
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            
            if entry_tick >= tick:
                current_time += (tick - current_tick) / self.resolution / current_bpm * 60.0
                return current_time
            
            current_time += (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    current_bpm = entry.tempo_bpm
                    
        assert(tick > current_tick)
        current_time += (tick - current_tick) / self.resolution / current_bpm * 60.0
        return current_time
        
    # Time from start of song -> Measure from start of song (first measure is 1)
    def time_to_measure(self, time):
        current_time = 0.0
        current_tick = 0
        current_bpm = 120
        current_measure = 1
        current_ts_numerator = 4
        current_ts_denominator = 4
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            entry_time = current_time + (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            if entry_time >= time:
                current_measure += (time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
                return current_measure
            
            current_measure += (entry_time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
            current_time += (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    current_bpm = entry.tempo_bpm
                    
                if entry.ts_numerator != None:
                    current_ts_numerator = entry.ts_numerator
                
                if entry.ts_denominator != None:
                    current_ts_denominator = entry.ts_denominator
                    
        assert(time > current_time)
        current_measure += (time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
        return current_measure
            
    def meter_at_tick(self, tick):
        tempo = 120
        ts_numerator = 4
        ts_denominator = 4
        
        current_tick = 0
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            if entry_tick > tick:
                break
            
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    tempo = entry.tempo_bpm
                    
                if entry.ts_numerator != None:
                    ts_numerator = entry.ts_numerator
                
                if entry.ts_denominator != None:
                    ts_denominator = entry.ts_denominator
        
        
        return (tempo, ts_numerator, ts_denominator)
        
            
    def parsefile(self, filename):
        self.song = Song()
        
        with open(filename, mode='r') as charttxt:
            self.load_sections(charttxt)
            
        #for s in self.sections.values():
        #    s.report()
            
        self.resolution = int(self.sections["Song"].data["Resolution"][0].property)
        
        solo_on = False

        sp_phrase_endtick = None
        fill_endtick = None
        fill_starttime = None
        fill_startmeasure = None
        
        # Loop over the different ticks in the drum chart where things happen
        for tick,tick_entries in self.sections["ExpertDrums"].data.items():
            
            timestamp = SongTimestamp()
            timestamp.chord = hynote.Chord()
            
            timestamp.time = self.tick_to_time(tick)
            timestamp.measure = self.time_to_measure(timestamp.time)
            timestamp.measure_earlyhit = self.time_to_measure(timestamp.time - 0.070)
            timestamp.measure_latehit = self.time_to_measure(timestamp.time + 0.070)
            timestamp.beat = tick / self.resolution

            
            timestamp.flag_solo = solo_on
            
            # Loop over the things happening on this tick
            # Sort note values ascending to make the order of adding/modifying notes completely predictable
            for tick_entry in sorted(tick_entries, key=lambda e: e.notevalue if e.notevalue != None else -1):
                assert(tick_entry.is_tick_data())
                
                if tick_entry.solo_start == True:
                    assert(not solo_on)
                    solo_on = True
                    
                    # We passed the normal spot where solo_on is applied, but we want to include this tick's chord in the solo.
                    timestamp.flag_solo = True
                
                if tick_entry.solo_end == True:
                    assert(solo_on)
                    solo_on = False
                
                if tick_entry.notevalue != None:
                    match tick_entry.notevalue:
                        case 0:
                            # Kick note
                            timestamp.chord.Kick = hynote.ChordNote.NORMAL
                        case 1:
                            # Red note
                            timestamp.chord.Red = hynote.ChordNote.NORMAL
                        case 2:
                            # Yellow note
                            timestamp.chord.Yellow = hynote.ChordNote.NORMAL
                        case 3:
                            # Blue note
                            timestamp.chord.Blue = hynote.ChordNote.NORMAL
                        case 4:
                            # Green note
                            timestamp.chord.Green = hynote.ChordNote.NORMAL
                        case 32:
                            # 2x Kick note
                            timestamp.chord.Kick2x = hynote.ChordNote.NORMAL
                        case 34:
                            # Red accent
                            assert(timestamp.chord.Red == hynote.ChordNote.NORMAL)
                            timestamp.chord.Red = hynote.ChordNote.ACCENT
                        case 35:
                            # Yellow accent
                            assert(timestamp.chord.Yellow == hynote.ChordNote.NORMAL)
                            timestamp.chord.Yellow = hynote.ChordNote.ACCENT
                        case 36:
                            # Blue accent
                            assert(timestamp.chord.Blue == hynote.ChordNote.NORMAL)
                            timestamp.chord.Blue = hynote.ChordNote.ACCENT
                        case 37:
                            # Green accent
                            assert(timestamp.chord.Green == hynote.ChordNote.NORMAL)
                            timestamp.chord.Green = hynote.ChordNote.ACCENT
                        case 40:
                            # Red ghost
                            assert(timestamp.chord.Red == hynote.ChordNote.NORMAL)
                            timestamp.chord.Red = hynote.ChordNote.GHOST
                        case 41:
                            # Yellow ghost
                            assert(timestamp.chord.Yellow == hynote.ChordNote.NORMAL)
                            timestamp.chord.Yellow = hynote.ChordNote.GHOST
                        case 42:
                            # Blue ghost
                            assert(timestamp.chord.Blue == hynote.ChordNote.NORMAL)
                            timestamp.chord.Blue = hynote.ChordNote.GHOST
                        case 43:
                            # Green ghost
                            assert(timestamp.chord.Green == hynote.ChordNote.NORMAL)
                            timestamp.chord.Green = hynote.ChordNote.GHOST
                        case 66:
                            # Yellow cymbal
                            assert(timestamp.chord.Yellow != None)
                            timestamp.chord.Yellow = timestamp.chord.Yellow.to_cymbal()
                        case 67:
                            # Blue cymbal
                            assert(timestamp.chord.Blue != None)
                            timestamp.chord.Blue = timestamp.chord.Blue.to_cymbal()
                        case 68:
                            # Green cymbal
                            assert(timestamp.chord.Green != None)
                            timestamp.chord.Green = timestamp.chord.Green.to_cymbal()
                        case _:
                            raise NotImplementedError(f"Unknown note {tick_entry.notevalue}")
                
                if tick_entry.phrasevalue != None:
                    match tick_entry.phrasevalue:
                        case 2:
                            # SP phrase start
                            assert(sp_phrase_endtick == None)
                            sp_phrase_endtick = tick + tick_entry.phraselength
                        case 64:
                            # Fill / activation start
                            assert(fill_endtick == None and fill_starttime == None and fill_startmeasure == None)
                            fill_endtick = tick + tick_entry.phraselength
                            fill_starttime = timestamp.time #self.tick_to_time(tick)
                            fill_startmeasure = timestamp.measure #self.time_to_measure(fill_starttime)
                            fill_startbeat = timestamp.beat
                        case 65:
                            # Single roll marker
                            pass 
                        case 66:
                            # Double roll marker
                            pass
                        case _:
                            raise NotImplementedError(f"Unknown phrase {tick_entry.phrasevalue}, length {tick_entry.phraselength}")
                
            timestamp.tempo, timestamp.ts_numerator, timestamp.ts_denominator = self.meter_at_tick(tick)
            
            if len(self.song.sequence) > 0:
                timestamp.beat_earlyhit = timestamp.beat - (0.070 / 60 * self.song.sequence[-1].tempo)
            else:
                timestamp.beat_earlyhit = timestamp.beat - (0.070 / 60 * 120)
                
            timestamp.beat_latehit = timestamp.beat + (0.070 / 60 * timestamp.tempo)
            
            # to do this could be a great way to re-implement the retroactive behavior in the midi parser
            if sp_phrase_endtick != None and tick >= sp_phrase_endtick:
                self.song.sequence[-1].flag_sp = True
                sp_phrase_endtick = None
            
            if timestamp.chord.count() > 0:
                self.song.note_count += timestamp.chord.count()
                self.song.ghost_count += timestamp.chord.ghost_count()
                self.song.accent_count += timestamp.chord.accent_count()
                if timestamp.flag_solo:
                    self.song.solo_note_count += timestamp.chord.count()
 
                self.song.sequence.append(timestamp)
                
            # Fills apply to the chord on the end tick, if present, so this check happens after adding the timestamp.
            if fill_endtick != None and tick >= fill_endtick:
                self.song.sequence[-1].flag_activation = True
                self.song.sequence[-1].activation_fill_length_seconds = self.tick_to_time(tick) - fill_starttime
                self.song.sequence[-1].activation_fill_start_measure = fill_startmeasure
                self.song.sequence[-1].activation_fill_start_beat = fill_startbeat
                fill_endtick = None
                fill_starttime = None
                fill_startmeasure = None
                fill_startbeat = None
        
        return self.song
        


        