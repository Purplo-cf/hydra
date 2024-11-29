# The end result of Hydra processing: Each unique chart can have 1 HydraRecord per combination of difficulty, norm/pro, and 2x bass.
class HydraRecord():
    
    def __init__(self):
        
        self.version = None
        
        # Identifying info for this record - only 1 HydraRecord for each unique combination of these
        self.songid = None
        self.difficulty = None
        self.prodrums = None
        self.bass2x = None
        
        # Analysis results
        self.notecount = None
        self.solos = []
        self.multsqueezes = []
        self.paths = []
        
        # Non-SP scoring
        self.score_base = None      # Sum of base note values (50 or 65) ("Notes" in CH)
        self.score_combo = None     # Additional points from 2x/3x/4x combo multiplier ("Combo Bonus" in CH)
        self.score_accents = None  # "Accent Notes" in CH
        self.score_ghosts = None  # "Ghost Notes" in CH
        
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
        for r_solo in r_dict['solos']:
            raise NotImplementedError
        for msq_dict in r_dict['multsqueezes']:
            multsqueeze = HydraRecordMultSqueeze()
            
            multsqueeze.multiplier = msq_dict['multiplier']
            multsqueeze.chord = HydraRecordChord.from_dict(msq_dict['chord'])
            multsqueeze.squeezecount = msq_dict['squeezecount']
            multsqueeze.points = msq_dict['points']
            
            record.multsqueezes.append(multsqueeze)
            
        for path_dict in r_dict['paths']:
            path = HydraRecordPath()
            
            for act_dict in path_dict['activations']:
                act = HydraRecordActivation()
                
                act.skips = act_dict['skips']
                act.measure = act_dict['measure']
                act.chord = HydraRecordChord.from_dict(act_dict['chord'])
                act.sp_meter = act_dict['sp_meter']
                
                path.activations.append(act)
                
                
            path.avgmultiplier = path_dict['avgmultiplier']
            path.score_sp = path_dict['score_sp']
            
            record.paths.append(path)
            
            
        record.score_base = r_dict['score_base']
        record.score_combo = r_dict['score_combo']
        record.score_accents = r_dict['score_accents']
        record.score_ghosts = r_dict['score_ghosts']
        
        return record

        
    def solobonus(self): # Sum of solo bonuses ("Solo Bonus" in CH)
        return sum([s.bonus() for s in self.solos])

    def json(self):
        return json.dumps(self, default=lambda r: r.__dict__, sort_keys=True, indent=4)
        
    # There's multiple ways to chop up scoring by source, but this way mirrors the CH score screen.
    def optimal(self):
        notes = self.score_base
        combo_bonus = self.score_combo
        starpower = self.paths[0].score_sp
        solobonus = sum([s.bonus() for s in self.solos])
        accents = self.score_accents
        ghosts = self.score_ghosts
        
        return notes + combo_bonus + starpower + solobonus + accents + ghosts

class HydraRecordSolo():
    
    def __init__(self):
        self.notecount = None
    
    def bonus(self):
        return 100 * self.notecount
        
class HydraRecordPath():
    
    def __init__(self):
        
        self.activations = []
        self.avgmultiplier = None
        self.score_sp = None # "Star Power" in CH

class HydraRecordActivation():
    
    def __init__(self):
        self.skips = None
        self.measure = None
        self.chord = None
        self.sp_meter = None
        
class HydraRecordMultSqueeze():
    
    def __init__(self):
        # This squeeze happens while hitting this multiplier (2, 3, or 4)
        self.multiplier = None
        # This squeeze happens while hitting this chord
        self.chord = None
        # This many notes in the chord can be squeezed
        self.squeezecount = None
        # The base points gained from performing this squeeze fully vs. completely missing it.
        self.points = None

class HydraRecordChord():
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
        
