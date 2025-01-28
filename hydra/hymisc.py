from functools import total_ordering
import pathlib
import sys

"""Semantic version number for Hydra.
    
Major version update: Incompatible changes or big milestones.
Minor version update: Changes that are expected to affect paths/scores.
Patch version update: UI or other cosmetic changes.

Records with an old major version will be wiped without trying to read them.
Records with an old minor version will be marked stale, but will work normally.

"""
HYDRA_VERSION = (0,1,1)


"""Static paths and files"""

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    ROOTPATH = pathlib.Path(sys._MEIPASS).resolve()
else:
    ROOTPATH = pathlib.Path(__file__).resolve().parent.parent
INIPATH = ROOTPATH / "hyapp.ini"
DBPATH = ROOTPATH / "hyapp.db"
FONTPATH_ANTQ = ROOTPATH / "resource" / "ShipporiAntiqueB1-Regular.ttf"
FONTPATH_MONO = ROOTPATH / "resource" / "CourierPrime-Regular.ttf"
BOOKPATH = ROOTPATH / "records.json"

ICOPATH_APP = ROOTPATH / "resource" / "icon_app.ico"
ICOPATH_RECORD = ROOTPATH / "resource" / "icon_record_32.png"
ICOPATH_STAR = ROOTPATH / "resource" / "icon_star_32.png"
ICOPATH_PENCIL = ROOTPATH / "resource" / "icon_pencil_32.png"
ICOPATH_HASH = ROOTPATH / "resource" / "icon_hash_32.png"


"""Associated info: db column name, db index, and display name."""
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
        self.measures_decimal = 0.0
        self.ms = 0.0
        
        if song is not None:
            self._init_mbt(song)
            self._init_ms(song)
    
    def _init_mbt(self, song):
        """Iterate over a song's meter to derive the measure/beat/tick position
        that corresponds to self.ticks.
        
        After all whole measures are counted, whole beats are counted.
        The remainder after measures and beats stays as ticks.
            
        """
        keys = sorted(song.tpm_changes.keys())
        handled_ticks = 0
        current_tpm = song.tpm_changes[0]
        
        # Advance through the song in sections marked by each tpm change
        for tick_key in keys[1:]:
            # Advance to whichever comes first, the next section or our tick
            ticks_to_advance = min(
                tick_key - handled_ticks,
                self.ticks - handled_ticks
            )
            
            # Count whole measures out of the ticks that are being advanced
            whole_measures = ticks_to_advance // current_tpm
            ticks_to_advance %= current_tpm
            self.measure_beats_ticks[0] += whole_measures
            handled_ticks += whole_measures * current_tpm
            
            # If our tick is what's next (i.e. no more sections are needed)
            if handled_ticks + ticks_to_advance == self.ticks:
                break
        
            # Set new tpm for the next section
            current_tpm = song.tpm_changes[tick_key]
        
        # Count past the last tpm mark if needed
        ticks_to_advance = self.ticks - handled_ticks
        
        # Count whole measures
        self.measure_beats_ticks[0] += ticks_to_advance // current_tpm
        ticks_to_advance %= current_tpm
        
        # Less than 1 measure remains. Count whole beats
        self.measure_beats_ticks[1] = ticks_to_advance // song.tick_resolution
        # Any ticks left over (less than 1 beat) will just be the remainder
        self.measure_beats_ticks[2] = ticks_to_advance % song.tick_resolution
        
        # Alternate way to express being partway into a measure
        partial_m = ticks_to_advance / current_tpm
        self.measures_decimal = self.measure_beats_ticks[0] + partial_m
        
        # Finalize
        self.measure_beats_ticks = tuple(self.measure_beats_ticks)
    
    def _init_ms(self, song):
        """Iterate over a song's tempo map to derive milliseconds."""
        keys = sorted(song.bpm_changes.keys())
        
        def to_tps(bpm):
            nonlocal song
            return bpm * song.tick_resolution / 60
        
        handled_ticks = 0
        tps = to_tps(song.bpm_changes[0])
        # Advance through the song in sections marked by each bpm change
        for tick_key in keys[1:]:
            # Advance to whichever comes first, the next section or our tick
            ticks_to_advance = min(
                tick_key - handled_ticks,
                self.ticks - handled_ticks
            )
            
            # Apply ms
            self.ms += ticks_to_advance / tps * 1000
            handled_ticks += ticks_to_advance
            
            # If we finished, jump out
            if handled_ticks == self.ticks:
                break
                
            tps = to_tps(song.bpm_changes[tick_key])
            
        # Count ms past the last bpm mark if needed
        ticks_to_advance = self.ticks - handled_ticks
        self.ms += ticks_to_advance / tps * 1000
    
    def __eq__(self, other):
        return self.ticks == other.ticks
    
    def __lt__(self, other):
        return self.ticks < other.ticks
    
    def __hash__(self):
        return self.ticks
    
    def __repr__(self):
        return str(self.ticks)
        
    def is_measure_start(self):
        return self.measure_beats_ticks[1] == self.measure_beats_ticks[2] == 0 
    
    def measurestr(self, fixed_width=False):
        m, b, t = self.measure_beats_ticks
        if fixed_width:
            return f"{f"m{m+1}": >5}.{b + 1}.{t: <3}"
        else:
            return f"m{m + 1}.{b + 1}.{t}"        
    
    def plusmeasure(self, add_measures, song):
        """Returns a new Timecode offset by the given number of measures.
        
        Partial measures will work by percentage rather than by
        number of beats or ticks. For example, "22 and a quarter measure"
        plus 2 measures will always equal "24 and a quarter measure" no
        matter the time signature.
        
        """
        # Add the given measures (working in measures)
        m_decimal = self.measures_decimal + add_measures
        target_m = int(m_decimal)
        targetpartial = m_decimal % 1
        
        keys = sorted(song.tpm_changes.keys())
        handled_ticks = 0
        current_tpm = song.tpm_changes[0]
        counted_m = 0
        
        # Advance through the song in sections marked by each tpm change
        for tick_key in keys[1:]:
            # Count of ticks within this section
            ticks_to_advance = tick_key - handled_ticks
        
            # Count measures in this section (but stop at target measure)
            while ticks_to_advance >= current_tpm and counted_m < target_m:
                counted_m += 1
                handled_ticks += current_tpm
                ticks_to_advance -= current_tpm
        
            # If we hit the target measure, jump out
            if counted_m == target_m:
                # But if it was right on the section edge, get the next tpm
                if ticks_to_advance == 0:
                    current_tpm = song.tpm_changes[tick_key]
                break
        
            current_tpm = song.tpm_changes[tick_key]
        
        # Count measures past the last tpm if needed
        while counted_m < target_m:
            counted_m += 1
            handled_ticks += current_tpm
            
        # Now that we have the right tpm, convert the partial measure to ticks
        partial = int(targetpartial * current_tpm)
        return Timecode(handled_ticks + partial, song)
