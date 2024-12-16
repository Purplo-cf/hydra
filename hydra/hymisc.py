from functools import total_ordering


@total_ordering
class Timecode:
    """A point in time in a song, in multiple representations.
    
    The absolute way to measure time in songs is with ticks, but some contexts
    want to work with measures, beats, or milliseconds.
    
    Timecodes are created with a tick value and song context; the rest of the
    values are derived.
    
    All derived values are, like ticks, fully precise integers; except for
    milliseconds, which is a float value.
    
    """
    def __init__(self, ticks, song):
        # Fundamental value
        self.ticks = ticks
        
        # Derived values
        self.measure_beats_ticks = [0, 0, 0]
        self.ms = 0.0
        
        self._init_mbt(song)
        self._init_ms(song)
    
    def _init_mbt(self, song):
        """Iterate over a song's meter to convert ticks to measures.
            
        After all whole measures are counted, whole beats are counted.
        The remainder after measures and beats stays as ticks.
            
        """
        assert(song.measure_map)
        keys = sorted(song.measure_map.keys())
        assert(keys[0] == 0)
        at_tick = 0
        current_ticks_per_m = song.measure_map[0]
        ticks_to_advance = 0
        for tick_key in keys[1:]:            
            ticks_to_advance = min(tick_key - at_tick, self.ticks - at_tick)
            
            # Apply measures
            whole_measures = ticks_to_advance // current_ticks_per_m
            ticks_to_advance %= current_ticks_per_m
            
            self.measure_beats_ticks[0] += whole_measures
            at_tick += whole_measures * current_ticks_per_m
            
            
            if at_tick + ticks_to_advance == self.ticks:
                break
            else:
                assert(ticks_to_advance == 0)
        
            current_ticks_per_m = song.measure_map[tick_key]
            
            
        ticks_to_advance = self.ticks - at_tick
        
        # Remainder: beats, then ticks
        self.measure_beats_ticks[1] = ticks_to_advance // song.tick_resolution
        self.measure_beats_ticks[2] = ticks_to_advance % song.tick_resolution
        
        self.measure_beats_ticks = tuple(self.measure_beats_ticks)
    
    def _init_ms(self, song):
        """Iterate over a song's tempo map to derive milliseconds."""
        assert(song.tempo_map)
        assert(song.tick_resolution)
        keys = sorted(song.tempo_map.keys())
        assert(keys[0] == 0)
        
        def to_tps(bpm):
            nonlocal song
            return bpm * song.tick_resolution / 60
        
        at_tick = 0
        ticks_per_sec = to_tps(song.tempo_map[0])
        ticks_to_advance = 0
        for tick_key in keys[1:]:
            ticks_to_advance = min(tick_key - at_tick, self.ticks - at_tick)
            
            # Apply ms
            self.ms += ticks_to_advance / ticks_per_sec * 1000
            at_tick += ticks_to_advance
            
            if at_tick == self.ticks:
                break
                
            ticks_per_sec = to_tps(song.tempo_map[tick_key])
            
        ticks_to_advance = self.ticks - at_tick
        self.ms += ticks_to_advance / ticks_per_sec * 1000
        
    
    def __eq__(self, other):
        return self.ticks == other.ticks
    
    def __lt__(self, other):
        return self.ticks < other.ticks
    
    def __hash__(self):
        return self.ticks
    
    def __repr__(self):
        return str(self.ticks)
    
    def measurestr(self):
        return f"m{'.'.join(self.measure_beats_ticks)}"
    
    # Non-mutating add
    def plusmeasure(self, wholemeasures_to_add, song):
        resolved_ticks = self.ticks
        current_ticks_per_measure = None
        added_ticks = 0
        added_measures = 0
        rollover_ticks = 0
        # On the one hand this looks kinda crazy,
        # on the other hand converting to/from measures really is a pain
        for tick_key in sorted(song.measure_map.keys()):
            if tick_key <= resolved_ticks:
                current_ticks_per_measure = song.measure_map[tick_key]
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
            current_ticks_per_measure = song.measure_map[tick_key]
            
        # One last update with the (unlimited) time after the last meter change
        added_ticks += current_ticks_per_measure * (wholemeasures_to_add - added_measures)
        
        return Timecode(self.ticks + added_ticks, song)
