import os
import unittest
import json

import hydra.hyutil as hyutil
import hydra.hydata as hydata


class TestMultSqueezeData(unittest.TestCase):
    """Test cases for multiplier squeezes."""
    def setUp(self):
        pass

    def test_all_chords(self):
        # Solutions
        solns = {
            # 2-note mult squeezes
            (0, 7): None,
            (0, 8): ([(hydata.Chord(code='K'), hydata.Chord(code='Y+'))], 50),
            (1, 7): None,
            (1, 8): ([(hydata.Chord(code='K'), hydata.Chord(code='y'))], 15),
            (2, 7): None,
            (2, 8): ([(hydata.Chord(code='K'), hydata.Chord(code='y+'))], 80),
            (3, 7): None,
            (3, 8): ([(hydata.Chord(code='y'), hydata.Chord(code='G+'))], 35),
            (4, 7): None,
            (4, 8): ([(hydata.Chord(code='G+'), hydata.Chord(code='y+'))], 30),
            (5, 7): None,
            (5, 8): ([(hydata.Chord(code='g'), hydata.Chord(code='y+'))], 65),
            # 3-note mult squeezes
            (6, 7): (
                # 7 combo: 1 pair per high note
                [
                    (hydata.Chord(code='KG'), hydata.Chord(code='Y+'))
                ], 50
            ),
            (6, 8): (
                # 8 combo: 1 pair per low note
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='Y+G')),
                    (hydata.Chord(code='G'), hydata.Chord(code='KY+'))
                ], 50
            ),
            (7, 7): (
                [
                    (hydata.Chord(code='KG'), hydata.Chord(code='y'))
                ], 15
            ),
            (7, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='yG')),
                    (hydata.Chord(code='G'), hydata.Chord(code='Ky'))
                ], 15
            ),
            (8, 7): (
                [
                    (hydata.Chord(code='KG'), hydata.Chord(code='y+'))
                ], 80
            ),
            (8, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='y+G')),
                    (hydata.Chord(code='G'), hydata.Chord(code='Ky+'))
                ], 80
            ),
            (9, 7): (
                [
                    (hydata.Chord(code='KY+'), hydata.Chord(code='G+')),
                    (hydata.Chord(code='KG+'), hydata.Chord(code='Y+'))
                ], 50
            ),
            (9, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='Y+G+'))
                ], 50
            ),
            (10, 7): (
                [
                    (hydata.Chord(code='Ky'), hydata.Chord(code='G+'))
                ], 50
            ),
            (10, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='yG+'))
                ], 50
            ),
            (11, 7): (
                [
                    (hydata.Chord(code='KG+'), hydata.Chord(code='y+'))
                ], 80
            ),
            (11, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='y+G+'))
                ], 80
            ),
            (12, 7): (
                [
                    (hydata.Chord(code='Ky'), hydata.Chord(code='g')),
                    (hydata.Chord(code='Kg'), hydata.Chord(code='y'))
                ], 15
            ),
            (12, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='yg'))
                ], 15
            ),
            (13, 7): (
                [
                    (hydata.Chord(code='Kg'), hydata.Chord(code='y+'))
                ], 80
            ),
            (13, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='y+g'))
                ], 80
            ),
            (14, 7): (
                [
                    (hydata.Chord(code='Ky+'), hydata.Chord(code='g+')),
                    (hydata.Chord(code='Kg+'), hydata.Chord(code='y+'))
                ], 80
            ),
            (14, 8): (
                [
                    (hydata.Chord(code='K'), hydata.Chord(code='y+g+'))
                ], 80
            ),
        }
        
        test_data = [
            hydata.Chord(code='KY+'),
            hydata.Chord(code='Ky'),
            hydata.Chord(code='Ky+'),
            hydata.Chord(code='yG+'),
            hydata.Chord(code='y+G+'),
            hydata.Chord(code='y+g'),
            hydata.Chord(code='KY+G'),
            hydata.Chord(code='KyG'),
            hydata.Chord(code='Ky+G'),
            hydata.Chord(code='KY+G+'),
            hydata.Chord(code='KyG+'),
            hydata.Chord(code='Ky+G+'),
            hydata.Chord(code='Kyg'),
            hydata.Chord(code='Ky+g'),
            hydata.Chord(code='Ky+g+'),
        ]
        
        combos = [7,8]
        
        for i, chord in enumerate(test_data):
            with self.subTest(i=i):
                for combo in combos:
                    try:
                        msq = hydata.MultSqueeze(chord, combo)
                        soln_pairs = solns[(i, combo)][0]
                        test_pairs = msq.guide_chords
                        self.assertEqual(len(soln_pairs), len(test_pairs))
                        for soln_pair in soln_pairs:
                            self.assertTrue(soln_pair in test_pairs)
                        self.assertEqual(solns[(i, combo)][1], msq.points)
                    except ValueError:
                        self.assertTrue(solns[(i, combo)] is None)
                    
