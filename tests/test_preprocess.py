"""Analytical synthetic fixtures only; never included in real demo outputs."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from preprocess import central_slope


class SlopeTests(unittest.TestCase):
    def test_flat_synthetic_plane(self):
        z = np.full((7, 7), -2500.)
        slope, valid = central_slope(z, np.ones(z.shape, dtype=bool), 40., 40.)
        self.assertTrue(valid.all())
        np.testing.assert_array_equal(slope, 0)

    def test_known_synthetic_plane_uses_horizontal_distance(self):
        # Columns physically 30 m apart; rows 20 m apart, slope components .2,.3.
        rr, cc = np.indices((7, 7))
        z = .2*cc*30 - .3*rr*20
        slope, _ = central_slope(z, np.ones(z.shape, dtype=bool), 60., 40.)
        np.testing.assert_allclose(slope, np.degrees(np.arctan(np.hypot(.2, .3))), rtol=1e-6)

    def test_synthetic_hole_invalidates_cross_without_interpolation(self):
        z = np.ones((7, 7))
        valid = np.ones(z.shape, dtype=bool)
        valid[3, 3] = False
        slope, output_valid = central_slope(z, valid, 40., 40.)
        self.assertEqual(int((~output_valid).sum()), 5)
        self.assertTrue(np.isnan(slope[~output_valid]).all())
        self.assertTrue((slope[output_valid] == 0).all())

    def test_nonfinite_synthetic_neighbor_is_missing(self):
        z = np.ones((5, 5)); z[2, 2] = np.nan
        slope, valid = central_slope(z, np.ones(z.shape, dtype=bool), 40., 40.)
        self.assertEqual(int((~valid).sum()), 5)
        self.assertTrue(np.isnan(slope[~valid]).all())


if __name__ == '__main__':
    unittest.main()
