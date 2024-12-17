import os
import unittest
import configparser

import hydra.hypath as hypath
import hydra.hyutil as hyutil
import hydra.hymisc as hymisc

class TestScoring(unittest.TestCase):
    
    def get_testchart_or_skip(self, name):
        try:
            return self.name_to_notesfile[name]
        except KeyError:
            self.skipTest(f"{name} not found in charts.")
            return None
            
    def get_testsolution_or_skip(self, name):
        solns_with_name = [r for r in self.solnrecords if r.songid == name]
        
        if len(solns_with_name) == 1:
            return solns_with_name[0]
        elif not solns_with_name:
            self.skipTest(f"{name} not found in solutions.")
            return None
        else:
            self.skipTest(f"Multiple {name} solutions found, please fix.")
            return None

    def setUp(self):
        # Get the test charts
        chartsroot = os.sep.join(["..","_charts","test_scoring"])
        charts = hyutil.discover_charts(chartsroot)        
        
        self.name_to_notesfile = {}
        for notesfile, inifile in charts:
            config = configparser.ConfigParser()
            config.read(inifile)
            
            if 'Song' in config:
                name = config['Song']['name']
            elif 'song' in config:
                name = config['song']['name']
            else:
                raise hymisc.ChartFileError()
            
            self.name_to_notesfile[name] = notesfile
        
        # Get the solution data
        solnsroot = os.sep.join(["..","test","solutions","test_scoring.json"])
        self.solnrecords = hyutil.load_records(solnsroot)
        
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
        self._test_scoring("Missed Injections")
        
    def test_entertain_me(self):
      self._test_scoring("Entertain Me")
        
    def test_think_dirty_out_loud(self):
      self._test_scoring("Think Dirty out Loud")
        
    # def test_basescore_normal(self):
        # self._test_scoring("Test - Base Score Normal") 
        
        
