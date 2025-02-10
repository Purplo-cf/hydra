import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestAllData(unittest.TestCase):
    """Test for everything in a record."""
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_alldata"])
        
        # Get the solution data
        solnspath = os.sep.join(["..","test","solutions","test_alldata.json"])
        with open(solnspath, 'r') as jsonfile:
            self.book = json.load(jsonfile, object_hook=hydata.json_load)
    
    def _test_alldata(self, chartname, hyhash, depth):
        chartpath = self.chartfolder + os.sep + chartname
        record = hyutil.analyze_chart(
            chartpath,
            'expert', True, True,
            'scores', depth
        )
        soln_record = self.book[hyhash]['records']['Expert Pro Drums, 2x Bass']
        
        self.assertEqual(record, soln_record)
        
        
    def test_ties(self):
        self._test_alldata("ties.chart", '7a9963dcaf891304e64d174b49782332', 4)
        
    def test_tappedout(self):
        self._test_alldata("tappedout.mid", '075859e5f6fbecd9cd43aa86064d5107', 4)

    def test_sugartzu(self):
        self._test_alldata("sugartzu.mid", '5999376934d319b9775b63edbdd47f38', 4)
        
    def test_dreamgenie(self):
        self._test_alldata("dreamgenie.mid", '351d260456bf2ca2dc017a38795eed6f', 4)

    def test_discog(self):
        self._test_alldata("discog.mid", '675d57a5708206690d70de3488d89bc2', 0)