import json

# The end result of Hydra processing: Each unique chart can have 1 HydraRecord per combination of difficulty, norm/pro, and 2x bass.
class HydraRecord:
    
    def __init__(self):
        
        self.version = None
        
        # Parameters for this record - only 1 HydraRecord for each unique combination of these
        self.songid = None
        self.difficulty = None
        self.prodrums = None
        self.bass2x = None
        
        # Analysis results
        self.notecount = None
        self.solos = []
        #self.multsqueezes = []
        self.paths = []
       
    @staticmethod
    def from_graph(song, pather):
        record = HydraRecord()
        
        record.notecount = song.note_count
    
        for graphpath in pather.paths:
            record.paths.append(graphpath.record)
    
    
        return record
    
    @staticmethod
    def from_hydra(song, optimizer):
        record = HydraRecord()
        
        # to do: version
        
        # to do: songid
        # to do: difficulty
        # to do: prodrums
        # to do: bass2x
        
        record.notecount = song.note_count
        # to do: solos
        for msq in optimizer.paths[0].multiplier_squeezes:
            multsqueeze = HydraRecordMultSqueeze()
            
            multsqueeze.multiplier = msq.multiplier + 1
            multsqueeze.chord = HydraRecordChord.from_chord(msq.chord)
            multsqueeze.squeezecount = msq.squeeze_count
            multsqueeze.points = msq.extrascore
            
            record.multsqueezes.append(multsqueeze)
            
        for p in optimizer.paths:
            path = HydraRecordPath()
        
            for a in p.activations:
                activation = HydraRecordActivation()
                
                activation.skips = a.skips
                activation.measure = round(a.measure, 2)
                activation.chord = HydraRecordChord.from_chord(a.chord)
                activation.sp_meter = round(a.sp * 4)
                
                path.activations.append(activation)
                
            # to do: avgmultiplier
            path.score_sp = p.spscore + sum([s.extrascore for s in p.activation_squeezes]) + sum([s.extrascore for s in p.backend_squeezes]) 

            record.paths.append(path)
                
        record.score_base = optimizer.paths[0].basescore + sum([s.extrascore for s in optimizer.paths[0].multiplier_squeezes])
        record.score_combo = 0
        record.score_accents = optimizer.paths[0].basedynamics
        record.score_ghosts = 0
        
        return record
        
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
            
            for scoreattr in ['score_base', 'score_combo', 'score_sp', 'score_solo', 'score_accents', 'score_ghosts']:
                setattr(path, scoreattr, path_dict[scoreattr] if scoreattr in path_dict else 0)
                
            record.paths.append(path)
                    
        return record

        
    def solobonus(self): # Sum of solo bonuses ("Solo Bonus" in CH)
        return sum([s.bonus() for s in self.solos])

    def json(self):
        return json.dumps(self, default=lambda r: r.__dict__, sort_keys=True, indent=4)
        

    def optimal(self):
        return self.paths[0].optimal()

class HydraRecordSolo:
    
    def __init__(self):
        self.notecount = None
    
    def bonus(self):
        return 100 * self.notecount
        
class HydraRecordPath:
    
    def __init__(self):
        
        self.activations = []
        self.multsqueezes = []
        self.avgmultiplier = None
        
        self.score_base = 0      # Sum of base note values (50 or 65) ("Notes" in CH)
        self.score_combo = 0     # Additional points from 2x/3x/4x combo multiplier ("Combo Bonus" in CH)
        self.score_sp = 0 # "Star Power" in CH
        self.score_solo = 0 
        self.score_accents = 0  # "Accent Notes" in CH
        self.score_ghosts = 0  # "Ghost Notes" in CH

        
    # There's multiple ways to chop up scoring by source, but this way mirrors the CH score screen.
    def optimal(self):
        return self.score_base + self.score_combo + self.score_sp + self.score_solo + self.score_accents + self.score_ghosts

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
        
