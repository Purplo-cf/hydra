import mido
import re
import hashlib

from . import hydata
from . import hymisc


class SongTimestamp:
    """Associates a timecode with the notes, time signature, tempo, and other
    gameplay things active at that point in time."""
    def __init__(self):      
        self.timecode = None
        self.chord = None
        
        self.flag_solo = False
        self.flag_sp = False
        self.activation_length = None
        
        self.tempo = None
        self.ts_numerator = None
        self.ts_denominator = None

    def has_activation(self):
        return self.activation_length is not None


class Song:
    """The structure for charts that have been loaded in. A sequence of
    timestamps, plus tempo/meter changes.
    """
    def __init__(self):
        self.sequence = []
        
        """This song's conversions from ticks to any other time unit."""
        self.tick_resolution = None # Ticks per beat, song-wide
        self.tpm_changes = {} # {Tick: Ticks per measure}. (Time signature)
        self.bpm_changes = {} # {Tick: Beats per minute}. (Tempo)
        
        """Stub for song-wide analysis."""
        self.features = []
    
    def check_activations(self):
        """ If a chart has no drum fills, add them in like Clone Hero would.
        Rule: Add at m3.1.0 + n*(4m), 1/2 m long, if there's a chord there.
        To do: More testing around this rule. Unit tests.
        """
        if all([not ts.has_activation() for ts in self.sequence]):
            self.features.append('Auto-Generated Fills')
            ts_numerator = self.sequence[0].ts_numerator
            ts_denominator = self.sequence[0].ts_denominator
            for timestamp in self.sequence:
                assert(timestamp.ts_numerator != None)
                assert(timestamp.ts_denominator != None)
                if (
                    timestamp.timecode.is_measure_start()
                    and timestamp.timecode.measure_beats_ticks[0] % 4 == 3
                    and timestamp.chord
                    and not timestamp.flag_sp
                ):
                    beats = ts_numerator // 2 * 4 // ts_denominator
                    timestamp.activation_length = self.tick_resolution * beats
                ts_numerator = timestamp.ts_numerator
                ts_denominator = timestamp.ts_denominator

    def start_time(self):
        return hymisc.Timecode(0, self)


class MidiParser:
    """Converts midi charts to hydra's Song object."""
    def __init__(self):
        self.song = None
        
        # The current timestamp, which due to a few retroactive modifiers isn't fully determined until we've hit the next chord in a future timestamp.
        # Some useless midi timepoints (like ones that only have note-offs for drum notes) won't become timestamps.
        self.timestamp = SongTimestamp()
        
        self.elapsed_time = 0.0
        self.elapsed_measures = 0.0
        self.elapsed_beats = 0.0
        self.elapsed_ticks = 0
        self.ticks_per_beat = None
        
        # A fill ended, so the next chord will be marked as an activation (but we need to wait for it to be finalized).
        self.fill_primed = False
        # We started a fill, so we expect an activation timestamp in the future and when we set it we'll save this info to it.
        self.fill_start_time = None
        self.fill_start_measure = None
        
        # The next encountered chord will cause the current timestamp to finalize. 
        self.push_primed = False
        
        # Current state of markers that apply to all chords in their range
        self.tom_flags = {98:False, 99:False, 100:False}
        self.solo_active = False
        self.disco_flip = False
        
        # Current state of params that affect time
        self.tempo = None
        self.ts_numerator = 4
        self.ts_denominator = 4
    
    def push_timestamp(self):
        assert(self.song != None)
        assert(self.timestamp != None)
        assert(self.push_primed)
        
        self.push_primed = False
        
        if self.timestamp.chord == None or self.timestamp.chord.count() == 0:
            assert(len(self.song.sequence) == 0)
            self.timestamp = SongTimestamp()
            return
        
        # Add timestamp to song
        self.song.sequence.append(self.timestamp)
        
        self.timestamp = SongTimestamp()
        
    def read_message(self, msg):
        
        # Message has moved time forward.
        if msg.time != 0:
            
            if not self.push_primed:
                # Timestamp will push when we hit the next note.
                self.push_primed = True
                
                # Apply fleeting modifiers like toms, solo, and disco flip.
                if self.timestamp.chord:
                    if self.mode_pro:
                        self.timestamp.chord.apply_cymbals(not self.tom_flags[98], not self.tom_flags[99], not self.tom_flags[100])
                    
                    if self.disco_flip:
                        self.timestamp.chord.apply_disco_flip()
                self.timestamp.flag_solo = self.solo_active
                
                self.timestamp.timecode = hymisc.Timecode(self.elapsed_ticks, None)
                
                self.timestamp.tempo = self.tempo
                self.timestamp.ts_numerator = self.ts_numerator
                self.timestamp.ts_denominator = self.ts_denominator
                
                # Timestamps if hit as early/late as possible.
                # Will use the time signature at the timestamp - there will be slight error if the time signature changes too close to it.
                max_offset_seconds = 0.070
                ticks_per_measure = self.ticks_per_beat * self.ts_numerator * (4/self.ts_denominator)
                max_offset_measures = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / ticks_per_measure
                
                max_offset_beats = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / self.ticks_per_beat
                
            if self.fill_primed:
                self.timestamp.activation_length = self.elapsed_ticks - self.fill_start_tick
                self.fill_primed = False
                self.fill_start_time = None
                self.fill_start_measure = None
                self.fill_start_beat = None
                self.fill_start_tick = None
                
            # Update time.
            ticks_per_measure = self.ticks_per_beat * self.ts_numerator * (4/self.ts_denominator)
            msg_measures = mido.second2tick(msg.time, self.ticks_per_beat, self.tempo) / ticks_per_measure
            
            self.elapsed_time += msg.time
            self.elapsed_measures += msg_measures
            self.elapsed_beats += mido.second2tick(msg.time, self.ticks_per_beat, self.tempo) / self.ticks_per_beat
            self.elapsed_ticks += mido.second2tick(msg.time, self.ticks_per_beat, self.tempo)
        
        # Text marker to begin disco flip - interpret Red as YellowCym and YellowCym as Red
        if msg.type == 'text' and re.fullmatch(r'\[mix.3.drums\d?d\]', msg.text):
            self.disco_flip = True

        # Text marker to end disco flip
        if msg.type == 'text' and re.fullmatch(r'\[mix.3.drums\d?\]', msg.text):
            self.disco_flip = False
        
        # Current tempo
        if msg.type in ['set_tempo']:
            self.tempo = msg.tempo
            
            self.song.bpm_changes[self.elapsed_ticks] = 60000000 / msg.tempo
            
        # Time signature
        if msg.type in ['time_signature']:
            self.ts_numerator = msg.numerator
            self.ts_denominator = msg.denominator
            
            # ticks/beat * subdivisions/measure * beats/subdivision = ticks/measure
            self.song.tpm_changes[self.elapsed_ticks] = self.ticks_per_beat * self.ts_numerator * 4 // self.ts_denominator
            
        if msg.type in ['note_on', 'note_off']:
            note_started = msg.type == 'note_on' and msg.velocity > 0
            note_ended = msg.type == 'note_off' or msg.type == 'note_on' and msg.velocity == 0
            
            match msg.note:
                
                # Fill - endpoint marks an activation chord
                case 120:
                    if note_started:
                        # The fill won't appear if it starts too close to gaining 50% sp (or else it'd risk being already in view)
                        self.fill_start_time = self.elapsed_time
                        self.fill_start_measure = 1 + self.elapsed_measures
                        self.fill_start_beat = self.elapsed_beats
                        self.fill_start_tick = self.elapsed_ticks
                    if note_ended:
                        # When time advances, the current chord can be marked as an activation.
                        self.fill_primed = True
                        
                # SP phrase - endpoint modifies the current chord
                case 116: 
                    # Only bother with the ends of phrases
                    # To do: like fills, weirdness if sp marker ends at the same time as a new chord
                    if note_ended:
                        self.timestamp.flag_sp = True

                # Solo marker
                case 103:
                    if note_ended:
                        self.solo_active = False
                    if note_started:
                        self.solo_active = True
                    
                # Tom markers
                case 110 | 111 | 112:
                    if note_ended:
                        self.tom_flags[msg.note - 12] = False
                    if note_started:
                        self.tom_flags[msg.note - 12] = True
                        
                # Notes
                case 95 | 96 | 97 | 98 | 99 | 100:
                    ignored_2x = msg.note == 95 and not self.mode_bass2x
                    if note_started and not ignored_2x:
                        if self.push_primed:
                            self.push_timestamp()

                        # Add to current chord - tom status will apply later
                        if not self.timestamp.chord:
                            self.timestamp.chord = hydata.Chord()
                        self.timestamp.chord.add_from_midi(msg.note, msg.velocity)
        
    def parsefile(self, filename, m_difficulty, m_pro, m_bass2x):
        assert(filename.endswith(".mid"))
        
        mid = mido.MidiFile(filename)
        self.ticks_per_beat = mid.ticks_per_beat
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x

        # Remove other instruments while keeping events and any un-named or generic tracks
        for t in mid.tracks:
            is_nondrum_instrument = t.name.startswith("PART") and t.name != "PART DRUMS"
            is_harmony_track = t.name in ["HARM1", "HARM2", "HARM3"]
            if is_nondrum_instrument or is_harmony_track:
                t.clear()
                
        self.song = Song()
        self.song.tick_resolution = self.ticks_per_beat
        
        # Default time sig on tick 0. Will be overridden if the song has one
        self.song.tpm_changes[0] = self.ticks_per_beat * 4
        
        for m in mid:
            self.read_message(m)
        self.push_timestamp()
        
        # Replace tick-only timecodes with complete ones
        for ts in self.song.sequence:
            ts.timecode = hymisc.Timecode(ts.timecode.ticks, self.song)
        
        self.song.check_activations()
        return self.song 

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
        
        
        return (tempo, ts_numerator, ts_denominator)
        
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
        self.song = Song()
        self.mode_difficulty = m_difficulty
        self.mode_pro = m_pro
        self.mode_bass2x = m_bass2x
        
        with open(filename, mode='r') as charttxt:
            self.load_sections(charttxt)
            
        self.resolution = int(self.sections["Song"].data["Resolution"][0].property)
        self.song.tick_resolution = self.resolution
        
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
                
            timestamp.tempo, timestamp.ts_numerator, timestamp.ts_denominator = self.meter_at_tick(tick)
            
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
        return self.song
        