import json
from enum import Enum

from . import hymisc


def json_save(obj):
    """Object --> dict conversion."""
    if isinstance(obj, HydraRecord):
        return {
            '__obj__': 'record',
            
            'hyversion': obj.hyversion,
            'paths': obj.paths,
        }
    
    if isinstance(obj, Path):
        return {
            '__obj__': 'path',
        
            'multsqueezes': obj.multsqueezes,
            'activations': obj.activations,
            
            'score_base': obj.score_base,
            'score_combo': obj.score_combo,
            'score_sp': obj.score_sp,
            'score_solo': obj.score_solo,
            'score_accents': obj.score_accents,
            'score_ghosts': obj.score_ghosts,
            
            'ref_totalscore': obj.totalscore(),
        }
    
    if isinstance(obj, MultSqueeze):
        return {
            '__obj__': 'msq',
        
            'multiplier': obj.multiplier,
            'chord': obj.chord,
            'squeezecount': obj.squeezecount,
            'points': obj.points,
        }
    
    if isinstance(obj, Activation):
        return {
            '__obj__': 'activation',
        
            'skips': obj.skips,
            'timecode': obj.timecode,
            'chord': obj.chord,
            'sp_meter': obj.sp_meter,
            
            'frontend': obj.frontend,
            'backends': obj.backends,
            
            'sqinouts': obj.sqinouts,
            
            'e_offset': obj.e_offset,
        }
    
    if isinstance(obj, FrontendSqueeze):
        return {
            '__obj__': 'fsq',
        
            'chord': obj.chord,
            'points': obj.points,
        }
    
    if isinstance(obj, BackendSqueeze):
        return {
            '__obj__': 'bsq',
        
            'timecode': obj.timecode,
            'chord': obj.chord,
            'points': obj.points,
            'sqout_points': obj.sqout_points,
            'is_sp': obj.is_sp,
            'offset_ms': obj.offset_ms,
    }
    
    if isinstance(obj, Chord):
        return {
            '__obj__': 'chord',
        
            'kick': obj.notemap[NoteColor.KICK],
            'red': obj.notemap[NoteColor.RED],
            'yellow': obj.notemap[NoteColor.YELLOW],
            'blue': obj.notemap[NoteColor.BLUE],
            'green': obj.notemap[NoteColor.GREEN],
        }
    
    if isinstance(obj, ChordNote):
        return {
            '__obj__': 'note',
        
            'dynamic': obj.dynamictype,
            'cymbal': obj.cymbaltype,
            'is_2x': obj.is2x,
        }
    
    if isinstance(obj, NoteCymbalType):
        return {
            NoteCymbalType.NORMAL: 'normal',
            NoteCymbalType.CYMBAL: 'cymbal',
        }[obj]
    
    if isinstance(obj, NoteDynamicType):
        return {
            NoteDynamicType.NORMAL: 'normal',
            NoteDynamicType.GHOST: 'ghost',
            NoteDynamicType.ACCENT: 'accent',
        }[obj]
    
    if isinstance(obj, hymisc.Timecode):
        return {
            '__obj__': 'timecode',
            
            'tick': obj.ticks,
            
            # Derived values, but if we're loading timestamps,
            # we can't re-derive them without analyzing the song again.
            'mbt': obj.measure_beats_ticks,
            'm_decimal': obj.measures_decimal,
            'ms': obj.ms,
                        
            'ref_measure': obj.measurestr(),
        }
    
    raise TypeError(f"Unhanded type: {type(obj)}")
    
def json_load(_dict):
    """JSON has loaded a dict; try to fit it to Hydra data types.
    
    Hydra data types are saved with an __obj__ value to facilitate this.
    
    The top level maps hyhash keys to a 'records' map with keys based on
    difficulty/pro/2x. Everything after that is a hydata object.
    """
    try:
        obj_code = _dict['__obj__']
    except KeyError:
        # Not one of our objects, just a dict
        return _dict
    
    if obj_code == 'record':
        o = HydraRecord()
        o.hyversion = tuple(_dict['hyversion'])
        
        if not o.is_version_compatible():
            return o
        
        o.paths = _dict['paths']
        
        return o
    
    try:
        if obj_code == 'path':
            o = Path()
            o.multsqueezes = _dict['multsqueezes']
            o.activations = _dict['activations']
            
            o.score_base = _dict['score_base']
            o.score_combo = _dict['score_combo']
            o.score_sp = _dict['score_sp']
            o.score_solo = _dict['score_solo']
            o.score_accents = _dict['score_accents']
            o.score_ghosts = _dict['score_ghosts']
            
            return o
        
        if obj_code == 'msq':
            o = MultSqueeze()
            o.multiplier = _dict['multiplier']
            o.chord = _dict['chord']
            o.squeezecount = _dict['squeezecount']
            o.points = _dict['points']
            
            return o
        
        if obj_code == 'activation':
            o = Activation()
            o.skips = _dict['skips']
            o.timecode = _dict['timecode']
            o.chord = _dict['chord']
            o.sp_meter = _dict['sp_meter']
            
            o.frontend = _dict['frontend']
            o.backends = _dict['backends']
            
            o.sqinouts = _dict['sqinouts']
            
            o.e_offset = _dict['e_offset']
        
            return o
        
        if obj_code == 'fsq':
            o = FrontendSqueeze(_dict['chord'], _dict['points'])

            return o
        
        if obj_code == 'bsq':
            o = BackendSqueeze(
                _dict['timecode'],
                _dict['chord'],
                _dict['points'],
                _dict['sqout_points'],
                _dict['is_sp'],
            )
            o.offset_ms = _dict['offset_ms']
            
            return o
        
        if obj_code == 'chord':
            o = Chord()
            o.notemap = {
                NoteColor.KICK: _dict['kick'],
                NoteColor.RED: _dict['red'],
                NoteColor.YELLOW: _dict['yellow'],
                NoteColor.BLUE: _dict['blue'],
                NoteColor.GREEN: _dict['green'],
            }
            
            for c, note in o.notemap.items():
                if note:
                    note.colortype = c
            
            return o
        
        if obj_code == 'note':
            o = ChordNote()
            
            o.cymbaltype = {
                'normal': NoteCymbalType.NORMAL,
                'cymbal': NoteCymbalType.CYMBAL,
            }[_dict['cymbal']]
            
            o.dynamictype = {
                'normal': NoteDynamicType.NORMAL,
                'ghost': NoteDynamicType.GHOST,
                'accent': NoteDynamicType.ACCENT,
            }[_dict['dynamic']]
            
            o.is2x = _dict['is_2x']
            
            return o
        
        if obj_code == 'timecode':
            o = hymisc.Timecode(_dict['tick'], None)
            o.measure_beats_ticks = _dict['mbt']
            o.measures_decimal = _dict['m_decimal']
            o.ms = _dict['ms']
            
            return o
    except KeyError:
        return "<Invalid object>"
        
    return "<Unrecognized object>"


class HydraRecord:
    """A "printout" representing one analyzed chart.
    
    Each unique chart file (hash) can have 1 unique HydraRecord per combination
    of difficulty, pro/non-pro, and 2x/1x bass (chartmode).
    
    Multiple paths for a given chart are grouped within the same hydata.
    
    A hydata stores the version of Hydra that created it.
    
    """
    def __init__(self):   
        # Made by this version of Hydra.
        self.hyversion = hymisc.HYDRA_VERSION
        
        # Path results.
        self.paths = []

    def __eq__(self, other):
        if len(self.paths) != len(other.paths):
            return False
        
        for i in range(len(self.paths)):
            if self.paths[i] != other.paths[i]:
                return False
        
        return True
    
    def is_version_compatible(self):
        return self.hyversion[:2] == hymisc.HYDRA_VERSION[:2]


class Path:
    
    def __init__(self):
        # Path characteristics
        self.multsqueezes = []
        self.activations = []
        
        # Score breakdown categories from Clone Hero
        self.score_base = 0
        self.score_combo = 0
        self.score_sp = 0
        self.score_solo = 0 
        self.score_accents = 0
        self.score_ghosts = 0
   
    def __eq__(self, other):
        for listattr in ['multsqueezes', 'activations']:
            a = getattr(self, listattr)
            b = getattr(other, listattr)
            if len(a) != len(b):
                return False
            for i in range(len(a)):
                if a[i] != b[i]:
                    return False
        
        for attr in ['score_base', 'score_combo', 'score_sp', 'score_solo', 'score_accents', 'score_ghosts']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True
   
    def totalscore(self):
        return (
            self.score_base + self.score_combo + self.score_sp
            + self.score_solo + self.score_accents + self.score_ghosts
        )
    
    def pathstring(self):
        if self.activations:
            return ' '.join([str(a.notationstr()) for a in self.activations])
        else:
            return "(No activations.)"

    def copy(self):
        c = Path()
        
        # New list moving forward, shared previous activations
        c.activations = [a for a in self.activations]
        
        # Except for the latest activation 
        if c.activations:
            c.activations[-1] = c.activations[-1].copy()
        
        c.multsqueezes = self.multsqueezes
        
        c.score_base = self.score_base
        c.score_combo = self.score_combo
        c.score_sp = self.score_sp
        c.score_solo = self.score_solo
        c.score_accents = self.score_accents
        c.score_ghosts = self.score_ghosts
        
        return c

class Activation:
    
    def __init__(self):
        self.skips = None
        self.timecode = None
        self.chord = None
        self.sp_meter = None
        
        self.frontend = None
        self.backends = []
        
        self.sqinouts = []
        
        self.e_offset = None
    
    def __eq__(self, other):
        for listattr in ['backends', 'sqinouts']:
            a = getattr(self, listattr)
            b = getattr(other, listattr)
            if len(a) != len(b):
                return False
            for i in range(len(a)):
                if a[i] != b[i]:
                    return False
        
        for attr in ['skips', 'timecode', 'chord', 'sp_meter', 'frontend', 'e_offset']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True
        
    def notationstr(self):
        e = 'E' if self.is_e_critical() else ''
        return f"{e}{self.skips}{''.join(self.sqinouts)}"
    
    def is_e_critical(self):
        return self.e_offset < 70 
        
    def copy(self):
        c = Activation()
        
        c.skips = self.skips
        c.timecode = self.timecode
        c.chord = self.chord
        c.sp_meter = self.sp_meter
        
        c.frontend = self.frontend
        c.backends = self.backends
        
        c.sqinouts = [s for s in self.sqinouts]
        
        c.e_offset = self.e_offset
        
        return c


class MultSqueeze:
    """Multiplier squeeze: When the combo multiplier goes up partway through a
    chord, and that chord has notes with different values, the higher-value
    notes should be hit on the higher combo multiplier.
    
    This usually results in +15s for cymbal squeezes or +50s for dynamic
    squeezes.
    """
    def __init__(self):
        self.multiplier = None
        self.chord = None
        self.squeezecount = None
        self.points = None
        
    def __eq__(self, other):
        for attr in ['multiplier', 'chord', 'squeezecount', 'points']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True

    
    def notationstr(self):
        return f"{self.multiplier}x"


class FrontendSqueeze:
    
    def __init__(self, chord, points):
        self.chord = chord
        self.points = points
        
    def __eq__(self, other):
        for attr in ['chord', 'points']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True
        


class BackendSqueeze:
    def __init__(self, timecode, chord, points, sqout_points, is_sp):
        self.timecode = timecode
        self.chord = chord
        self.points = points
        self.sqout_points = sqout_points
        self.is_sp = is_sp

        self.offset_ms = None
        
    def __eq__(self, other):
        for attr in ['timecode', 'chord', 'points', 'sqout_points', 'is_sp', 'offset_ms']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True
        
    def ratingstr(self):
        """Hydra ratings for how hard the squeeze's timing is."""
        thresholds = [
            (-140, "Free"),
            (-105, "Free"),
            (-70, "Free"),
            (-35, "Trivial"),
            (-2, "Easy"),
            (2, "Normal"),
            (35, "Hard"),
            (70, "Extreme"),
            (105, "Insane"),
            (140, "Insane+"),
        ]
        max_rating = "Impossible"
        
        for threshold, rating in thresholds:
            if self.offset_ms < threshold:
                return rating
        
        return max_rating


class NoteColor(Enum):
    """Representation of a note color.
    
    Note colors actually determine what types of notes are possible.
    Kick notes only have normal notes and the special 2x kick note.
    Red notes don't have cymbals.
    
    """
    KICK = 1
    RED = 2
    YELLOW = 3
    BLUE = 4
    GREEN = 5
    
    def allows_cymbals(self):
        return self in [
            NoteColor.YELLOW,
            NoteColor.BLUE,
            NoteColor.GREEN
        ]
            
    
    def allows_dynamics(self):
        return self in [
            NoteColor.RED,
            NoteColor.YELLOW,
            NoteColor.BLUE,
            NoteColor.GREEN
        ]
    
    def __str__(self):
        match self:
            case NoteColor.KICK:
                return "Kick"
            case NoteColor.RED:
                return "Red"
            case NoteColor.YELLOW:
                return "Yellow"
            case NoteColor.BLUE:
                return "Blue"
            case NoteColor.GREEN:
                return "Green"
    
    def notationstr(self):
        match self:
            case NoteColor.KICK:
                return "K"
            case NoteColor.RED:
                return "R"
            case NoteColor.YELLOW:
                return "Y"
            case NoteColor.BLUE:
                return "B"
            case NoteColor.GREEN:
                return "G"


class NoteDynamicType(Enum):
    """Representation of a note's dynamic type."""
    NORMAL = 1
    GHOST = 2
    ACCENT = 3


class NoteCymbalType(Enum):
    """Representation of a note's dynamic type.
    
    Normal = Toms / Snare / Kick.
    
    """
    NORMAL = 1
    CYMBAL = 2

    def flip(self):
        if self == NoteCymbalType.CYMBAL:
            return NoteCymbalType.NORMAL
        else:
            return NoteCymbalType.CYMBAL

class ChordNote:
    """Representation of a note from a chart."""

    def __init__(self):
        self.colortype = None
        self.dynamictype = NoteDynamicType.NORMAL
        self.cymbaltype = NoteCymbalType.NORMAL
        self.is2x = False
    
    def __eq__(self, other):
        for attr in ['colortype', 'dynamictype', 'cymbaltype', 'is2x']:
            if getattr(self, attr) != getattr(other, attr):
                return False
                
        return True
    
    def __str__(self):
        if self.colortype.allows_cymbals():
            cym = "Cym" if self.cymbaltype == NoteCymbalType.CYMBAL else "Tom"
        else:
            cym = ""
            
        if self.colortype.allows_dynamics():
            match self.dynamictype:
                case NoteDynamicType.NORMAL:
                    mod = ""
                case NoteDynamicType.GHOST:
                    mod = " (Ghost)"
                case NoteDynamicType.ACCENT:
                    mod = " (Accent)"
        elif self.is2x:
            mod = " (2x)"
        else:
            mod = ""
            
        return f"{self.colortype}{cym}{mod}"
    
    def basescore(self):
        points = 65 if self.is_cymbal() else 50

        if self.is_dynamic():
            points *= 2
        
        return points
    
    def is_dynamic(self):
        return self.dynamictype != NoteDynamicType.NORMAL
    
    def is_accent(self):
        return self.dynamictype == NoteDynamicType.ACCENT
    
    def is_ghost(self):
        return self.dynamictype == NoteDynamicType.GHOST
    
    def is_cymbal(self):
        return self.cymbaltype == NoteCymbalType.CYMBAL


class Chord:
    """Representation of a chord which has 1 note (or None) for each color."""
    
    def __init__(self):
        self.notemap = {
            NoteColor.KICK: None,
            NoteColor.RED: None,
            NoteColor.YELLOW: None,
            NoteColor.BLUE: None,
            NoteColor.GREEN: None
        }
    
    def __eq__(self, other):
        for color in self.notemap.keys():
            if self[color] != other[color]:
                return False
        return True
                
    def __getitem__(self, c, objtype=None):
        return self.notemap[c]
    
    def __setitem__(self, c, value):
        self.notemap[c] = value
    
    def notes(self, basesorted=False):
        """Gets the notes that aren't empty."""
        notelist = [n for n in self.notemap.values() if n is not None]
        if basesorted:
            notelist.sort(key=lambda n: n.basescore())
        return notelist
    
    def count(self):
        return len(self.notes())
    
    def ghost_count(self):
        return len([n for n in self.notes() if n.is_ghost()])
    
    def accent_count(self):
        return len([n for n in self.notes() if n.is_accent()])
    
    def rowstr(self):
        return f"[{" - ".join([str(n) for n in self.notes()])}]"
    
    def notationstr(self):
        krybg = "["
        for color, note in self.notemap.items():
            krybg += color.notationstr() if note else ' '
        return krybg + "]"
    
    def apply_disco_flip(self):
        """Utility to edit notes based on a disco flip flag."""
        red = self[NoteColor.RED]
        yellow = self[NoteColor.YELLOW]
        
        if red:
            # Red -> Yellow cymbal
            red.cymbaltype = NoteCymbalType.CYMBAL
            red.colortype = NoteColor.YELLOW
        if yellow:
            # Yellow -> Red
            yellow.cymbaltype = NoteCymbalType.NORMAL
            yellow.colortype = NoteColor.RED
        
        # Color swap
        self[NoteColor.RED] = yellow
        self[NoteColor.YELLOW] = red
    
    def add_note(self, color):
        if self[color] is not None:
            raise hymisc.ChartFileError("Duplicate note.")
        note = ChordNote()
        note.colortype = color
        self[color] = note
        return note
    
    def add_2x(self):
        self.add_note(NoteColor.KICK)
        self[NoteColor.KICK].is2x = True
    
    def apply_cymbal(self, color):
        assert(self[color] is not None)
        self[color].cymbaltype = NoteCymbalType.CYMBAL
    
    def apply_ghost(self, color):
        assert(self[color] is not None)
        self[color].dynamictype = NoteDynamicType.GHOST
    
    def apply_accent(self, color):
        assert(self[color] is not None)
        self[color].dynamictype = NoteDynamicType.ACCENT

