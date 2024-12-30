from functools import total_ordering
import pathlib


"""Semantic version number for Hydra.
    
Major version update: Incompatible changes or big milestones.
Minor version update: Changes that are expected to affect paths/scores.
Patch version update: UI or other cosmetic changes.

Records with an old major or minor version will be considered stale.

"""
HYDRA_VERSION = (0,0,1)


"""Static paths and files"""

ROOTPATH = pathlib.Path(__file__).resolve().parent.parent
INIPATH = ROOTPATH / "hyapp.ini"
DBPATH = ROOTPATH / "hydra.db"
ICOPATH = ROOTPATH / "resource" / "Icon.ico"
FONTPATH_ANTQ = ROOTPATH / "resource" / "ShipporiAntiqueB1-Regular.ttf"
ICOPATH_NOTE = ROOTPATH / "resource" / "uicon_note_32.png"
ICOPATH_SNAKE = ROOTPATH / "resource" / "uicon_snake_32.png"
BOOKPATH = ROOTPATH / "records.json"

TABLE_COL_INFO = {
    'hyhash': (0, "Hydra Hash"),
    'name': (1, "Title"),
    'artist': (2, "Artist"),
    'charter': (3, "Charter"),
    'path': (4, "File Path"),
    'folder': (5, "Folder"),
}


class ChartFileError(Exception):
    """Just a custom error for a chart file that doesn't work."""
    pass
    

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
        self.measure_percent = 0.0
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
        
        self.measure_beats_ticks[0] += ticks_to_advance // current_ticks_per_m
        ticks_to_advance %= current_ticks_per_m
        
        # Alternate remainder: percentage
        self.measure_percent = ticks_to_advance / current_ticks_per_m
        
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
        strs = [str(v) for v in self.measure_beats_ticks]
        return f"m{'.'.join(strs)}"
    
    def plusmeasure(self, add_measures, song):
        """Returns a new Timecode offset by the given number of measures.
        
        Partial measures will work by percentage rather than by
        number of beats or ticks. For example, "22 and a quarter measure"
        plus 2 measures will always equal "24 and a quarter measure" no
        matter the time signature.
        
        """
        t = self.measure_beats_ticks[0] + self.measure_percent + add_measures
        assert(t >= 0)
        target_m = int(t)
        targetpartial = t % 1
        
        keys = sorted(song.measure_map.keys())
        assert(keys[0] == 0)
        ticks_per_m = song.measure_map[0]
        ticks_to_advance = 0
        counted_m = 0
        countedticks = 0
        
        for tick_key in keys[1:]:
            available_ticks = tick_key - countedticks
        
            while available_ticks >= ticks_per_m and counted_m < target_m:
                counted_m += 1
                countedticks += ticks_per_m
                available_ticks -= ticks_per_m
        
            if counted_m == target_m:
                break
        
            ticks_per_m = song.measure_map[tick_key]
        
        while counted_m < target_m:
            counted_m += 1
            countedticks += ticks_per_m
            
        partial = int(targetpartial * ticks_per_m)
        return Timecode(countedticks + partial, song)
