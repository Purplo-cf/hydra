import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestChordCode(unittest.TestCase):
    """Test cases for initializing chords via codes (KRYBG)."""
    def setUp(self):
        pass

    def test_kick(self):
        code_chord = hydata.Chord(code='K')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.KICK] = hydata.ChordNote(
            hydata.NoteColor.KICK, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_kick_ignores_dyn(self):
        code_chord = hydata.Chord(code='K+')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.KICK] = hydata.ChordNote(
            hydata.NoteColor.KICK, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_kick_ignores_cym(self):
        code_chord = hydata.Chord(code='k')
        
        sol_chord = hydata.Chord()
        self.assertEqual(code_chord, sol_chord)
        
    def test_red(self):
        code_chord = hydata.Chord(code='R')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.RED] = hydata.ChordNote(
            hydata.NoteColor.RED, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_red_ghost(self):
        code_chord = hydata.Chord(code='R-')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.RED] = hydata.ChordNote(
            hydata.NoteColor.RED, 
            dynamictype=hydata.NoteDynamicType.GHOST, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_red_accent(self):
        code_chord = hydata.Chord(code='R+')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.RED] = hydata.ChordNote(
            hydata.NoteColor.RED, 
            dynamictype=hydata.NoteDynamicType.ACCENT, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_yellow(self):
        code_chord = hydata.Chord(code='Y')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_yellow_ghost(self):
        code_chord = hydata.Chord(code='Y-')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.GHOST, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_yellow_accent(self):
        code_chord = hydata.Chord(code='Y+')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.ACCENT, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
    
    def test_yellow_cym(self):
        code_chord = hydata.Chord(code='y')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            colortype=hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.CYMBAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_yellow_cym_ghost(self):
        code_chord = hydata.Chord(code='y-')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            colortype=hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.GHOST, 
            cymbaltype=hydata.NoteCymbalType.CYMBAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_yellow_cym_accent(self):
        code_chord = hydata.Chord(code='y+')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            colortype=hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.ACCENT, 
            cymbaltype=hydata.NoteCymbalType.CYMBAL
        )
        
        self.assertEqual(code_chord, sol_chord)
        
    def test_chord(self):
        code_chord = hydata.Chord(code='Ky+G-')
        
        sol_chord = hydata.Chord()
        sol_chord[hydata.NoteColor.KICK] = hydata.ChordNote(
            colortype=hydata.NoteColor.KICK, 
            dynamictype=hydata.NoteDynamicType.NORMAL, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        sol_chord[hydata.NoteColor.YELLOW] = hydata.ChordNote(
            colortype=hydata.NoteColor.YELLOW, 
            dynamictype=hydata.NoteDynamicType.ACCENT, 
            cymbaltype=hydata.NoteCymbalType.CYMBAL
        )
        sol_chord[hydata.NoteColor.GREEN] = hydata.ChordNote(
            colortype=hydata.NoteColor.GREEN, 
            dynamictype=hydata.NoteDynamicType.GHOST, 
            cymbaltype=hydata.NoteCymbalType.NORMAL
        )
        
        self.assertEqual(code_chord, sol_chord)
