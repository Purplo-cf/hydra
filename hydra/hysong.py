import mido
import re
import hashlib

from . import hydata
from . import hymisc


class SongTimestamp:
    """Associates a timecode with a chord and some gameplay modifiers."""
    def __init__(self):      
        self.timecode = None
        self.chord = None
        
        self.flag_solo = False
        self.flag_sp = False
        self.activation_length = None

    def __str__(self):
        if self.flag_sp:
            mod = ", SP"
        elif self.activation_length:
            mod = f", Fill ({self.activation_length})"
        else:
            mod = ""
        return f"[{self.timecode.measurestr()}: {self.chord.rowstr()}{mod}]"

    def has_activation(self):
        return self.activation_length is not None


class SongIter:
    def __init__(self, song):
        self.i = 0
        self.tick = 0
        self.tpm_keys = list(song.tpm_changes.keys())
        self.tpm = song.tpm_changes[self.tpm_keys.pop(0)]
        self.bpm_keys = list(song.bpm_changes.keys())
        self.bpm = song.bpm_changes[self.bpm_keys.pop(0)]
        self.song = song

    def __iter__(self):
        return self
        
    def __next__(self):
        try:
            ts = self.song.sequence[self.i]
            self.i += 1
        except IndexError:
            raise StopIteration

        self.tick = ts.timecode.ticks
        if self.tpm_keys and self.tick >= self.tpm_keys[0]:
            self.tpm = self.song.tpm_changes[self.tpm_keys.pop(0)]
        
        if self.bpm_keys and self.tick >= self.bpm_keys[0]:
            self.bpm = self.song.bpm_changes[self.bpm_keys.pop(0)]
        
        return (ts, self.tpm, self.bpm)

class Song:
    """The structure for charts that have been loaded in. A sequence of
    timestamps, plus tempo/meter changes.
    """
    def __init__(self, resolution):
        self.sequence = []
        
        """This song's conversions from ticks to any other time unit."""
        self.tick_resolution = resolution
        self.tpm_changes = {0: resolution * 4}
        self.bpm_changes = {}
        
        """Stub for song-wide analysis."""
        self.features = []
        
    def __iter__(self):
        return SongIter(self)
    
    def check_activations(self):
        """ If a chart has no drum fills, add them in like Clone Hero would.
        Rule: Add at m3.1.0 + n*(4m), 1/2 m long, if there's a chord there.
        To do: More testing around this rule. Unit tests.
        """
        if all([not ts.has_activation() for ts in self.sequence]):
            self.features.append('Auto-Generated Fills')
            tpm = self.tpm_changes[0]
            for timestamp, tpm, bpm in self:
                if (
                    timestamp.timecode.is_measure_start()
                    and timestamp.timecode.measure_beats_ticks[0] % 4 == 2
                    and timestamp.chord
                    and not timestamp.flag_sp
                ):
                    timestamp.activation_length = tpm // 2

    def start_time(self):
        return hymisc.Timecode(0, self)


class MidiParser:
    """Reads a .mid file to create a Song object."""
    def __init__(self):
        self.song = None
        
        # Parsing mode
        self.mode_difficulty = None
        self.mode_pro = None
        self.mode_bass2x = None
        
        # Parsing state
        self._chord = None
        self._msg_buffer = None
        self._flag_solo = None
        self._flag_cymbals = None
        self._flag_disco = None
        self._fill_start_tick = None
        self._dynamics_enabled = None

    def optype(self, msg, tick):
        """Parses individual midi messages into the actual actions the parser
        will take based on that message.
        
        We figure out these payloads but don't run them right away because 
        we may want to run them in a particular order, or filter them.
        
        See: op_* functions.
        
        Returns: (op_phase, op_func, *args)
        
        """
        # The actual conditions for note on/off in practice
        is_noteon = (
            msg.type == 'note_on' and msg.velocity > 0
        )
        is_noteoff = (
            msg.type == 'note_off'
            or msg.type == 'note_on' and msg.velocity == 0
        )
        
        # Text events that are used for disco flip
        r_disco_on_x = r'\[mix.3.drums\d?d\]'
        r_disco_off_x = r'\[mix.3.drums\d?\]'
        
        r_dynamics = r'\[?ENABLE_CHART_DYNAMICS\]?'
            
        # Interpret midi message for which procedure to return
        match msg:
            case mido.MetaMessage(text=t) if re.fullmatch(r_dynamics, t):
                return ('pre', self.op_enable_dynamics)
            case mido.MetaMessage(text=t) if re.fullmatch(r_disco_on_x, t):
                return ('pre', self.op_disco, True)
            case mido.MetaMessage(text=t) if re.fullmatch(r_disco_off_x, t):
                return ('pre', self.op_disco, False)
            case mido.MetaMessage(type='set_tempo'):
                return ('time', self.op_tempo, tick, msg.tempo)
            case mido.MetaMessage(type='time_signature'):
                return ('time', self.op_timesig, tick, msg.numerator, msg.denominator)
            case mido.Message(note=120) if is_noteon:
                return ('pre', self.op_fillstart, tick)
            case mido.Message(note=120) if is_noteoff:
                return ('post', self.op_fillend, tick)
            case mido.Message(note=116) if is_noteoff:
                return ('pre', self.op_sp_end)
            case mido.Message(note=112) if is_noteon:
                return ('pre', self.op_tom, hydata.NoteColor.GREEN, hydata.NoteCymbalType.NORMAL)
            case mido.Message(note=112) if is_noteoff:
                return ('pre', self.op_tom, hydata.NoteColor.GREEN, hydata.NoteCymbalType.CYMBAL)
            case mido.Message(note=111) if is_noteon:
                return ('pre', self.op_tom, hydata.NoteColor.BLUE, hydata.NoteCymbalType.NORMAL)
            case mido.Message(note=111) if is_noteoff:
                return ('pre', self.op_tom, hydata.NoteColor.BLUE, hydata.NoteCymbalType.CYMBAL)
            case mido.Message(note=110) if is_noteon:
                return ('pre', self.op_tom, hydata.NoteColor.YELLOW, hydata.NoteCymbalType.NORMAL)
            case mido.Message(note=110) if is_noteoff:
                return ('pre', self.op_tom, hydata.NoteColor.YELLOW, hydata.NoteCymbalType.CYMBAL)
            case mido.Message(note=103) if is_noteon:
                return ('pre', self.op_solo, True)
            case mido.Message(note=103) if is_noteoff:
                return ('pre', self.op_solo, False)
            case mido.Message(note=100, velocity=127) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.GREEN, hydata.NoteDynamicType.ACCENT, False)
            case mido.Message(note=100, velocity=1) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.GREEN, hydata.NoteDynamicType.GHOST, False)
            case mido.Message(note=100) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.GREEN, hydata.NoteDynamicType.NORMAL, False)
            case mido.Message(note=99, velocity=127) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.BLUE, hydata.NoteDynamicType.ACCENT, False)
            case mido.Message(note=99, velocity=1) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.BLUE, hydata.NoteDynamicType.GHOST, False)
            case mido.Message(note=99) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.BLUE, hydata.NoteDynamicType.NORMAL, False)
            case mido.Message(note=98, velocity=127) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.YELLOW, hydata.NoteDynamicType.ACCENT, False)
            case mido.Message(note=98, velocity=1) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.YELLOW, hydata.NoteDynamicType.GHOST, False)
            case mido.Message(note=98) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.YELLOW, hydata.NoteDynamicType.NORMAL, False)
            case mido.Message(note=97, velocity=127) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.RED, hydata.NoteDynamicType.ACCENT, False)
            case mido.Message(note=97, velocity=1) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.RED, hydata.NoteDynamicType.GHOST, False)
            case mido.Message(note=97) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.RED, hydata.NoteDynamicType.NORMAL, False)
            case mido.Message(note=96) if is_noteon:
                return ('notes', self.op_note, hydata.NoteColor.KICK, hydata.NoteDynamicType.NORMAL, False)
            case mido.Message(note=95) if is_noteon and self.mode_bass2x:
                return ('notes', self.op_note, hydata.NoteColor.KICK, hydata.NoteDynamicType.NORMAL, True)
            case _:
                return (None, None)

    """Op functions: Each midi event results in one of these."""
    
    def op_enable_dynamics(self):
        self._dynamics_enabled = True
        
    def op_disco(self, is_on):
        self._flag_disco = is_on
    
    def op_tempo(self, tick, miditempo):
        self.song.bpm_changes[tick] = 60000000 / miditempo
    
    def op_timesig(self, tick, numerator, denominator):
        self.song.tpm_changes[tick] = self.song.tick_resolution * numerator * 4 // denominator
    
    def op_fillstart(self, tick):
        self._fill_start_tick = tick
    
    def op_fillend(self, tick):
        self.song.sequence[-1].activation_length = tick - self._fill_start_tick
    
    def op_sp_end(self):
        self.song.sequence[-1].flag_sp = True
    
    def op_tom(self, color, cymbal):
        self._flag_cymbals[color] = cymbal
    
    def op_solo(self, is_on):
        self._flag_solo = is_on
    
    def op_note(self, color, dynamic, is2x):
        note = self._chord.add_note(color)
        if self._dynamics_enabled:
            note.dynamictype = dynamic
        else:
            note.dynamictype = hydata.NoteDynamicType.NORMAL
        if color.allows_cymbals() and self.mode_pro:
            note.cymbaltype = self._flag_cymbals[color]
        note.is2x = is2x
    
    def push_timestamp(self, tick):
        """Process all the events that happened simultaneously on this tick.
        
        Because we've collected the events, we can easily do them in whichever
        order as configured in the optype function.
        
        """
        self._chord = hydata.Chord()
        
        ops = [self.optype(msg, tick) for msg in self._msg_buffer]
        
        # 'pre': Effects that apply before the timestamp is added, such as a 
        #   'previous chord' mechanic that doesn't include this chord, or
        #   flags that change the type of note that's about to be created.
        # 'notes': The actual notes being created.
        for phase in ['pre', 'notes']:
            for op_phase, op, *op_args in ops:
                if op_phase == phase:
                    try:
                        op(*op_args)
                    except hymisc.ChartFileError:
                        pass
        
        # Append to the Song
        if self._chord.count():
            timestamp = SongTimestamp()
            timestamp.chord = self._chord
            timestamp.timecode = hymisc.Timecode(tick, self.song)
            timestamp.flag_solo = self._flag_solo
            if self._flag_disco:
                timestamp.chord.apply_disco_flip()
            
            self.song.sequence.append(timestamp)
            self._chord = None
            
        # 'post': Effects that apply after the timestamp is added, such as a
        #   'previous chord' mechanic that includes this chord
        for op_phase, op, *op_args in ops:
                if op_phase == 'post':
                    try:
                        op(*op_args)
                    except hymisc.ChartFileError:
                        pass
            
        self._msg_buffer = []
    
    def parsefile(self, filename, m_difficulty, m_pro, m_bass2x):
        """After calling this, self.song will reflect the input filename.
        Must be .mid.
        """
        # Load from MIDI
        mid = mido.MidiFile(filename)
        
        # Parser settings
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x

        # Initialize Song
        self.song = Song(mid.ticks_per_beat)
        
        # Map tempo and time signatures
        elapsed_ticks = 0
        for msg in mid.tracks[0]:
            elapsed_ticks += msg.time
            op_phase, op, *op_args = self.optype(msg, elapsed_ticks)
            if op_phase == 'time':
                op(*op_args)
        
        # Add from the drum track to our Song
        for track in mid.tracks:
            if track.name == "PART DRUMS":
                elapsed_ticks = 0
                self._msg_buffer = []
                self._flag_solo = False
                self._flag_disco = False
                self._flag_cymbals = {
                    hydata.NoteColor.GREEN: hydata.NoteCymbalType.CYMBAL,
                    hydata.NoteColor.BLUE: hydata.NoteCymbalType.CYMBAL,
                    hydata.NoteColor.YELLOW: hydata.NoteCymbalType.CYMBAL
                }
                self._dynamics_enabled = False
                for msg in track:
                    if msg.time != 0:
                        # Process timestamp first
                        self.push_timestamp(elapsed_ticks)
                        elapsed_ticks += msg.time
                    
                    # Add message to group that will eventually be a timestamp
                    self._msg_buffer.append(msg)
                
                # Process a remaining timestamp if any
                self.push_timestamp(elapsed_ticks)
                break
        
        self.song.check_activations()


class ChartSection:
    """Much like a config, .chart data goes under a section name."""
    def __init__(self):
        self.name = None
        self.data = {}

class ChartDataEntry:
    """A bunch of values that are None, or set to a value if this entry in
    the .chart file was for that value.
    
    To do: clean how the key works
    
    """
    def __init__(self, keystr, valuestr):
        keystr = keystr.strip()
        valuestr = valuestr.strip()
        
        self.key_name = None
        self.key_tick = None
        
        self.property = None
        
        self.ts_numerator = None
        self.ts_denominator = None
        
        self.tempo_bpm = None
        
        self.textevent = None
        self.flagevent = None
        
        self.notevalue = None
        self.notelength = None
        
        self.phrasevalue = None
        self.phraselength = None
        
        self.solo_start = False
        self.solo_end = False
        
        self.discoflip_enable = False
        self.discoflip_disable = False
        self.discoflip_difficulty = None
        
        try:
            self.key_tick = int(keystr)
        except ValueError:
            self.key_name = keystr
        
        r_disco_on_x = r'\[?mix.3.drums\d?d\]?'
        r_disco_off_x = r'\[?mix.3.drums\d?\]?'
            
        match (valuestr, valuestr.split()):
            case v, _ if self.key_tick is None:
                try:
                    self.property = int(v)
                except ValueError:
                    self.property = v
            case _, ["TS", n]:
                self.ts_numerator = int(n)
                self.ts_denominator = 4
            case _, ["TS", n, d]:
                self.ts_numerator = int(n)
                self.ts_denominator = 2**int(d)
            case _, ["B", bpm]:
                self.tempo_bpm = int(bpm) / 1000.0
            case _, ["E", "solo"]:
                self.solo_start = True
            case _, ["E", "soloend"]:
                self.solo_end = True
            case _, ["E", event] if re.fullmatch(r_disco_off_x, event):
                self.discoflip_disable = True
            case _, ["E", event] if re.fullmatch(r_disco_on_x, event):
                self.discoflip_enable = True
            case _, ["E", *anywords]:
                self.textevent = ' '.join(anywords)
            case _, ["N", v, length]:
                self.notevalue = int(v)
                self.notelength = int(length)
            case _, ["S", v, length]:
                self.phrasevalue = int(v)
                self.phraselength = int(length)


    def is_property(self):
        return self.property != None

    def is_tick_data(self):
        return self.key_tick != None

    def key(self):
        return self.key_tick if self.is_tick_data() else self.key_name
        
class ChartParser:
    """Reads a .chart file to create a Song object."""
    def __init__(self):
        self.song = None
        self.sections = {}
        
        # Parsing mode
        self.mode_difficulty = None
        self.mode_pro = None
        self.mode_bass2x = None
        
        # Parsing state
        self._chord = None
        self._flag_solo = None
        self._flag_disco = None
        self._sp_end_tick = None
        self._fill_end_tick = None
        self._fill_length = None
        
        # Ticks per quarter note
        self.resolution = None
    
    def load_sections(self, charttxt):
        """Loads the chartfile's sections from text form so they can be 
        accessed easily.
        
        To do: This can be a bit more robust (USE UNIT TESTS)
        """
        wip_section = None
        open_block = False
        for line in charttxt:
            if wip_section:
                if line.rstrip() == "{":
                    # Start a block
                    assert(not open_block)
                    open_block = True
                elif line.rstrip() == "}":
                    # End the block and assign the result
                    assert(open_block)
                    open_block = False
                    self.sections[wip_section.name] = wip_section
                    wip_section = None
                else:
                    # Continue the block and make an entry in it
                    assert(open_block)
                    lhs = line.split('=')[0].strip()
                    rhs = line.split('=')[1].strip()
                    
                    dataentry = ChartDataEntry(lhs, rhs)
                    
                    # Multiple entries on the same key can stack
                    if dataentry.key() in wip_section.data:
                        wip_section.data[dataentry.key()].append(dataentry)
                    else:
                        wip_section.data[dataentry.key()] = [dataentry]
            else:
                assert(not open_block)
                # start a new section
                wip_section = ChartSection()
                wip_section.name = re.findall(r'\[.*\]', line)[0][1:-1]
    
    def optype(self, entry, tick):
        match entry:
            case ChartDataEntry(discoflip_enable=True):
                return ('pre', self.op_disco, True)
            case ChartDataEntry(discoflip_disable=True):
                return ('pre', self.op_disco, False)
            case ChartDataEntry(tempo_bpm=bpm) if bpm is not None:
                return ('time', self.op_tempo, tick, bpm)
            case ChartDataEntry(ts_numerator=n, ts_denominator=d) if n:
                return ('time', self.op_timesig, tick, n, d)
            case ChartDataEntry(solo_start=True):
                return ('pre', self.op_solo, True)
            case ChartDataEntry(solo_end=True):
                return ('pre', self.op_solo, False)
            case ChartDataEntry(notevalue=0):
                return ('notes', self.op_note, hydata.NoteColor.KICK)
            case ChartDataEntry(notevalue=1):
                return ('notes', self.op_note, hydata.NoteColor.RED)
            case ChartDataEntry(notevalue=2):
                return ('notes', self.op_note, hydata.NoteColor.YELLOW)
            case ChartDataEntry(notevalue=3):
                return ('notes', self.op_note, hydata.NoteColor.BLUE)
            case ChartDataEntry(notevalue=4):
                return ('notes', self.op_note, hydata.NoteColor.GREEN)
            case ChartDataEntry(notevalue=32) if self.mode_bass2x:
                return ('notes', self.op_2x)
            case ChartDataEntry(notevalue=34):
                return ('note_mods', self.op_accent, hydata.NoteColor.RED)
            case ChartDataEntry(notevalue=35):
                return ('note_mods', self.op_accent, hydata.NoteColor.YELLOW)
            case ChartDataEntry(notevalue=36):
                return ('note_mods', self.op_accent, hydata.NoteColor.BLUE)
            case ChartDataEntry(notevalue=37):
                return ('note_mods', self.op_accent, hydata.NoteColor.GREEN)
            case ChartDataEntry(notevalue=40):
                return ('note_mods', self.op_ghost, hydata.NoteColor.RED)
            case ChartDataEntry(notevalue=41):
                return ('note_mods', self.op_ghost, hydata.NoteColor.YELLOW)
            case ChartDataEntry(notevalue=42):
                return ('note_mods', self.op_ghost, hydata.NoteColor.BLUE)
            case ChartDataEntry(notevalue=43):
                return ('note_mods', self.op_ghost, hydata.NoteColor.GREEN)
            case ChartDataEntry(notevalue=66) if self.mode_pro:
                return ('note_mods', self.op_cymbal, hydata.NoteColor.YELLOW)
            case ChartDataEntry(notevalue=67) if self.mode_pro:
                return ('note_mods', self.op_cymbal, hydata.NoteColor.BLUE)
            case ChartDataEntry(notevalue=68) if self.mode_pro:
                return ('note_mods', self.op_cymbal, hydata.NoteColor.GREEN)
            case ChartDataEntry(phrasevalue=2, phraselength=length):
                return ('pre', self.op_sp_start, tick + length)
            case ChartDataEntry(phrasevalue=64, phraselength=length):
                return ('pre', self.op_fillstart, tick + length, length)
            case _:
                return (None, None)
    
    def op_disco(self, is_on):
        self._flag_disco = is_on
    
    def op_tempo(self, tick, bpm):
        self.song.bpm_changes[tick] = bpm
    
    def op_timesig(self, tick, numerator, denominator):
        self.song.tpm_changes[tick] = self.song.tick_resolution * numerator * 4 // denominator
    
    def op_fillstart(self, endtick, length):
        self._fill_end_tick = endtick
        self._fill_length = length
    
    def op_fillend(self, length):
        self.song.sequence[-1].activation_length = length
    
    def op_sp_start(self, endtick):
        self._sp_end_tick = endtick
    
    def op_sp_end(self):
        self.song.sequence[-1].flag_sp = True
    
    def op_solo(self, is_on):
        self._flag_solo = is_on
    
    def op_note(self, color):
        self._chord.add_note(color)
    
    def op_2x(self):
        self._chord.add_2x()
    
    def op_accent(self, color):
        self._chord.apply_accent(color)
    
    def op_ghost(self, color):
        self._chord.apply_ghost(color)
    
    def op_cymbal(self, color):
        self._chord.apply_cymbal(color)
    
    def push_timestamp(self, tick, entries):
        # Process all the events that happened simultaneously on this tick.
        # Because we've collected the events, we can easily do them in
        # whichever order as configured in the optype function
        self._chord = hydata.Chord()
        
        ops = [self.optype(entry, tick) for entry in entries]
        
        # ops that come from ticks elapsing, not their own entries
        if self._sp_end_tick is not None and tick >= self._sp_end_tick:
            ops.append(('pre', self.op_sp_end))
            self._sp_end_tick = None
        
        if self._fill_end_tick is not None and tick >= self._fill_end_tick:
            ops.append(('post', self.op_fillend, self._fill_length))
            self._fill_end_tick = None
            self._fill_length = None
        
        # 'pre': Effects that apply before the timestamp is added, such as a 
        #   'previous chord' mechanic that doesn't include this chord, or
        #   flags that change the type of note that's about to be created.
        # 'notes': The actual notes being created.
        # 'note_mods': Modifiers for a pre-existing note
        for phase in ['pre', 'notes', 'note_mods']:
            for op_phase, op, *op_args in ops:
                if op_phase == phase:
                    try:
                        op(*op_args)
                    except hymisc.ChartFileError:
                        pass
        
        # Append to the Song
        if self._chord.count():
            timestamp = SongTimestamp()
            timestamp.chord = self._chord
            timestamp.timecode = hymisc.Timecode(tick, self.song)
            timestamp.flag_solo = self._flag_solo
            if self._flag_disco:
                timestamp.chord.apply_disco_flip()
                
            self.song.sequence.append(timestamp)
            self._chord = None
            
        # 'post': Effects that apply after the timestamp is added, such as a
        #   'previous chord' mechanic that includes this chord
        for op_phase, op, *op_args in ops:
            if op_phase == 'post':
                try:
                    op(*op_args)
                except hymisc.ChartFileError:
                    pass
        
    def parsefile(self, filename, m_difficulty, m_pro, m_bass2x):
        """After calling this, self.song will reflect the input filename.
        Must be .chart.
        """
        # Load from txt
        with open(filename, mode='r') as charttxt:
            self.load_sections(charttxt)
        
        # Parser settings
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x
        
        # Initialize Song
        tick_resolution = int(self.sections["Song"].data["Resolution"][0].property)
        self.song = Song(tick_resolution)
        
        # Map tempo and time signatures
        for entry_tick, entries in self.sections["SyncTrack"].data.items():
            for entry in entries:
                op_phase, op, *op_args = self.optype(entry, entry_tick)
                if op_phase == 'time':
                    op(*op_args)
        
        self._flag_solo = False
        self._flag_disco = False
        
        # Add from the drum chart to our Song
        for tick, tick_entries in self.sections["ExpertDrums"].data.items():
            self.push_timestamp(tick, tick_entries)
        
        self.song.check_activations()
