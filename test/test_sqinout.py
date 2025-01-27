import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestSqinout(unittest.TestCase):
    """Test that the score breakdowns match between the test solution and
    the test input freshly analyzed.
    
    Any chart + score can be added as a test as long as the score is pretty
    confidently optimal AND the Clone Hero score breakdown for that optimal
    run is known.
    
    This file is for sqinout mechanics i.e. various sp backend situations.
    """
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_sqinout"])
        
        # Get the solution data
        solnspath = os.sep.join(["..","test","solutions","test_sqinout.json"])
        with open(solnspath, 'r') as jsonfile:
            self.book = json.load(jsonfile, object_hook=hydata.json_load)
    
    def _test_scoring(self, chartname, hyhash):
        chartpath = self.chartfolder + os.sep + chartname
        record = hyutil.analyze_chart(
            chartpath,
            'expert', True, True,
            'scores', 0
        )
        soln_record = self.book[hyhash]['records']['Expert Pro Drums, 2x Bass']
        
        path = record.paths[0]
        soln = soln_record.paths[0]
        
        self.assertEqual(path.score_base, soln.score_base)
        self.assertEqual(path.score_combo, soln.score_combo)
        self.assertEqual(path.score_sp, soln.score_sp)
        self.assertEqual(path.score_solo, soln.score_solo)
        self.assertEqual(path.score_accents, soln.score_accents)
        self.assertEqual(path.score_ghosts, soln.score_ghosts)
        
        self.assertEqual(path.totalscore(), soln.totalscore())
        
    def test_sqin_0ms(self):
        self._test_scoring("sqin_0ms.chart", 'a5480902a492edfba92033a209afc253')
        
    def test_sqin_early(self):
        self._test_scoring("sqin_early.chart", '1739d51f18dbc5701a3e52d43c9fa6ef')
        
    def test_sqin_late(self):
        self._test_scoring("sqin_late.chart", '405d5ae80f4499a79341a9b88a39109f')
    
    def test_sqout_0ms(self):
        self._test_scoring("sqout_0ms.chart", '0df6dd52fab41f03987a9238c9fa61d2')

    def test_sqout_early(self):
        self._test_scoring("sqout_early.chart", '68c9752a1855fb7ab28c70803c3b486e')
        
    def test_sqout_early_emptydeact(self):
        self._test_scoring("sqout_early_emptydeact.chart", '08269472b520688f05f0f2e19520da16')
        
    def test_sqout_late(self):
        self._test_scoring("sqout_late.chart", '57271d6efdaecc00d904b60b365bc8d9')

    # To do: More edge cases between SqIn/backends and SqOut/frontends.
    # Especially a frontend that is squeezed in despite being
    # before the activation chord.
