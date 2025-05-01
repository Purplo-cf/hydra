import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestMisc(unittest.TestCase):
    """Cement any problem songs as regression tests when their problems get fixed."""
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_misc"])
    
    def best_path(self, chartname):
        return hyutil.analyze_chart(
            self.chartfolder + os.sep + chartname,
            'expert', True, True,
            'scores', 0
        ).paths[0]
    
    def _test_pathstr(self, chartname, s_pathstr):
        path = self.best_path(chartname)
        self.assertEqual(path.pathstring(), s_pathstr)
        
    def test_path_hellabove(self):
        self._test_pathstr("hellabove.mid", "1 2")
        
    def test_path_arithmophobia(self):
        self._test_pathstr("arithmophobia.mid", "5 9+ 0")
