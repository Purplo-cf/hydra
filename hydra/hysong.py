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
    """Reads a midi file to create a Song object."""
    def __init__(self):
        self.song = None
        
        # Parsing mode
        self.mode_difficulty = None
        self.mode_pro = None
        self.mode_bass2x = None
        
        # Parsing state
        self._ts = None
        self._msg_buffer = None
        self._flag_solo = None
        self._flag_cymbals = None
        self._flag_disco = None
        self._fill_start_tick = None

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
            
        # Interpret midi message for which procedure to return
        match msg:
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
        note = self._ts.chord.add_note(color)
        note.dynamictype = dynamic
        if color.allows_cymbals() and self.mode_pro:
            note.cymbaltype = self._flag_cymbals[color]
        note.is2x = is2x
    
    def push_timestamp(self, tick):
        """Process all the events that happened simultaneously on this tick.
        
        Because we've collected the events, we can easily do them in whichever
        order as configured in the optype function.
        
        """
        self._ts = SongTimestamp()
        self._ts.chord = hydata.Chord()
        
        ops = [self.optype(msg, tick) for msg in self._msg_buffer]
        
        # 'pre': Effects that apply before the timestamp is added, such as a 
        #   'previous chord' mechanic that doesn't include this chord, or
        #   flags that change the type of note that's about to be created.
        # 'notes': The actual notes being created.
        for phase in ['pre', 'notes']:
            for op_phase, op, *op_args in ops:
                if op_phase == phase:
                    op(*op_args)
              
        if self._ts.chord.count():
            self._ts.flag_solo = self._flag_solo
            if self._flag_disco:
                self._ts.chord.apply_disco_flip()
            self._ts.timecode = hymisc.Timecode(tick, self.song)
            self.song.sequence.append(self._ts)
            
        # 'post': Effects that apply after the timestamp is added, such as a
        #   'previous chord' mechanic that includes this chord
        for op_phase, op, *op_args in ops:
                if op_phase == 'post':
                    op(*op_args)
            
        self._ts = None
        self._msg_buffer = []
    
    def parsefile(self, filename, m_difficulty, m_pro, m_bass2x):
        """Reads a chart file and updates self.song."""
        assert(filename.endswith(".mid"))
        mid = mido.MidiFile(filename)
        
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x

        self.song = Song(mid.ticks_per_beat)

        elapsed_ticks = 0
        for msg in mid.tracks[0]:
            # Look for tempo and time signature events
            elapsed_ticks += msg.time
            op_phase, op, *op_args = self.optype(msg, elapsed_ticks)
            if op_phase == 'time':
                op(*op_args)
        
        for track in mid.tracks:
            if track.name == "PART DRUMS":
                # Drum track (won't have tempo / time signatures)
                elapsed_ticks = 0
                self._msg_buffer = []
                self._flag_solo = False
                self._flag_disco = False
                self._flag_cymbals = {
                    hydata.NoteColor.GREEN: hydata.NoteCymbalType.CYMBAL,
                    hydata.NoteColor.BLUE: hydata.NoteCymbalType.CYMBAL,
                    hydata.NoteColor.YELLOW: hydata.NoteCymbalType.CYMBAL
                }
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
    
    def __init__(self):
        self.name = None
        self.data = {}

class ChartDataEntry:
    
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
        
        # Interpret valuestr
        tokens = valuestr.split()
        if not self.is_tick_data():
            # Single value for a named property (i.e. Song properties)
            try:
                self.property = int(valuestr)
            except ValueError:
                self.property = valuestr
        elif tokens[0] == "TS":
            # Time signature
            assert(2 <= len(tokens) <= 3)
            self.ts_numerator = int(tokens[1])
            self.ts_denominator = 2**int(tokens[2]) if len(tokens) == 3 else 4
        elif tokens[0] == "B":
            # BPM
            assert(len(tokens) == 2)
            self.tempo_bpm = int(tokens[1]) / 1000.0
        elif tokens[0] == "E":
            # Event
            lyric_events = ['lyric', 'phrase_start', 'phrase_end']
            anim_events = ['Default', 'crowd_normal', 'crowd_clap', 'crowd_noclap', 'crowd_intense', 'crowd_realtime', 'crowd_mellow', '[idle]', '[idle_realtime]', '[idle_intense]', '[map_HandMap_Default]', '[map_HandMap_DropD]', '[map_HandMap_DropD2]', '[map_StrumMap_Default]', '[map_StrumMap_Pick]', '[play]', '[intense]']
            structure_events = ['section',  'music_start', 'music_end', 'end']
            if tokens[1].strip('"') in lyric_events + anim_events + structure_events:
                # Various events we have no use for
                self.textevent = ' '.join(tokens[1:])
            elif tokens[1] == "solo":
                self.solo_start = True
            elif tokens[1] == "soloend":
                self.solo_end = True
            elif re.fullmatch(r'\[mix.\d.drums\d?\]', tokens[1]):
                self.discoflip_disable = True
                self.discoflip_difficulty = tokens[1][5]
            elif re.fullmatch(r'\[mix.\d.drums\d?d\]', tokens[1]):
                self.discoflip_enable = True
                self.discoflip_difficulty = tokens[1][5]
            else:
                raise NotImplementedError(f"Unknown Event data value in entry: {self.key()} = {valuestr}")
        elif tokens[0] == "N":
            # Note
            assert(len(tokens) == 3)
            self.notevalue = int(tokens[1])
            self.notelength = int(tokens[2])
        elif tokens[0] == "S":
            # Phrase (sp, activation fill, roll lane)
            assert(len(tokens) == 3)
            self.phrasevalue = int(tokens[1])
            self.phraselength = int(tokens[2])
        elif tokens[0] == "A":
            # Anchored BPM (ignored in game)
            pass
        else:
            # Ensures there isn't anything we're missing.
            raise NotImplementedError(f"Unknown data value in entry: {self.key()} = {valuestr}")

    def is_property(self):
        return self.property != None

    def is_tick_data(self):
        return self.key_tick != None

    def key(self):
        return self.key_tick if self.is_tick_data() else self.key_name
        
class ChartParser:
    
    def __init__(self):
        self.song = None
        self.sections = {}
        
        # Ticks per quarter note
        self.resolution = None
        
    # Loads the chartfile's sections from text form so they can be accessed easily.
    # Also converts from text values to more useful structures.
    # Also combines multi values within the same section.
    def load_sections(self, charttxt):
        wip_section = None
        block_depth = 0 # Should only be 0 or 1...
        for line in charttxt:
            if wip_section:
                if line.rstrip() == "{":
                    assert(block_depth == 0)
                    block_depth = 1
                elif line.rstrip() == "}":
                    assert(block_depth == 1)
                    block_depth = 0
                    self.sections[wip_section.name] = wip_section
                    wip_section = None
                else:
                    assert(block_depth == 1)
                    lhs = line.split('=')[0].strip()
                    rhs = line.split('=')[1].strip()
                    
                    dataentry = ChartDataEntry(lhs, rhs)
                    
                    if dataentry.key() in wip_section.data:
                        wip_section.data[dataentry.key()].append(dataentry)
                    else:
                        wip_section.data[dataentry.key()] = [dataentry]
            else:
                assert(block_depth == 0)
                # start a new section
                wip_section = ChartSection()
                wip_section.name = re.findall(r'\[.*\]', line)[0][1:-1]
            
            
    # Tick from start of song -> Time from start of song
    def tick_to_time(self, tick):
        current_time = 0.0
        current_tick = 0
        current_bpm = 120
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            
            if entry_tick >= tick:
                current_time += (tick - current_tick) / self.resolution / current_bpm * 60.0
                return current_time
            
            current_time += (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    current_bpm = entry.tempo_bpm
                    
        assert(tick > current_tick)
        current_time += (tick - current_tick) / self.resolution / current_bpm * 60.0
        return current_time
        
    # Time from start of song -> Measure from start of song (first measure is 1)
    def time_to_measure(self, time):
        current_time = 0.0
        current_tick = 0
        current_bpm = 120
        current_measure = 1
        current_ts_numerator = 4
        current_ts_denominator = 4
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            entry_time = current_time + (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            if entry_time >= time:
                current_measure += (time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
                return current_measure
            
            current_measure += (entry_time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
            current_time += (entry_tick - current_tick) / self.resolution / current_bpm * 60.0
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    current_bpm = entry.tempo_bpm
                    
                if entry.ts_numerator != None:
                    current_ts_numerator = entry.ts_numerator
                
                if entry.ts_denominator != None:
                    current_ts_denominator = entry.ts_denominator
                    
        assert(time > current_time)
        current_measure += (time - current_time) / 60.0 * current_bpm / (current_ts_numerator * (4/current_ts_denominator))
        return current_measure
            
    def meter_at_tick(self, tick):
        tempo = 120
        ts_numerator = 4
        ts_denominator = 4
        
        current_tick = 0
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            if entry_tick > tick:
                break
            
            current_tick = entry_tick
            
            for entry in entries:
                if entry.tempo_bpm != None:
                    tempo = entry.tempo_bpm
                    
                if entry.ts_numerator != None:
                    ts_numerator = entry.ts_numerator
                
                if entry.ts_denominator != None:
                    ts_denominator = entry.ts_denominator
        
        
        return ts_denominator
        
    def tick_timings(self, tick):
        ts_numerator = 4
        ts_denominator = 4
        
        handled_ticks = 0
        acc_beat = 0
        acc_measure = 0
        beats = 0
        measures = 0
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            if entry_tick > tick:
                break
            
            new_ticks = entry_tick - handled_ticks

            acc_beat += new_ticks
            while acc_beat >= self.resolution:
                acc_beat -= self.resolution
                beats += 1
                acc_measure += 1
                
            while acc_measure >= ts_numerator:
                acc_measure -= ts_numerator
                measures += 1
            
            handled_ticks = entry_tick
            
            for entry in entries:
                    
                if entry.ts_numerator != None:
                    ts_numerator = entry.ts_numerator
                
                if entry.ts_denominator != None:
                    ts_denominator = entry.ts_denominator
        
        new_ticks = tick - handled_ticks
        acc_beat += new_ticks
        while acc_beat >= self.resolution:
            acc_beat -= self.resolution
            beats += 1
            acc_measure += 1
            
        while acc_measure >= ts_numerator:
            acc_measure -= ts_numerator
            measures += 1
        
        return ((beats, acc_beat), (measures, acc_measure * self.resolution + acc_beat))
            
            
    def timing_maps(self):
        ts_numerator = 4
        ts_denominator = 4
        current_ticks_per_measure = None
        mm = {}
        
        tempo = None
        tm = {}
        for entry_tick,entries in self.sections["SyncTrack"].data.items():
            
            for entry in entries:        
                if entry.ts_numerator != None:
                    ts_numerator = entry.ts_numerator
                    
                    # ticks/beat * subdivisions/measure * beats/subdivision = ticks/measure
                    update = self.resolution * ts_numerator * 4 // ts_denominator
                    if current_ticks_per_measure != update:
                        current_ticks_per_measure = update
                        mm[entry_tick] = current_ticks_per_measure
                
                if entry.ts_denominator != None:
                    ts_denominator = entry.ts_denominator
                    
                    # ticks/beat * subdivisions/measure * beats/subdivision = ticks/measure
                    update = self.resolution * ts_numerator * 4 // ts_denominator
                    if current_ticks_per_measure != update:
                        current_ticks_per_measure = update
                        mm[entry_tick] = current_ticks_per_measure
            
                if entry.tempo_bpm != None and entry.tempo_bpm != tempo:
                    tempo = entry.tempo_bpm
                    
                    tm[entry_tick] = tempo
            
        return (mm, tm)
            
    def parsefile(self, filename, m_difficulty, m_pro, m_bass2x):
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x
        
        with open(filename, mode='r') as charttxt:
            self.load_sections(charttxt)
            
        self.resolution = int(self.sections["Song"].data["Resolution"][0].property)
        self.song = Song(self.resolution)
        
        self.song.tpm_changes, self.song.bpm_changes = self.timing_maps()
        
        solo_on = False

        sp_phrase_endtick = None
        fill_endtick = None
        
        # Loop over the different ticks in the drum chart where things happen
        for tick,tick_entries in self.sections["ExpertDrums"].data.items():
            
            timestamp = SongTimestamp()
            timestamp.chord = hydata.Chord()
            timestamp.timecode = hymisc.Timecode(tick, self.song)
            
            timestamp.flag_solo = solo_on
            # Loop over the things happening on this tick
            # Sort note values ascending to make the order of adding/modifying notes completely predictable
            for tick_entry in sorted(tick_entries, key=lambda e: e.notevalue if e.notevalue != None else -1):
                assert(tick_entry.is_tick_data())
                
                if tick_entry.solo_start == True:
                    assert(not solo_on)
                    solo_on = True
                    
                    # We passed the normal spot where solo_on is applied, but we want to include this tick's chord in the solo.
                    timestamp.flag_solo = True
                
                if tick_entry.solo_end == True:
                    assert(solo_on)
                    solo_on = False
                
                if tick_entry.notevalue != None:
                    match tick_entry.notevalue:
                        case 0:
                            # Kick note
                            timestamp.chord.add_note(hydata.NoteColor.KICK)
                        case 1:
                            # Red note
                            timestamp.chord.add_note(hydata.NoteColor.RED)
                        case 2:
                            # Yellow note
                            timestamp.chord.add_note(hydata.NoteColor.YELLOW)
                        case 3:
                            # Blue note
                            timestamp.chord.add_note(hydata.NoteColor.BLUE)
                        case 4:
                            # Green note
                            timestamp.chord.add_note(hydata.NoteColor.GREEN)
                        case 32:
                            # 2x Kick note
                            if self.mode_bass2x:
                                timestamp.chord.add_2x()
                        case 34:
                            # Red accent
                            timestamp.chord.apply_accent(hydata.NoteColor.RED)
                        case 35:
                            # Yellow accent
                            timestamp.chord.apply_accent(hydata.NoteColor.YELLOW)
                        case 36:
                            # Blue accent
                            timestamp.chord.apply_accent(hydata.NoteColor.BLUE)
                        case 37:
                            # Green accent
                            timestamp.chord.apply_accent(hydata.NoteColor.GREEN)
                        case 40:
                            # Red ghost
                            timestamp.chord.apply_ghost(hydata.NoteColor.RED)
                        case 41:
                            # Yellow ghost
                            timestamp.chord.apply_ghost(hydata.NoteColor.YELLOW)
                        case 42:
                            # Blue ghost
                            timestamp.chord.apply_ghost(hydata.NoteColor.BLUE)
                        case 43:
                            # Green ghost
                            timestamp.chord.apply_ghost(hydata.NoteColor.GREEN)
                        case 66:
                            # Yellow cymbal
                            if self.mode_pro:
                                timestamp.chord.apply_cymbal(hydata.NoteColor.YELLOW)
                        case 67:
                            # Blue cymbal
                            if self.mode_pro:
                                timestamp.chord.apply_cymbal(hydata.NoteColor.BLUE)
                        case 68:
                            # Green cymbal
                            if self.mode_pro:
                                timestamp.chord.apply_cymbal(hydata.NoteColor.GREEN)
                        case _:
                            raise NotImplementedError(f"Unknown note {tick_entry.notevalue}")
                
                if tick_entry.phrasevalue != None:
                    match tick_entry.phrasevalue:
                        case 2:
                            # SP phrase start
                            assert(sp_phrase_endtick == None)
                            sp_phrase_endtick = tick + tick_entry.phraselength
                        case 64:
                            # Fill / activation start
                            assert(fill_endtick == None)
                            fill_endtick = tick + tick_entry.phraselength
                            fill_ticklength = tick_entry.phraselength
                        case 65:
                            # Single roll marker
                            pass 
                        case 66:
                            # Double roll marker
                            pass
                        case _:
                            raise NotImplementedError(f"Unknown phrase {tick_entry.phrasevalue}, length {tick_entry.phraselength}")
                
            
            # to do this could be a great way to re-implement the retroactive behavior in the midi parser
            if sp_phrase_endtick != None and tick >= sp_phrase_endtick:
                self.song.sequence[-1].flag_sp = True
                sp_phrase_endtick = None
            
            if timestamp.chord.count() > 0:
                self.song.sequence.append(timestamp)
                
            # Fills apply to the chord on the end tick, if present, so this check happens after adding the timestamp.
            if fill_endtick != None and tick >= fill_endtick:
                self.song.sequence[-1].activation_length = fill_ticklength
                fill_endtick = None
                fill_ticklength = None
        
        self.song.check_activations()
        