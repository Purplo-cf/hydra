import json
from enum import Enum

from . import hymisc


def custom_json_save(obj):
    """Object --> dict conversion."""
    if isinstance(obj, HydraRecord):
        return {
            '__obj__': 'record',
            
            'hyversion': obj.hyversion,
            'paths': obj.paths,
        }
    
    if isinstance(obj, HydraRecordPath):
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
        
    if isinstance(obj, HydraRecordMultSqueeze):
        return {
            '__obj__': 'msq',
        
            'multiplier': obj.multiplier,
            'chord': obj.chord,
            'squeezecount': obj.squeezecount,
            'points': obj.points,
        }
        
    if isinstance(obj, HydraRecordActivation):
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
        
    if isinstance(obj, HydraRecordFrontendSqueeze):
        return {
            '__obj__': 'fsq',
        
            'chord': obj.chord,
            'points': obj.points,
        }
        
    if isinstance(obj, HydraRecordBackendSqueeze):
        return {
            '__obj__': 'bsq',
        
            'timecode': obj.timecode,
            'chord': obj.chord,
            'points': obj.points,
            'sqout_points': obj.sqout_points,
            'offset_ms': obj.offset_ms,
    }
        
    if isinstance(obj, HydraRecordChord):
        return {
            '__obj__': 'chord',
        
            'kick': obj.notemap[HydraRecordNoteColor.KICK],
            'red': obj.notemap[HydraRecordNoteColor.RED],
            'yellow': obj.notemap[HydraRecordNoteColor.YELLOW],
            'blue': obj.notemap[HydraRecordNoteColor.BLUE],
            'green': obj.notemap[HydraRecordNoteColor.GREEN],
        }
        
    if isinstance(obj, HydraRecordChordNote):
        return {
            '__obj__': 'note',
        
            'dynamic': obj.dynamictype,
            'cymbal': obj.cymbaltype,
            'is_2x': obj.is2x,
        }
    
    if isinstance(obj, HydraRecordNoteCymbalType):
        return {
            HydraRecordNoteCymbalType.NORMAL: 'normal',
            HydraRecordNoteCymbalType.CYMBAL: 'cymbal',
        }[obj]
        
    if isinstance(obj, HydraRecordNoteDynamicType):
        return {
            HydraRecordNoteDynamicType.NORMAL: 'normal',
            HydraRecordNoteDynamicType.GHOST: 'ghost',
            HydraRecordNoteDynamicType.ACCENT: 'accent',
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
    

def custom_json_load(_dict):
    """Dict --> Object conversion."""
    try:
        obj_code = _dict['__obj__']
    except KeyError:
        return _dict
    
    if obj_code == 'record':
        o = HydraRecord()
        o.hyversion = _dict['hyversion']
        o.paths = _dict['paths']
        
        return o
        
    if obj_code == 'path':
        o = HydraRecordPath()
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
        o = HydraRecordMultSqueeze()
        o.multiplier = _dict['multiplier']
        o.chord = _dict['chord']
        o.squeezecount = _dict['squeezecount']
        o.points = _dict['points']
        
        return o
    
    if obj_code == 'activation':
        o = HydraRecordActivation()
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
        o = HydraRecordFrontendSqueeze(_dict['chord'], _dict['points'])

        return o
        
    if obj_code == 'bsq':
        o = HydraRecordBackendSqueeze(
            _dict['timecode'],
            _dict['chord'],
            _dict['points'],
            _dict['sqout_points'],
        )
        o.offset_ms = _dict['offset_ms']
        
        return o
        
    if obj_code == 'chord':
        o = HydraRecordChord()
        o.notemap = {
            HydraRecordNoteColor.KICK: _dict['kick'],
            HydraRecordNoteColor.RED: _dict['red'],
            HydraRecordNoteColor.YELLOW: _dict['yellow'],
            HydraRecordNoteColor.BLUE: _dict['blue'],
            HydraRecordNoteColor.GREEN: _dict['green'],
        }
        
        for c, note in o.notemap.items():
            if note:
                note.colortype = c
        
        return o
        
    if obj_code == 'note':
        o = HydraRecordChordNote()
        
        o.cymbaltype = {
            'normal': HydraRecordNoteCymbalType.NORMAL,
            'cymbal': HydraRecordNoteCymbalType.CYMBAL,
        }[_dict['cymbal']]
        
        o.dynamictype = {
            'normal': HydraRecordNoteDynamicType.NORMAL,
            'ghost': HydraRecordNoteDynamicType.GHOST,
            'accent': HydraRecordNoteDynamicType.ACCENT,
        }[_dict['dynamic']]
        
        o.is2x = _dict['is_2x']
        
        return o
            
    if obj_code == 'timecode':
        o = hymisc.Timecode(_dict['tick'], None)
        o.measure_beats_ticks = _dict['mbt']
        o.measures_decimal = _dict['m_decimal']
        o.ms = _dict['ms']
        
        return o
    
    raise TypeError(f"Tried to load unhandled JSON object: {_dict}")

class HydraRecord:
    """A "printout" representing one analyzed chart.
    
    Each unique chart file (hash) can have 1 unique HydraRecord per combination
    of difficulty, pro/non-pro, and 2x/1x bass (chartmode).
    
    Multiple paths for a given chart are grouped within the same hyrecord.
    
    A hyrecord stores the version of Hydra that created it.
    
    """
    def __init__(self):   
        # Made by this version of Hydra.
        self.hyversion = hymisc.HYDRA_VERSION
        
        # Path results.
        self.paths = []


class HydraRecordPath:
    
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
       
    def totalscore(self):
        return (self.score_base + self.score_combo + self.score_sp
                + self.score_solo + self.score_accents + self.score_ghosts)
                
    def pathstring(self):
        if self.activations:
            return ' '.join([str(a.notationstr()) for a in self.activations])
        else:
            return "(No activations.)"
            
class HydraRecordActivation:
    
    def __init__(self):
        self.skips = None
        self.timecode = None
        self.chord = None
        self.sp_meter = None
        
        self.frontend = None
        self.backends = []
        
        self.sqinouts = []
        
        self.e_offset = None
        
    def __repr__(self):
        return f"{self.skips}{''.join(self.sqinouts)}\t{self.timecode.measurestr()}\t{self.sp_meter}\t{self.chord.rowstr()}"

    def notationstr(self):
        e = 'E' if self.is_e_critical() else ''
        return f"{e}{self.skips}{''.join(self.sqinouts)}"
        
    def is_e_critical(self):
        return self.e_offset < 70 

class HydraRecordMultSqueeze:
    
    def __init__(self):
        # This squeeze happens while hitting this multiplier (2, 3, or 4)
        self.multiplier = None
        # This squeeze happens while hitting this chord
        self.chord = None
        # This many notes in the chord can be squeezed
        self.squeezecount = None
        # The base points gained from performing this squeeze fully vs. completely missing it.
        self.points = None
        
    def notationstr(self):
        return f"{self.multiplier}x"


class HydraRecordFrontendSqueeze:
    
    def __init__(self, chord, points):
        self.chord = chord
        self.points = points


class HydraRecordBackendSqueeze:
    def __init__(self, timecode, chord, points, sqout_points):
        self.timecode = timecode
        self.chord = chord
        self.points = points
        self.sqout_points = sqout_points
        self.offset_ms = None


    def ratingstr(self):
        # ms thresholds and the label for the adjacent region on the negative side
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


class HydraRecordNoteColor(Enum):
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
            HydraRecordNoteColor.YELLOW,
            HydraRecordNoteColor.BLUE,
            HydraRecordNoteColor.GREEN
        ]
            
        
    def allows_dynamics(self):
        return self in [
            HydraRecordNoteColor.RED,
            HydraRecordNoteColor.YELLOW,
            HydraRecordNoteColor.BLUE,
            HydraRecordNoteColor.GREEN
        ]
        
    def __str__(self):
        match self:
            case HydraRecordNoteColor.KICK:
                return "Kick"
            case HydraRecordNoteColor.RED:
                return "Red"
            case HydraRecordNoteColor.YELLOW:
                return "Yellow"
            case HydraRecordNoteColor.BLUE:
                return "Blue"
            case HydraRecordNoteColor.GREEN:
                return "Green"
                
    def notationstr(self):
        match self:
            case HydraRecordNoteColor.KICK:
                return "K"
            case HydraRecordNoteColor.RED:
                return "R"
            case HydraRecordNoteColor.YELLOW:
                return "Y"
            case HydraRecordNoteColor.BLUE:
                return "B"
            case HydraRecordNoteColor.GREEN:
                return "G"


class HydraRecordNoteDynamicType(Enum):
    """Representation of a note's dynamic type."""
    NORMAL = 1
    GHOST = 2
    ACCENT = 3


class HydraRecordNoteCymbalType(Enum):
    """Representation of a note's dynamic type.
    
    Normal = Toms / Snare / Kick.
    
    """
    NORMAL = 1
    CYMBAL = 2


class HydraRecordChordNote:
    """Representation of a note from a chart."""

    def __init__(self):
        self.colortype = None
        self.dynamictype = HydraRecordNoteDynamicType.NORMAL
        self.cymbaltype = HydraRecordNoteCymbalType.NORMAL
        self.is2x = False
        
    def __str__(self):
        if self.colortype.allows_cymbals():
            cym = "Cym" if self.cymbaltype == HydraRecordNoteCymbalType.CYMBAL else "Tom"
        else:
            cym = ""
            
        if self.colortype.allows_dynamics():
            match self.dynamictype:
                case HydraRecordNoteDynamicType.NORMAL:
                    mod = ""
                case HydraRecordNoteDynamicType.GHOST:
                    mod = " (Ghost)"
                case HydraRecordNoteDynamicType.ACCENT:
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
        return self.dynamictype != HydraRecordNoteDynamicType.NORMAL
        
    def is_accent(self):
        return self.dynamictype == HydraRecordNoteDynamicType.ACCENT
        
    def is_ghost(self):
        return self.dynamictype == HydraRecordNoteDynamicType.GHOST
        
    def is_cymbal(self):
        return self.cymbaltype == HydraRecordNoteCymbalType.CYMBAL
        
    def flip_cymbal(self):
        self.cymbaltype = HydraRecordNoteCymbalType.NORMAL if self.is_cymbal() else HydraRecordNoteCymbalType.CYMBAL


class HydraRecordChord:
    """Representation of a chord which has 1 note (or None) for each color."""
    
    def __init__(self):
        self.notemap = {
            HydraRecordNoteColor.KICK: None,
            HydraRecordNoteColor.RED: None,
            HydraRecordNoteColor.YELLOW: None,
            HydraRecordNoteColor.BLUE: None,
            HydraRecordNoteColor.GREEN: None
        }
        
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
        return len([n for n in self.notes() if n.dynamictype == HydraRecordNoteDynamicType.GHOST])
        
    def accent_count(self):
        return len([n for n in self.notes() if n.dynamictype == HydraRecordNoteDynamicType.ACCENT])
        
    def rowstr(self):
        return f"[{" - ".join([str(n) for n in self.notes()])}]"
        
    def notationstr(self):
        letters = [c.notationstr() if n else ' ' for c, n in self.notemap.items()]
        return f"[{''.join(letters)}]"
        
    def apply_cymbals(self, yellow_iscym, blue_iscym, green_iscym):
        """Utility to edit notes based on a tom/cymbal flag."""
        for key, flag in [
            (HydraRecordNoteColor.YELLOW, yellow_iscym),
            (HydraRecordNoteColor.BLUE, blue_iscym),
            (HydraRecordNoteColor.GREEN, green_iscym)
        ]:
            if self[key] and flag is not None:
                self[key].cymbaltype = HydraRecordNoteCymbalType.CYMBAL if flag else HydraRecordNoteCymbalType.NORMAL
        
    def apply_disco_flip(self):
        """Utility to edit notes based on a disco flip flag."""
        red = self[HydraRecordNoteColor.RED]
        yellow = self[HydraRecordNoteColor.YELLOW]
        
        # Cymbal flip
        if red:
            red.flip_cymbal()
        if yellow:
            yellow.flip_cymbal()
        
        # Color swap
        self[HydraRecordNoteColor.RED] = yellow
        self[HydraRecordNoteColor.YELLOW] = red
        
        
    def add_from_midi(self, note, velocity):
        note_to_color = {
            95: HydraRecordNoteColor.KICK,
            96: HydraRecordNoteColor.KICK,
            97: HydraRecordNoteColor.RED,
            98: HydraRecordNoteColor.YELLOW,
            99: HydraRecordNoteColor.BLUE,
            100: HydraRecordNoteColor.GREEN        
        }
        
        color = note_to_color[note]
        
        assert(self[color] is None)
        newnote = HydraRecordChordNote()
        newnote.colortype = color
        if color.allows_dynamics():
            if velocity == 1:
                newnote.dynamictype = HydraRecordNoteDynamicType.GHOST
            elif velocity == 127:
                newnote.dynamictype = HydraRecordNoteDynamicType.ACCENT
            else:
                newnote.dynamictype = HydraRecordNoteDynamicType.NORMAL
        newnote.is2x = note == 95
        self[color] = newnote
        
        
    def add_note(self, color):
        assert(self[color] is None)
        self[color] = HydraRecordChordNote()
        self[color].colortype = color
        
    def add_2x(self):
        self.add_note(HydraRecordNoteColor.KICK)
        self[HydraRecordNoteColor.KICK].is2x = True
        
    def apply_cymbal(self, color):
        assert(self[color] is not None)
        self[color].cymbaltype = HydraRecordNoteCymbalType.CYMBAL
        
    def apply_ghost(self, color):
        assert(self[color] is not None)
        self[color].dynamictype = HydraRecordNoteDynamicType.GHOST
        
    def apply_accent(self, color):
        assert(self[color] is not None)
        self[color].dynamictype = HydraRecordNoteDynamicType.ACCENT

