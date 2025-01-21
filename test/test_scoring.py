import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestScoring(unittest.TestCase):
    """Test that the score breakdowns match between the test solution and
    the test input freshly analyzed.
    
    Any chart + score can be added as a test as long as the score is pretty
    confidently optimal AND the Clone Hero score breakdown for that optimal
    run is known.
    
    """
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_scoring"])
        
        # Get the solution data
        solnspath = os.sep.join(["..","test","solutions","test_scoring.json"])
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
        
    def test_missed_injections(self):
        self._test_scoring("mi.mid", 'fe04583a51eccc70c55788f5096e2947')
        
    def test_entertain_me(self):
        self._test_scoring("em.chart", '47bd79be8195bc216299c59b43b584d2')
        
    def test_think_dirty_out_loud(self):
        self._test_scoring("tdol.mid", 'a80f00cffa9dfd684373aaba03e0f467')

    def test_book(self):
        self._test_scoring("book.mid", 'eb9a1e7e9b064e8fe4d04d3e99803e46')
        
    def test_all_these_people(self):
        self._test_scoring("atp.mid", '72cc3037f114c4090550349048c650a3')