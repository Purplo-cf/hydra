import json

from . import hymisc


class HydraRecord:
    """A "printout" representing one analyzed chart.
    
    Each unique chart file can have 1 unique HydraRecord per combination
    of difficulty, pro/non-pro, and 2x/1x bass.
    
    Multiple paths for a given chart are grouped within the same hyrecord.
    
    A hyrecord stores the version of Hydra that created it.
    
    """
    def __init__(self):   
        # Made by this version of Hydra.
        self.hyversion = hymisc.HYDRA_VERSION
        
        # Hash of the chart file. Not comparable to other apps' song hashes.
        self.hyhash = None
        
        # Some output-only metadata for convenience if digging through the json
        self.ref_songname = None
        self.ref_artistname = None
        
        # Chart params.
        self.difficulty = None
        self.prodrums = None
        self.bass2x = None
        
        # Path results.
        self.paths = []
    
    @staticmethod
    def from_dict(r_dict):
        record = HydraRecord()
        
        record.version = r_dict['version']
        
        record.songid = r_dict['songid']
        record.difficulty = r_dict['difficulty']
        record.prodrums = r_dict['prodrums']
        record.bass2x = r_dict['bass2x']
        
        record.notecount = r_dict['notecount']
        
        record._multsqueezes = []
        
        for r_solo in r_dict['solos']:
            raise NotImplementedError
        for msq_dict in r_dict['multsqueezes']:
            multsqueeze = HydraRecordMultSqueeze()
            
            multsqueeze.multiplier = msq_dict['multiplier']
            multsqueeze.chord = HydraRecordChord.from_dict(msq_dict['chord'])
            multsqueeze.squeezecount = msq_dict['squeezecount']
            multsqueeze.points = msq_dict['points']
            
            record._multsqueezes.append(multsqueeze)
            
        for path_dict in r_dict['paths']:
            path = HydraRecordPath()
            
            path.multsqueezes = record._multsqueezes
            
            for act_dict in path_dict['activations']:
                act = HydraRecordActivation()
                
                act.skips = act_dict['skips']
                act.measure = act_dict['measure']
                act.chord = HydraRecordChord.from_dict(act_dict['chord'])
                act.sp_meter = act_dict['sp_meter']
                
                path.activations.append(act)
                
                
            path.avgmultiplier = path_dict['avgmultiplier']
            
            for scoreattr in ['score_base', 'score_combo', 'score_sp',
                              'score_solo', 'score_accents', 'score_ghosts']:
                setattr(path, scoreattr, path_dict[scoreattr] if scoreattr in path_dict else 0)
                
            record.paths.append(path)
                    
        return record

    
class HydraRecordPath:
    
    def __init__(self):
        
        self.activations = []
        self.multsqueezes = []
        self.avgmultiplier = None
        self.notecount = 0
        
        # Score breakdown categories from Clone Hero
        self.score_base = 0
        self.score_combo = 0
        self.score_sp = 0
        self.score_solo = 0 
        self.score_accents = 0
        self.score_ghosts = 0

        # Redundant total score for convenience if digging through the json
        self.ref_optimal = 0
       
    def totalscore(self):
        return (self.score_base + self.score_combo + self.score_sp
                + self.score_solo + self.score_accents + self.score_ghosts)

class HydraRecordActivation:
    
    def __init__(self):
        self.skips = None
        self.timecode = None
        self.chord = None
        self.sp_meter = None
        
        self.frontend = None
        self.backends = []
        
        self.sqinouts = []
        
    def __repr__(self):
        return f"{self.skips}{''.join(self.sqinouts)}\t{self.timecode.measurestr()}\t{self.sp_meter}\t{self.chord.rowstr()}"
        

        
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

class HydraRecordChord:
    def __init__(self, k, r, y, b, g):
        self.kick = k
        self.red = r
        self.yellow = y
        self.blue = b
        self.green = g
    
    def __eq__(self, other):
        return self.kick == other.kick and self.red == other.red and self.yellow == other.yellow and self.blue == other.blue and self.green == other.green
        
    def __repr__(self):
        return json.dumps(self, default=lambda r: r.__dict__, sort_keys=True, indent=4)
        
    def rowstr(self):
        return f"{"K" if self.kick else ""}{"R" if self.red else ""}{"Y" if self.yellow else ""}{"B" if self.blue else ""}{"G" if self.green else ""}"
        
    @staticmethod
    def from_chord(chord):
        k = "normal" if chord.Kick2x or chord.Kick else None
        r = chord.Red.json_value() if chord.Red else None
        y = chord.Yellow.json_value() if chord.Yellow else None
        b = chord.Blue.json_value() if chord.Blue else None
        g = chord.Green.json_value() if chord.Green else None
        
        return HydraRecordChord(k, r, y, b, g)
        
    @staticmethod
    def from_dict(c_dict):
        k = c_dict['kick']
        r = c_dict['red']
        y = c_dict['yellow']
        b = c_dict['blue']
        g = c_dict['green']
        
        return HydraRecordChord(k, r, y, b, g)
        
