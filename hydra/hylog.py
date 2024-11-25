# Analysis features: The 'things' that show up in paths and make them different from each other.
# Structs that store info and can be read back out after processing.

# to do: not "Record", but a name like "Log" might be better than feature. or Path Event.

# to do: "Record" naming is deprecated
class ActivationRecord:
    
    def __init__(self, chord, skips, sp, measure):
        self.chord = chord
        self.skips = skips
        self.sp = sp
        self.measure = measure
        self.activation_squeeze = None
        self.backend_squeeze = None
        self.phrase_squeeze = None # todo better data structure for this tristate (None, In, Out)
        self.quantum_fill = None

    def report(self, output):
        match self.phrase_squeeze:
            case "In":
                skips_suffix = '+'
            case "Out":
                skips_suffix = '-'
            case _:
                skips_suffix = ""
        
        
        measure_prefix = '~' if abs(self.measure - round(self.measure)) > 0.0000001 else ''
        
        skips = f'E{self.quantum_fill.skips_with_fill}' if self.quantum_fill else f'{self.skips}'
        
        output.write(f"\t\t\t{skips}{skips_suffix}\tMeasure {measure_prefix}{round(self.measure)}: {self.chord} (SP: {round(self.sp*4)*25}%)\n")
        
        if self.quantum_fill:
            self.quantum_fill.report(output)
        
        if self.activation_squeeze:
            self.activation_squeeze.report(output)
        
        if self.phrase_squeeze == "In":
            output.write(f"\t\t\t\t\tSqIn: chain the SP phrase at the end of this activation.\n")
        if self.phrase_squeeze == "Out":
            output.write(f"\t\t\t\t\tSqOut: don't chain the SP phrase at the end of this activation.\n")
        
# A chord, the multiplier the chord hits, the number of notes that can be squeezed, and the associated point difference.
class MultiplierSqueeze:
    
    def __init__(self, chord, multiplier, squeeze_count, extrascore):
        self.chord = chord
        self.multiplier = multiplier
        self.squeeze_count = squeeze_count
        self.extrascore = extrascore

    def report(self, output):
        output.write(f"\t\t\t{self.multiplier + 1}x\t{self.chord}: Hit {self.squeeze_count} high-value note{'s' if self.squeeze_count != 1 else ''} late for +{self.extrascore}.\n")
    
# A fill that can be present or not in the path depending on whether the player gained activatable SP early or late.
# Some paths will require a quantum fill to be present.
# Because skipped fills don't affect score, paths won't require skipped quantum fills to disappear, but it could throw off skip counting.
class QuantumFill:
    # to do some of these params are redundant
    def __init__(self, skips_with_fill, offset_to_flip_ms):
        self.skips_with_fill = skips_with_fill
        self.offset_to_flip_ms = offset_to_flip_ms

    def report(self, output):
        rounded = round(self.offset_to_flip_ms, 1)
        
        if self.skips_with_fill == 0:
            output.write(f"\t\t\t\t\tE0: Must gain SP earlier than {rounded} ms.\n")
        else:
            output.write(f"\t\t\t\t\tE{self.skips_with_fill}/L{self.skips_with_fill - 1} ({rounded} ms).\n")
        
        # if self.must_be_present:
            # if self.is_normally_present:
                # # Must avoid gaining SP late.
                # output.write(f"\t\t\t\t\tQuantum fill: Normally appears, but make sure to gain SP earlier than {rounded} ms.\n")
            # else:
                # # Must gain SP early.
                # output.write(f"\t\t\t\t\tQuantum fill: Must gain SP earlier than {rounded} ms for it to appear.\n")
        # else:
            # if self.is_normally_present:
                # # 1st skip may disappear if SP was gained late.
                # output.write(f"\t\t\t\t\tQuantum fill: 1 fewer skip (no score change) if SP is gained later than {rounded} ms.\n")
            # else:
                # # Extra skip may appear if SP was gained early.
                # output.write(f"\t\t\t\t\tQuantum fill: 1 extra skip (no score change) if SP is gained earlier than {rounded} ms.\n")

class FillRecord:
    
    def __init__(self, measure, sp_active, sp_meter):
        # Physical attributes
        self.measure = measure
        self.sp_age_time = None
        self.sp_age_measures = None
        self.threshold_beats = None
        
        # Analytical attributes
        self.result = None
        self.sp_active = sp_active
        self.sp_meter = sp_meter

    def report(self, output):
        if not self.sp_active and self.sp_meter >= 0.5:
            output.write(f"\t\t{self.measure}:\n\t\t\tSP: {self.sp_meter}({"active" if self.sp_active else "inactive"})\n\t\t\tSP age: {self.sp_age_time}s/{self.sp_age_measures}mm/{self.threshold_beats}b\n\t\t\tResult: {self.result}\n")
        else:
            output.write(f"\t\t{self.measure}:\n\t\t\tSP: {self.sp_meter}({"active" if self.sp_active else "inactive"})\n\t\t\tResult: {self.result}\n")
            
            
        

class ActivationSqueeze:
    
    def __init__(self, chord, extrascore):
        self.chord = chord
        self.extrascore = extrascore
        
    def report(self, output):
        output.write(f"\t\t\t\t\tHit the activation note first for +{self.extrascore}.\n")

class BackendSqueeze:
    
    def __init__(self, extrascore):
        self.extrascore = extrascore
        
    def report(self, output):
        output.write(f"\t\t\t\t\tinsert report for backend squeeze here (+{self.extrascore})\n")

class ChordLogEntry:
    
    def __init__(self, chord, features, measure):
        self.chord = chord
        self.features = features
        self.measure = measure
        
    def report(self, output):
        if len(self.features) > 0:
            output.write(f"{round(self.measure,2)}\t\t\t{self.chord}\t\t\t({", ".join(self.features)})\n")
        else:
            output.write(f"{round(self.measure,2)}\t\t\t{self.chord}\n")