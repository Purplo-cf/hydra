# To do: this are now path details rather than logging related
class Activation:
    
    def __init__(self, chord, skips, sp, measure):
        self.chord = chord
        self.skips = skips
        self.sp = sp
        self.measure = measure
        self.activation_squeeze = None
        self.backend_squeeze = None
        self.phrase_squeeze = None # todo better data structure for this tristate (None, In, Out)
        self.quantum_fill = None
        
# A chord, the multiplier the chord hits, the number of notes that can be squeezed, and the associated point difference.
class MultiplierSqueeze:
    
    def __init__(self, chord, multiplier, squeeze_count, extrascore):
        self.chord = chord
        self.multiplier = multiplier
        self.squeeze_count = squeeze_count
        self.extrascore = extrascore

# skips_with_fill is the 'E number' in path notation.
# offset_to_flip_ms is the threshold where the fill no longer appears, reducing skips by 1.
class CalibrationFill:

    def __init__(self, skips_with_fill, offset_to_flip_ms):
        self.skips_with_fill = skips_with_fill
        self.offset_to_flip_ms = offset_to_flip_ms

class ActivationSqueeze:
    
    def __init__(self, chord, extrascore):
        self.chord = chord
        self.extrascore = extrascore

class BackendSqueeze:
    
    def __init__(self, extrascore):
        self.extrascore = extrascore
