import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestPathCount(unittest.TestCase):
    """Test cases for path counts."""
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_pathcount"])
    
    def _test_pathcount(self, chartname, depth, pathcount):
        chartpath = self.chartfolder + os.sep + chartname
        paths = hyutil.analyze_chart(
            chartpath,
            'expert', True, True,
            'scores', depth
        ).paths
        
        self.assertEqual(len(paths), pathcount)
    
    def test_album(self):
        self._test_pathcount('album.mid', 10, 704)
