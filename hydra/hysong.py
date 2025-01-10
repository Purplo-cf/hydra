import mido
import re
import hashlib

from . import hydata
from . import hymisc

class SongTimestamp:
    
    def __init__(self):
        # Timing from start of the song
        self.time = 0.0
        self.measure = 0.0
        self.beat = 0.0
        
        # Tick from start of song
        self.tick = 0
        # Measure (int), then ticks into the measure
        self.measure_tick = (0, 0)
        # Beat (int), then ticks into the beat
        self.beat_tick = (0, 0)
        
        self.timecode = None
        
        self.beat_earlyhit = None
        self.beat_latehit = None
        
        self.measure_earlyhit = None
        self.measure_latehit = None
        
        # Notes
        self.chord = None
        
        # Flags
        self.flag_activation = False
        self.flag_solo = False
        self.flag_sp = False
        
        # to do: completely linked to flag_activation, could be simplified?
        self.activation_fill_start_beat = None
        self.activation_fill_length_ticks = None
        
        # Meter
        self.tempo = None
        self.ts_numerator = None
        self.ts_denominator = None

# Common and streamlined format for the optimizer to run through.
# The main structure is an ordered sequence of SongTimestamps.
class Song:
    
    def __init__(self):
        self.songhash = None
        
        self.sequence = []
        
        self.note_count = 0
        self.ghost_count = 0
        self.accent_count = 0
        self.solo_note_count = 0
        
        self.tick_resolution = None
        
        """The ticks where the ticks per measure / tempo changes."""
        self.tpm_changes = {}
        self.bpm_changes = {}
        
        self.generated_fills = False
    
    # If a chart has no drum fills, add them at measure 3 + 4n, half a measure long, if there's a chord there.
    # To do: The details of this rule need to be explored
    def check_activations(self):
        if all([not timestamp.flag_activation for timestamp in self.sequence]):
            self.generated_fills = True
            leadin_ts_numerator = self.sequence[0].ts_numerator
            leadin_ts_denominator = self.sequence[0].ts_denominator
            for timestamp in self.sequence:
                assert(timestamp.ts_numerator != None)
                assert(timestamp.ts_denominator != None)
                if abs(round(timestamp.measure) - timestamp.measure) < 0.00001 and (round(timestamp.measure) - 3) % 4 == 0 and timestamp.chord != None and not timestamp.flag_sp:
                    timestamp.flag_activation = True
                    timestamp.activation_fill_start_beat = timestamp.beat - (leadin_ts_numerator / 2) * (4/leadin_ts_denominator)
                    timestamp.activation_fill_length_ticks = self.tick_resolution * leadin_ts_numerator // 2 * 4 // leadin_ts_denominator
                leadin_ts_numerator = timestamp.ts_numerator
                leadin_ts_denominator = timestamp.ts_denominator

    def start_time(self):
        return hymisc.Timecode(0, self)
        
# Converts midi files to a common format for path analysis
class MidiParser:
    
    def __init__(self):
        # Song format that we're building up with timestamps
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
            
        # Update song-wide info
        self.song.note_count += self.timestamp.chord.count()
        self.song.ghost_count += self.timestamp.chord.ghost_count()
        self.song.accent_count += self.timestamp.chord.accent_count()
        if self.timestamp.flag_solo:
            self.song.solo_note_count += self.timestamp.chord.count()
        
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
                
                # The actual time stamp.
                self.timestamp.time = self.elapsed_time
                self.timestamp.measure = 1 + self.elapsed_measures
                self.timestamp.beat = self.elapsed_beats
                self.timestamp.tick = self.elapsed_ticks
                self.timestamp.measure_tick = (int(self.timestamp.measure), (self.timestamp.measure - int(self.timestamp.measure)) * self.ts_numerator * (4/self.ts_denominator) * self.ticks_per_beat)
                self.timestamp.beat_tick = (int(self.timestamp.beat), (self.timestamp.beat - int(self.timestamp.beat)) * self.ticks_per_beat)
                
                self.timestamp.tempo = self.tempo
                self.timestamp.ts_numerator = self.ts_numerator
                self.timestamp.ts_denominator = self.ts_denominator
                
                # Timestamps if hit as early/late as possible.
                # Will use the time signature at the timestamp - there will be slight error if the time signature changes too close to it.
                max_offset_seconds = 0.070
                ticks_per_measure = self.ticks_per_beat * self.ts_numerator * (4/self.ts_denominator)
                max_offset_measures = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / ticks_per_measure
                
                self.timestamp.measure_earlyhit = self.timestamp.measure - max_offset_measures
                self.timestamp.measure_latehit = self.timestamp.measure + max_offset_measures
                
                max_offset_beats = mido.second2tick(max_offset_seconds, self.ticks_per_beat, self.tempo) / self.ticks_per_beat
                self.timestamp.beat_earlyhit = self.timestamp.beat - max_offset_beats
                self.timestamp.beat_latehit = self.timestamp.beat + max_offset_beats
                
            if self.fill_primed:
                self.timestamp.flag_activation = True
                self.timestamp.activation_fill_start_beat = self.fill_start_beat
                self.timestamp.activation_fill_length_ticks = self.elapsed_ticks - self.fill_start_tick
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
        
        with open(filename, 'rb') as f:
            self.song.songhash = hashlib.file_digest(f, "md5").hexdigest()
        
        for m in mid:
            self.read_message(m)
        self.push_timestamp()
        
        for ts in self.song.sequence:
            ts.timecode = hymisc.Timecode(ts.tick, self.song)
        
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
        
        with open(filename, 'rb') as chartbin:
            self.song.songhash = hashlib.file_digest(chartbin, "md5").hexdigest()
        
        with open(filename, mode='r') as charttxt:
            self.load_sections(charttxt)
            
        self.resolution = int(self.sections["Song"].data["Resolution"][0].property)
        self.song.tick_resolution = self.resolution
        
        self.song.tpm_changes, self.song.bpm_changes = self.timing_maps()
        
        solo_on = False

        sp_phrase_endtick = None
        fill_endtick = None
        fill_starttime = None
        fill_startmeasure = None
        
        # Loop over the different ticks in the drum chart where things happen
        for tick,tick_entries in self.sections["ExpertDrums"].data.items():
            
            timestamp = SongTimestamp()
            timestamp.chord = hydata.Chord()
            
            timestamp.time = self.tick_to_time(tick)
            timestamp.measure = self.time_to_measure(timestamp.time)
            timestamp.measure_earlyhit = self.time_to_measure(timestamp.time - 0.070)
            timestamp.measure_latehit = self.time_to_measure(timestamp.time + 0.070)
            timestamp.beat = tick / self.resolution
            timestamp.tick = tick
            
            tt = self.tick_timings(tick)
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
                            assert(fill_endtick == None and fill_starttime == None and fill_startmeasure == None)
                            fill_endtick = tick + tick_entry.phraselength
                            fill_starttime = timestamp.time #self.tick_to_time(tick)
                            fill_startmeasure = timestamp.measure #self.time_to_measure(fill_starttime)
                            fill_startbeat = timestamp.beat
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
            
            if len(self.song.sequence) > 0:
                timestamp.beat_earlyhit = timestamp.beat - (0.070 / 60 * self.song.sequence[-1].tempo)
            else:
                timestamp.beat_earlyhit = timestamp.beat - (0.070 / 60 * 120)
                
            timestamp.beat_latehit = timestamp.beat + (0.070 / 60 * timestamp.tempo)
            
            # to do this could be a great way to re-implement the retroactive behavior in the midi parser
            if sp_phrase_endtick != None and tick >= sp_phrase_endtick:
                self.song.sequence[-1].flag_sp = True
                sp_phrase_endtick = None
            
            if timestamp.chord.count() > 0:
                self.song.note_count += timestamp.chord.count()
                self.song.ghost_count += timestamp.chord.ghost_count()
                self.song.accent_count += timestamp.chord.accent_count()
                if timestamp.flag_solo:
                    self.song.solo_note_count += timestamp.chord.count()
 
                self.song.sequence.append(timestamp)
                
            # Fills apply to the chord on the end tick, if present, so this check happens after adding the timestamp.
            if fill_endtick != None and tick >= fill_endtick:
                self.song.sequence[-1].flag_activation = True
                self.song.sequence[-1].activation_fill_start_beat = fill_startbeat
                self.song.sequence[-1].activation_fill_length_ticks = fill_ticklength
                fill_endtick = None
                fill_starttime = None
                fill_startmeasure = None
                fill_startbeat = None
                fill_ticklength = None
        
        self.song.check_activations()
        return self.song
        