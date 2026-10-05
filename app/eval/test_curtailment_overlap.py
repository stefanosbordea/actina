import unittest
import numpy as np
from eval.curtailment_overlap import window_weights, load_in_window


class CurtailmentOverlapTests(unittest.TestCase):
    def test_quarter_hour_weights_conserve_window_duration(self):
        weights = window_weights([{"start_local": "09:45", "end_local": "15:30"}])
        self.assertEqual(weights.sum(), 5.75)
        self.assertEqual(weights[9], .25)
        self.assertEqual(weights[15], .5)
        self.assertEqual(load_in_window(np.full(24, 408.), weights), 2346.)

    def test_missing_window_is_zero_overlap_not_a_zero_curtailment_claim(self):
        self.assertEqual(window_weights([]).sum(), 0)

    def test_disjoint_windows_do_not_fill_the_gap(self):
        weights = window_weights([{"start_local": "10:00", "end_local": "11:00"}, {"start_local": "12:00", "end_local": "13:00"}])
        self.assertEqual(weights.sum(), 2)
        self.assertEqual(weights[11], 0)

    def test_overlap_and_cross_midnight_rejected(self):
        for windows in [
            [{"start_local": "10:00", "end_local": "12:00"}, {"start_local": "11:00", "end_local": "13:00"}],
            [{"start_local": "23:00", "end_local": "01:00"}],
            [{"start_local": "12:00", "end_local": "12:00"}],
        ]:
            with self.subTest(windows=windows), self.assertRaises(ValueError):
                window_weights(windows)

    def test_invalid_load_is_rejected(self):
        for values in [np.zeros(23), np.full(24, np.nan), np.full(24, -1)]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                load_in_window(values, np.ones(24))


if __name__ == "__main__":
    unittest.main()
