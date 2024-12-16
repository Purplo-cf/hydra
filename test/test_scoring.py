import os
import unittest
import hydra.hypath as hypath
import hydra.hyutil as hyutil

class TestScoring(unittest.TestCase):
    
    def get_testchart_or_skip(self, name):
        try:
            return self.chartnames_to_paths[name]
        except KeyError:
            self.skipTest(f"{name} not found in charts.")
            
    def get_testsolution_or_skip(self, name):
        try:
            return [r for r in self.chartnames_to_solutions[name] if r.difficulty == 'expert'][0]
        except KeyError:
            self.skipTest(f"{name} not found in solutions.")
            
    def setUp(self):
        # Get the test charts
        self.chartnames_to_paths = hyutil.discover_charts(os.sep.join(["..","_charts","test_scoring"]))        
        
        # Get the solution data
        self.chartnames_to_solutions = hyutil.load_records(os.sep.join(["..","test","solutions","test_scoring.json"]))
        
    def _test_scoring(self, name):
        chartpath = self.get_testchart_or_skip(name)
        soln_record = self.get_testsolution_or_skip(name)
        
        record = hyutil.run_chart(chartpath)
        
        path = record.paths[0]
        soln = soln_record.paths[0]
        
        self.assertEqual(path.score_base, soln.score_base)
        self.assertEqual(path.score_combo, soln.score_combo)
        self.assertEqual(path.score_sp, soln.score_sp)
        self.assertEqual(path.score_solo, soln.score_solo)
        self.assertEqual(path.score_accents, soln.score_accents)
        self.assertEqual(path.score_ghosts, soln.score_ghosts)
        
        self.assertEqual(path.optimal(), soln.optimal())
        
    def test_missed_injections(self):
        self._test_scoring("Hail The Sun - Missed Injections")
        
    def test_entertain_me(self):
      self._test_scoring("Tigran Hamasyan - Entertain Me [tomato]")
        
    def test_think_dirty_out_loud(self):
      self._test_scoring("A Lot Like Birds - Think Dirty out Loud")
        
    # def test_basescore_normal(self):
        # self._test_scoring("Test - Base Score Normal") 
        
        
