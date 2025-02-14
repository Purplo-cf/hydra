import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestActMisalign(unittest.TestCase):
    """Test cases for Clone Hero's activation phrase misalignment fixing:
    An activation phrase typically "falls back" to find its activation chord
    if there isn't a chord exactly at the phrase's end, but it can actually
    also "fall forward" up to 6 ticks.
    
    If both are possible, the closer one is used.
    If there's a tie, the ahead note takes precedence.
    """
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_act_misalign"])
    
    def _test_activation_note(self, chartname, has_green):
        chartpath = self.chartfolder + os.sep + chartname
        record = hyutil.analyze_chart(
            chartpath,
            'expert', True, True,
            'scores', 0
        )
        act_chord = record.paths[0].activations[0].frontend.chord
        self.assertEqual(act_chord[hydata.NoteColor.GREEN] is not None, has_green)
    
    
    def test_control(self):
        self._test_activation_note("control.chart", True)
        
    def test_6t(self):
        self._test_activation_note("-6t.chart", True)
    
    def test_7t(self):
        self._test_activation_note("-7t.chart", False)
    
    def test_89t(self):
        self._test_activation_note("+89t.chart", True)
    
    def test_90t(self):
        self._test_activation_note("+90t.chart", False)
    
    def test_fast_6t(self):
        self._test_activation_note("fast -6t.chart", True)
    
    def test_fast_7t(self):
        self._test_activation_note("fast -7t.chart", False)
    
    def test_short_6t(self):
        self._test_activation_note("short -6t.chart", True)
    
    def test_short_7t(self):
        self._test_activation_note("short -7t.chart", False)
    
    def test_timesig_6t(self):
        self._test_activation_note("timesig -6t.chart", True)
    
    def test_timesig_7t(self):
        self._test_activation_note("timesig -7t.chart", False)
    
    def test_tie(self):
        self._test_activation_note("6t tie.chart", True)
    
    def test_pre_closer(self):
        self._test_activation_note("4t pre closer.chart", False)
    
    def test_post_closer(self):
        self._test_activation_note("4t post closer.chart", True)
    
    