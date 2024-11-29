import shutil
import copy
from enum import Enum
import math
import json

from . import hynote

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
            assert(timestamp.activation_fill_length_seconds != None)
            
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




