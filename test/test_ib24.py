import os
import unittest
import hydra.hypath as hypath
import hydra.hyutil as hyutil

# These are broad regression tests, not really unit tests.
# The IB24 setlist covers a wide range of cases and this tests that none of the paths have changed.
# A test failure means Hydra got something wrong, OR an improvement was found, although the latter
# is way less likely at this point. Only test note count, skips, mult squeezes, and optimal.
class TestIB24Dataset(unittest.TestCase):
    
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
        # Get the IB24 charts
        self.chartnames_to_paths = hyutil.discover_charts(os.sep.join(["..","_charts","IB24"]))        
        
        # Get the solution data
        self.chartnames_to_solutions = hyutil.load_records(os.sep.join(["..","test","solutions","test_ib24.json"]))
        
    def _test_basic_stats(self, name):
        chartpath = self.get_testchart_or_skip(name)
        soln = self.get_testsolution_or_skip(name)
        
        record = hyutil.run_chart(chartpath)
        
        self.assertEqual(record.notecount, soln.notecount)
        
        r_path = record.paths[0]
        a_path = soln.paths[0]
        self.assertEqual(len(r_path.activations), len(a_path.activations))
        for i in range(len(a_path.activations)):
            r_act = r_path.activations[i]
            a_act = a_path.activations[i]
            self.assertEqual(r_act.skips, a_act.skips, f"{r_act.timecode.measurestr()} / m{a_act.measure}")
            
            # to do: replace solution set with one that has timecodes
            self.assertEqual(r_act.timecode.measures()[0], int(a_act.measure))
            
            self.assertEqual(r_act.chord, a_act.chord)
            self.assertEqual(r_act.sp_meter, a_act.sp_meter)
            
        self.assertEqual(len(r_path.multsqueezes), len(a_path.multsqueezes))
        for i in range(len(r_path.multsqueezes)):
            r_msq = r_path.multsqueezes[i]
            a_msq = a_path.multsqueezes[i]
            self.assertEqual(r_msq.multiplier, a_msq.multiplier)
            self.assertEqual(r_msq.chord, a_msq.chord)
            #self.assertEqual(r_msq.squeezecount, a_msq.squeezecount)
            self.assertEqual(r_msq.points, a_msq.points)
        
        self.assertEqual(record.optimal(), soln.optimal())
                
    # def test_overrated(self):
       # self._test_basic_stats("Allister - Overrated")
        
    # def test_my_own_summer(self):
        # self._test_basic_stats("Deftones - My Own Summer (Shove It) [highfine]")
        
    # def test_september(self):
        # self._test_basic_stats("Earth, Wind & Fire - September")

    # def test_beg(self):
        # self._test_basic_stats("Evans Blue - Beg [highfine]")

    # def test_saying_sorry(self):
        # self._test_basic_stats("Hawthorne Heights - Saying Sorry")

    # def test_im_a_believer(self):
        # self._test_basic_stats("Smash Mouth - I_m A Believer (The Monkees cover) [highfine]")

    # def test_entertain_me(self):
        # self._test_basic_stats("Tigran Hamasyan - Entertain Me [tomato]")

    # def test_knightmare_frame(self):
        # self._test_basic_stats("Area 11 - Knightmare Frame")

    # def test_band_like_that(self):
        # self._test_basic_stats("fanclubwallet - Band Like That")

    # def test_themata(self):
        # self._test_basic_stats("Karnivool - Themata")

    # def test_jamie_all_over(self):
        # self._test_basic_stats("Mayday Parade - Jamie All Over")

    # def test_the_greater_cause(self):
        # self._test_basic_stats("Nova Charisma - The Greater Cause")

    # def test_trippin_on_a_hole_in_a_paper_heart(self):
        # self._test_basic_stats("Stone Temple Pilots - Trippin on a Hole in a Paper Heart")

    # def test_act_one_scene_one(self):
        # self._test_basic_stats("The Fall of Troy - Act One, Scene One [highfine]")

    # def test_acid_romance(self):
        # self._test_basic_stats("Alpha Wolf - Acid Romance")

    # def test_book(self):
        # self._test_basic_stats("CHON - Book (feat. Matt Garstka)")

    # def test_where_are_the_birds(self):
        # self._test_basic_stats("Good Tiger - Where Are the Birds")

    # def test_beautiful_madness(self):
        # self._test_basic_stats("Neck Deep - Beautiful Madness")

    # def test_outlive(self):
        # self._test_basic_stats("The Ghost Inside - Get What You Give - 02 - Outlive")

    # def test_deadbolt(self):
        # self._test_basic_stats("Thrice - Deadbolt")

    # def test_feast_of_fire(self):
        # self._test_basic_stats("Trivium - Feast of Fire")

    # def test_apex(self):
        # self._test_basic_stats("1.O.M. - Apex")

    # def test_think_dirty_out_loud(self):
        # self._test_basic_stats("A Lot Like Birds - Think Dirty out Loud")

    # def test_chocolate_jackalope(self):
        # self._test_basic_stats("Dance Gavin Dance - Chocolate Jackalope")

    # def test_everlong(self):
        # self._test_basic_stats("Foo Fighters - Everlong")

    # def test_missed_injections(self):
        # self._test_basic_stats("Hail The Sun - Missed Injections")

    # def test_the_good_doctor(self):
        # self._test_basic_stats("Haken - The Good Doctor")

    # def test_llama(self):
        # self._test_basic_stats("Phish - Llama")

    # def test_all_these_people(self):
        # self._test_basic_stats("sungazer - All These People")

    # def test_deception(self):
        # self._test_basic_stats("Tesseract - Deception - Concealing Fate, Pt. 2")

    # def test_someday(self):
        # self._test_basic_stats("Brandon Burkhalter - Someday")

    # def test_megalodon(self):
        # self._test_basic_stats("Mastodon - Megalodon")

    # def test_nostrum(self):
        # self._test_basic_stats("Meshuggah - Nostrum")

    # def test_tapped_out(self):
        # self._test_basic_stats("Mike Orlando - Tapped Out")

    # def test_whelmed(self):
        # self._test_basic_stats("Satyr - Whelmed")

    # def test_omniphobia(self):
        # self._test_basic_stats("Sianvar - Omniphobia")

    # def test_set_the_world_on_fire(self):
        # self._test_basic_stats("Symphony X - Set the World on Fire")

    # def test_laments_of_an_icarus(self):
        # self._test_basic_stats("TEXTURES - Laments Of An Icarus")

    # def test_sugar_tzu(self):
        # self._test_basic_stats("black midi - Sugar／Tzu (Smoochums, Vasasasasa)")

    # def test_blight(self):
        # self._test_basic_stats("Fallen Monarch - Blight")

    # def test_vacant_dreams(self):
        # self._test_basic_stats("Hannes Grossmann - Vacant Dreams")

    # def test_nasty(self):
        # self._test_basic_stats("HopH2O - Nasty (Tinashe)")

    # def test_levitating(self):
        # self._test_basic_stats("Levitating (feat. DaBaby) (Dua Lipa) (L)")

    # def test_dream_genie(self):
        # self._test_basic_stats("Lightning Bolt - Dream Genie")

    # def test_bend(self):
        # self._test_basic_stats("Lockslip - Lockslip - 02 - Bend")

    # def test_when_the_sunrise_breaks_the_darkness(self):
        # self._test_basic_stats("Pathfinder - When The Sunrise Breaks The Darkness")

    # def test_ladies_talk(self):
        # self._test_basic_stats("Senri Kawaguchi - Ladies Talk [Kiyo Sen] (Drumeo Performance)")

    # def test_the_sentinel(self):
        # self._test_basic_stats("Car Bomb - The Sentinel")

    # def test_prelude_to_obliteration(self):
        # self._test_basic_stats("Conquering Dystopia - Prelude to Obliteration")

    # def test_zildjian_live(self):
        # self._test_basic_stats("DOMi & JD Beck - Zildjian LIVE! Performance 2020")

    # def test_awakening(self):
        # self._test_basic_stats("Mahavishnu Orchestra - Awakening")

    # def test_tapestry_of_the_starless_abstract(self):
        # self._test_basic_stats("Ne Obliviscaris - Tapestry of the Starless Abstract (Shortened)")

    # def test_stabwound(self):
        # self._test_basic_stats("Necrophagist - Stabwound")

    # def test_snowball_earth(self):
        # self._test_basic_stats("SoundHaven - Snowball Earth [Indistinct]")

    # def test_bug_thief(self):
        # self._test_basic_stats("Xane60 & SoundHaven - Bug Thief [Iglooghost]")

    # def test_spirit_bomb(self):
        # self._test_basic_stats("Yoink - Spirit Bomb [GanonMetroid]")