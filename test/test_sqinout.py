import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestSqinout(unittest.TestCase):
    """Tests for sqinout mechanics i.e. various sp backend situations."""
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_sqinout"])
    
    def _test_scoring(
        self, chartname,
        s_base, s_combo, s_sp, s_solo, s_accents, s_ghosts, s_total
    ):
        chartpath = self.chartfolder + os.sep + chartname
        path = hyutil.analyze_chart(
            chartpath,
            'expert', True, True,
            'scores', 0
        ).paths[0]
        
        self.assertEqual(path.score_base, s_base)
        self.assertEqual(path.score_combo, s_combo)
        self.assertEqual(path.score_sp, s_sp)
        self.assertEqual(path.score_solo, s_solo)
        self.assertEqual(path.score_accents, s_accents)
        self.assertEqual(path.score_ghosts, s_ghosts)
        
        self.assertEqual(path.totalscore(), s_total)
        
    def test_sqin_0ms(self):
        self._test_scoring(
            "sqin_0ms.chart",
            1900, 2850, 3200, 0, 0, 0, 7950
        )
        
    def test_sqin_early(self):
        self._test_scoring(
            "sqin_early.chart",
            2200, 3750, 3950, 0, 0, 0, 9900
        )
        
    def test_sqin_late(self):
        self._test_scoring(
            "sqin_late.chart",
            2200, 3750, 3950, 0, 0, 0, 9900
        )
    
    def test_sqout_0ms(self):
        self._test_scoring(
            "sqout_0ms.chart",
            2150, 3600, 4200, 0, 0, 0, 9950
        )

    def test_sqout_early(self):
        self._test_scoring(
            "sqout_early.chart",
            2200, 3750, 4500, 0, 0, 0, 10450
        )
        
    def test_sqout_early_emptydeact(self):
        self._test_scoring(
            "sqout_early_emptydeact.chart",
            2150, 3600, 4350, 0, 0, 0, 10100
        )
        
    def test_sqout_late(self):
        self._test_scoring(
            "sqout_late.chart",
            2200, 3750, 4500, 0, 0, 0, 10450
        )
