import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata

class TestSB25Filter(unittest.TestCase):
    """Regression tests for active tourney setlist. For ms filter."""
    def setUp(self):
        self.chartfolder = os.sep.join(["..","test","input","test_sb25"])
    
    def _path_passes_filter(self, path, ms_filter):
        # ms_filter is the hardest allowed ms.
        # The higher the ms_filter, the more is allowed.
        # "ms_filter == infinity" is equivalent to ms_filter is None.
        for act in path.all_activations():
            # e offset: negative is harder
            if act.is_E0() and -act.e_offset > ms_filter:
                return False
            
            for sqinout in act.sqinouts:
                if sqinout.difficulty > ms_filter:
                    return False
                
        return True
        
    def _record_contains_path(self, record, path):
        # Path strings are sufficient in this context (known to be same chart)
        return any(p.pathstring() == path.pathstring() for p in record.all_paths())
    
    def _test_filter(self, chartname):
        
        full_record = hyutil.analyze_chart(
            self.chartfolder + os.sep + chartname,
            'expert', True, True,
            'scores', 500,
            None
        )
        
        for i, ms_filter in enumerate(range(-200, 205, 50)):
            with self.subTest(i=i):
                filter_depth = 5
                
                filter_record = hyutil.analyze_chart(
                    self.chartfolder + os.sep + chartname,
                    'expert', True, True,
                    'scores', filter_depth,
                    ms_filter
                )
                
                # First path (top score) is unchanged by filtering
                self.assertEqual(
                    full_record.best_path().pathstring(),
                    filter_record.best_path().pathstring()
                )
                
                # Tracing through the full record in order and collecting paths
                # that pass the filter recreates the filter record
                filter_paths = list(filter_record.all_paths())
                filter_i = 1
                lastscore = filter_record.best_path().totalscore()
                scorelevel = 0
                for p in list(full_record.all_paths())[1:]:
                    if p.passes_ms_filter(ms_filter):
                        if p.totalscore() != lastscore:
                            self.assertLess(p.totalscore(), lastscore)
                            scorelevel += 1
                            lastscore = p.totalscore()
                        if filter_i == len(filter_paths):
                            # Done with filter list. Check that further
                            # paths that pass the filter aren't supposed to be
                            # in the filter record's depth range
                            self.assertLess(filter_depth, scorelevel)
                        else:
                            if p.pathstring() != filter_paths[filter_i].pathstring():
                                print(f"Records:")
                                fps = list(full_record.all_paths())
                                flps = list(filter_record.all_paths())
                                for i in range(len(fps)):
                                    fp = fps[i]
                                    sout = f"\t{fp.totalscore()}, {fp.difficulty()} ms: {fp.pathstring()}"
                                    
                                    if i < len(flps):
                                        flp = flps[i]
                                        sout += f"\t\t\t{flp.totalscore()}, {flp.difficulty()} ms: {flp.pathstring()}"
                                        
                                    print(sout)
                            self.assertEqual(p.pathstring(), filter_paths[filter_i].pathstring())
                            filter_i += 1

                
                # Verify the filter record was traced through fully
                self.assertEqual(filter_i, len(filter_paths))


    # T1
    
    def test_paths_howyouremindme(self):
        self._test_filter("howyouremindme.chart")
        
    def test_paths_actors(self):
        self._test_filter("actors.mid")
        
    def test_paths_pokemontheme(self):
        self._test_filter("pokemontheme.chart")
        
    def test_paths_totheend(self):
        self._test_filter("totheend.mid")
        
    def test_paths_aprilhaha(self):
        self._test_filter("aprilhaha.chart")
        
    # T2
    
    def test_paths_lunaris(self):
        self._test_filter("lunaris.chart")
        
    def test_paths_cityofocala(self):
        self._test_filter("cityofocala.mid")
        
    def test_paths_youngrobot(self):
        self._test_filter("youngrobot.mid")
        
    def test_paths_limbo(self):
        self._test_filter("limbo.mid")
        
    def test_paths_avalanche(self):
        self._test_filter("avalanche.mid")
        
    # T3
    
    def test_paths_snakeskinboots(self):
        self._test_filter("snakeskinboots.chart")
        
    def test_paths_movealong(self):
        self._test_filter("movealong.mid")
        
    def test_paths_wastingtime(self):
        self._test_filter("wastingtime.mid")
        
    def test_paths_overture1928(self):
        self._test_filter("overture1928.chart")
        
    def test_paths_allies(self):
        self._test_filter("allies.chart")
        
    # T4
    
    def test_paths_yyz(self):
        self._test_filter("yyz.mid")
        
    def test_paths_burnout(self):
        self._test_filter("burnout.mid")
        
    def test_paths_limbfromlimb(self):
        self._test_filter("limbfromlimb.chart")
        
    def test_paths_chair(self):
        self._test_filter("chair.mid")
        
    def test_paths_unbound(self):
        self._test_filter("unbound.mid")
        
    # T5
    
    def test_paths_iamallofme(self):
        self._test_filter("iamallofme.mid")
        
    def test_paths_pathkeeper(self):
        self._test_filter("pathkeeper.mid")
        
    def test_paths_whitemist(self):
        self._test_filter("whitemist.mid")
        
    def test_paths_senescence(self):
        self._test_filter("senescence.chart")
        
    def test_paths_grow(self):
        self._test_filter("grow.chart")
        
    # T6
    
    def test_paths_thankyoupain(self):
        self._test_filter("thankyoupain.chart")
        
    def test_paths_87(self):
        self._test_filter("87.chart")
        
    def test_paths_bledtobefree(self):
        self._test_filter("bledtobefree.mid")
        
    def test_paths_swallow(self):
        self._test_filter("swallow.mid")
        
    def test_paths_b(self):
        self._test_filter("b.mid")
        
    # T7
    
    def test_paths_blister(self):
        self._test_filter("blister.mid")
        
    def test_paths_focus(self):
        self._test_filter("focus.mid")
        
    def test_paths_thespiralingvoid(self):
        self._test_filter("thespiralingvoid.chart")
        
    def test_paths_neibolt(self):
        self._test_filter("neibolt.mid")
        
    def test_paths_handthatrocksthecradle(self):
        self._test_filter("handthatrocksthecradle.mid")
        
    # T8
    
    def test_paths_epidermis(self):
        self._test_filter("epidermis.mid")
        
    def test_paths_godzilla(self):
        self._test_filter("godzilla.chart")
        
    def test_paths_geturfreakon(self):
        self._test_filter("geturfreakon.chart")
        
    def test_paths_drjekyll(self):
        self._test_filter("drjekyll.mid")
        
    def test_paths_alchemicwebofdeceit(self):
        self._test_filter("alchemicwebofdeceit.mid")
