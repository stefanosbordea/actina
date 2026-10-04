import unittest
import numpy as np
from paired import scores, weights


class PairedTests(unittest.TestCase):
    def test_pooled_counts_not_average_daily_ratios(self):
        counts = np.asarray([[1, 0, 1], [1, 9, 0]])
        result = scores(counts.sum(axis=0))
        np.testing.assert_allclose(result, [2 / 11, 2 / 3, 4 / 14])
        self.assertNotEqual(result[0], scores(counts)[:, 0].mean())

    def test_missing_denominators_remain_undefined(self):
        self.assertTrue(np.isnan(scores(np.asarray([0, 0, 0]))).all())
        result = scores(np.asarray([0, 0, 2]))
        self.assertTrue(np.isnan(result[0]))
        np.testing.assert_array_equal(result[1:], [0, 0])

    def test_paired_identity_and_calendar_mass(self):
        for block in (1, 7):
            draw = weights(np.random.default_rng(1), 10, block, 100)
            np.testing.assert_array_equal(draw.sum(axis=1), np.full(100, 10))
            self.assertTrue((draw >= 0).all())
            counts = np.tile([2, 1, 1], (10, 1))
            sample = scores(draw @ counts)
            np.testing.assert_array_equal(sample - sample, np.zeros((100, 3)))


if __name__ == '__main__':
    unittest.main()
