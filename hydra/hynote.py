from enum import Enum
from . import hylog

# Utility for getting the combo-based score multiplier.
# To do: Make a wrapper class for the combo number, and then simplify things using combo.multiplier
def to_multiplier(combo):
    if combo < 10:
        return 1
    elif combo < 20:
        return 2
    elif combo < 30:
        return 3
    else:
        return 4
        
class ChordNote(Enum):
    NORMAL = 1
    GHOST = 2
    ACCENT = 3
    
    # add 3 to turn any normal note into a cymbal.
    CYMBAL = 4
    CYMBAL_GHOST = 5
    CYMBAL_ACCENT = 6
    
    def basescore(self, no_dynamics=False):
        normal = 50
        cymbal = 65
        dynamic_mult = 1 if no_dynamics else 2
        
        match self:
            case ChordNote.NORMAL:
                return normal
            case ChordNote.GHOST | ChordNote.ACCENT:
                return normal * dynamic_mult
            case ChordNote.CYMBAL:
                return cymbal
            case ChordNote.CYMBAL_GHOST | ChordNote.CYMBAL_ACCENT:
                return cymbal * dynamic_mult
                
    def suffix(self, toms_allowed):
        match self:
            case ChordNote.NORMAL:
                return "Tom" if toms_allowed else ""
            case ChordNote.GHOST:
                return "Tom (Ghost)" if toms_allowed else " (Ghost)"
            case ChordNote.ACCENT:
                return "Tom (Accent)" if toms_allowed else " (Accent)"
            case ChordNote.CYMBAL:
                return "Cym"
            case ChordNote.CYMBAL_GHOST:
                return "Cym (Ghost)"
            case ChordNote.CYMBAL_ACCENT:
                return "Cym (Accent)"
            
    
    def to_cymbal(self):
        match self:
            case ChordNote.NORMAL:
                return ChordNote.CYMBAL
            case ChordNote.GHOST:
                return ChordNote.CYMBAL_GHOST
            case ChordNote.ACCENT:
                return ChordNote.CYMBAL_ACCENT
            case _:
                return self
                
    def to_normal(self):
        match self:
            case ChordNote.CYMBAL:
                return ChordNote.NORMAL
            case ChordNote.CYMBAL_GHOST:
                return ChordNote.GHOST
            case ChordNote.CYMBAL_ACCENT:
                return ChordNote.ACCENT
            case _:
                return self
    
    def disco_flipped(self):
        match self:
            case ChordNote.NORMAL:
                return ChordNote.CYMBAL
            case ChordNote.GHOST:
                return ChordNote.CYMBAL_GHOST
            case ChordNote.ACCENT:
                return ChordNote.CYMBAL_ACCENT
            case ChordNote.CYMBAL:
                return ChordNote.NORMAL
            case ChordNote.CYMBAL_GHOST:
                return ChordNote.GHOST
            case ChordNote.CYMBAL_ACCENT:
                return ChordNote.ACCENT
                
    def json_value(self):
        match self:
            case ChordNote.NORMAL:
                return "normal"
            case ChordNote.GHOST:
                return "ghost"
            case ChordNote.ACCENT:
                return "accent"
            case ChordNote.CYMBAL:
                return "cymbal"
            case ChordNote.CYMBAL_GHOST:
                return "cymbal ghost"
            case ChordNote.CYMBAL_ACCENT:
                return "cymbal accent"
    
# Class for a group of notes that happen simultaneously.
class Chord:
    def __init__(self):
        
        # When a chord is primed, it has finished adding notes but can still gain modifiers.
        self.primed = False
        
        # Song
        self.timestamp_time = None
        self.timestamp_measures = None
        
        # Notes
        self.Kick2x = None
        self.Kick = None
        self.Red = None
        self.Yellow = None
        self.Blue = None
        self.Green = None
        
        # Modifiers
        self.is_activation = False
        self.grants_sp = False
        self.in_solo = False
        
        # Analysis
        self.multiplier_squeeze_count = 0
        
        
    def __str__(self):
        chordstr = ""
        
        for name,note,can_tom in [("Kick (2x)", self.Kick2x, False),("Kick", self.Kick, False),("Red", self.Red, False),("Yellow", self.Yellow, True),("Blue", self.Blue, True),("Green", self.Green, True)]:
            if note != None:
                chordstr += name + note.suffix(can_tom) + " — "
        
        return chordstr[:-3]
        
    # To do: this is add_midi_note
    def add_note(self, note, velocity):
        match note:
            case 95:
                assert(self.Kick2x == None)
                self.Kick2x = ChordNote.NORMAL
            case 96:
                assert(self.Kick == None)
                self.Kick = ChordNote.NORMAL
            case 97:
                assert(self.Red == None)
                match velocity:
                    case 1:
                        self.Red = ChordNote.GHOST
                    case 127:
                        self.Red = ChordNote.ACCENT
                    case _:
                        self.Red = ChordNote.NORMAL
            case 98:
                assert(self.Yellow == None)
                match velocity:
                    case 1:
                        self.Yellow = ChordNote.GHOST
                    case 127:
                        self.Yellow = ChordNote.ACCENT
                    case _:
                        self.Yellow = ChordNote.NORMAL
            case 99:
                assert(self.Blue == None)
                match velocity:
                    case 1:
                        self.Blue = ChordNote.GHOST
                    case 127:
                        self.Blue = ChordNote.ACCENT
                    case _:
                        self.Blue = ChordNote.NORMAL
            case 100:
                assert(self.Green == None)
                match velocity:
                    case 1:
                        self.Green = ChordNote.GHOST
                    case 127:
                        self.Green = ChordNote.ACCENT
                    case _:
                        self.Green = ChordNote.NORMAL
            
    # Utility to apply cymbals to existing notes
    def apply_cymbals(self, yellow_cymbal, blue_cymbal, green_cymbal):
        if yellow_cymbal != None and self.Yellow != None:
            self.Yellow = self.Yellow.to_cymbal() if yellow_cymbal else self.Yellow.to_normal()
        if blue_cymbal != None and self.Blue != None:
            self.Blue = self.Blue.to_cymbal() if blue_cymbal else self.Blue.to_normal()
        if green_cymbal != None and self.Green != None:
            self.Green = self.Green.to_cymbal() if green_cymbal else self.Green.to_normal()            
            
    def apply_disco_flip(self):
        raw_red = self.Red
        raw_yellow = self.Yellow
                    
        self.Red = raw_yellow.disco_flipped() if raw_yellow else None
        self.Yellow = raw_red.disco_flipped() if raw_red else None
                        
    # Get the chord's notes as a collection
    def notes(self):
        return [n for n in [self.Kick2x, self.Kick, self.Red, self.Yellow, self.Blue, self.Green] if n != None]
        
    # Number of notes in the chord.
    def count(self):
        return len(self.notes())
        
    def ghost_count(self):
        return len([n for n in self.notes() if n in [ChordNote.GHOST, ChordNote.CYMBAL_GHOST]])
        
    def accent_count(self):
        return len([n for n in self.notes() if n in [ChordNote.ACCENT, ChordNote.CYMBAL_ACCENT]])

    # Base scores for each note in the chord.
    def point_spread(self, reverse=False, no_dynamics=False):
        return sorted([n.basescore(no_dynamics) for n in self.notes()], reverse=reverse)
        
    def basescore(self):
        return sum(self.point_spread())
        
    def comboscore(self, combo, reverse=False, no_dynamics=False):
        mx_thresholds = [10,20,30]
        multiplier = to_multiplier(combo)
        chord_points = 0
        for note_points in self.point_spread(reverse, no_dynamics):
            combo += 1
            if combo in mx_thresholds:
                multiplier += 1
        
            chord_points += note_points * multiplier
            
        return chord_points
        
    # The multiplier squeeze given the combo going into the chord, or None if no multiplier squeeze is possible.
    def get_multiplier_squeeze(self, combo, sp_active):
        best_points = self.comboscore(combo)
        worst_points = self.comboscore(combo, reverse=True)
        
        if sp_active:
            best_points *= 2
            worst_points *= 2
        
        if best_points != worst_points:
            squeeze_count = (combo + self.count()) % 10 + 1
            return hylog.MultiplierSqueeze(self, to_multiplier(combo), squeeze_count, best_points - worst_points)
            
        return None
        
    
    def get_activation_note_basescore(self):
        return (self.Green or self.Blue or self.Yellow or self.Red or self.Kick or self.Kick2x).basescore()
    
    def get_activation_squeeze(self, combo):
        # best points: entire chord is under sp
        best_points = self.comboscore(combo) * 2
        
        # worst points: only activation note is under sp; 2x it by adding it again
        worst_points = self.comboscore(combo) + self.get_activation_note_basescore()*to_multiplier(combo + self.count())
        
        if best_points != worst_points:
            return hylog.ActivationSqueeze(self, best_points - worst_points)
        
        return None
        