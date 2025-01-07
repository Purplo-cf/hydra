import os
import unittest
import configparser
import hashlib
import json

import hydra.hypath as hypath
import hydra.hyutil as hyutil
import hydra.hymisc as hymisc
import hydra.hyrecord as hyrecord


class TestScoring(unittest.TestCase):
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_scoring"])
        
        # Get the solution data
        solnspath = os.sep.join(["..","test","solutions","test_scoring.json"])
        with open(solnspath, 'r') as jsonfile:
            self.book = json.load(jsonfile, object_hook=hyrecord.custom_json_load)
    
    def _test_scoring(self, chartname, hyhash):
        chartpath = self.chartfolder + os.sep + chartname
        record = hyutil.run_chart(chartpath, 'expert', True, True, 'scores', 0)
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
