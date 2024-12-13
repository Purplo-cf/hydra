from functools import total_ordering

# A point in time, available in multiple song-y units.
# Based in integers and tick remainders for complete accuracy. (Except for ms)
# Never worry about tick resolution or beats per measure again.
# to do: The resolution, tempo map, and measure map are required for conversions, yet feel out of place in the struct
@total_ordering
class Timecode:
    
    def __init__(self, resolution, measure_map, tempo_map, ticks):
        self.resolution = resolution
        self.measure_map = measure_map
        self.tempo_map = tempo_map
        self.ticks = ticks
        
        # Cached properties
        self._beats = None
        self._measures = None
        self._ms = None
        
    def __eq__(self, other):
        return self.ticks == other.ticks
        
    def __lt__(self, other):
        return self.ticks < other.ticks
        
    def __hash__(self):
        return self.ticks
        
    def __repr__(self):
        return str(self.ticks)
        
    def measurestr(self):
        return f"m{self.measures()[0]}{f" + {round(self.measures()[1] / self.resolution, 2)} beats" if self.measures()[1] > 0 else ""}"
        
    def beats(self):
        if self._beats != None:
            return self._beats
        
        self._beats = (1 + self.ticks // self.resolution, self.ticks % self.resolution)
        return self._beats
        
    def measures(self):
        if self._measures != None:
            return self._measures
            
        
        counted_ticks = 0
        current_ticks_per_measure = None
        counted_measures = 0
        leftover_ticks = 0
        for tick_key in sorted(self.measure_map.keys()):
            if tick_key <= counted_ticks:
                current_ticks_per_measure = self.measure_map[tick_key]
                continue
            
            available_ticks = leftover_ticks + min(tick_key, self.ticks) - counted_ticks
            
            
            while available_ticks >= current_ticks_per_measure:
                available_ticks -= current_ticks_per_measure
                counted_measures += 1
            
            leftover_ticks = available_ticks
            counted_ticks = min(tick_key, self.ticks)
            
            
            
            if counted_ticks == self.ticks:
                break
                
            current_ticks_per_measure = self.measure_map[tick_key]
            
            
        # One last update with the (unlimited) time after the last meter change
        available_ticks = leftover_ticks + self.ticks - counted_ticks
        
        counted_measures += available_ticks // current_ticks_per_measure
        leftover_ticks = available_ticks % current_ticks_per_measure
            
        self._measures = (1 + counted_measures, leftover_ticks)
        return self._measures
        
    def ms(self):
        if self._ms != None:
            return self._ms
            
        counted_ticks = 0
        current_bpm = None
        counted_ms = 0
        for tick_key in sorted(self.tempo_map.keys()):
            if tick_key <= counted_ticks:
                current_bpm = self.tempo_map[tick_key]
                continue
        
            available_ticks = min(tick_key, self.ticks) - counted_ticks
            counted_ms += available_ticks / self.resolution / current_bpm * 60000
            counted_ticks += available_ticks
            
            if counted_ticks == self.ticks:
                break
            
            current_bpm = self.tempo_map[tick_key]
        
        
        
        # One last update with the (unlimited) time after the last bpm change
        available_ticks = self.ticks - counted_ticks
        counted_ms += available_ticks / self.resolution / current_bpm * 60000

        self._ms = counted_ms
        
        if self._ms == 0:
            print("Calculated ms = 0!!!")
            print(f"\tTempo map:")
            for k,v in self.tempo_map.items():
                print(f"\t\t{k}: {v}")
        
        return self._ms
        
    # Non-mutating add
    def plusmeasure(self, wholemeasures_to_add):
        resolved_ticks = self.ticks
        current_ticks_per_measure = None
        added_ticks = 0
        added_measures = 0
        rollover_ticks = 0
        # On the one hand this looks kinda crazy,
        # on the other hand converting to/from measures really is a pain
        for tick_key in sorted(self.measure_map.keys()):
            if tick_key <= resolved_ticks:
                current_ticks_per_measure = self.measure_map[tick_key]
                continue
                
            available_ticks = tick_key - resolved_ticks + rollover_ticks
            
            # TO DO: rollover ticks are bugged, they would not be counted as being in their old time signature :(
            # possible alternate algorithm: round down the partial measure, do the main alg to advance the desired measures,
            # then add back the partial measure.
            # current_ticks_per_measure is highly divisible because it's 4, 3.5, 3.75, etc. * the resolution.
            
            while available_ticks >= current_ticks_per_measure and added_measures < wholemeasures_to_add:
                available_ticks -= current_ticks_per_measure
                added_ticks += current_ticks_per_measure
                added_measures += 1
            
            if added_measures == wholemeasures_to_add:
                break
            
            rollover_ticks = available_ticks
            resolved_ticks = tick_key
            current_ticks_per_measure = self.measure_map[tick_key]
            
        # One last update with the (unlimited) time after the last meter change
        added_ticks += current_ticks_per_measure * (wholemeasures_to_add - added_measures)
        
        return Timecode(self.resolution, self.measure_map, self.tempo_map, self.ticks + added_ticks)
        
    # Positive if ts is later than self
    def offset_ms(self, ts):
        return ts.ms() - self.ms()
        