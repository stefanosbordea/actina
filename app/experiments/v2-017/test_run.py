import unittest
import numpy as np
import pandas as pd
import run


class PolicyTests(unittest.TestCase):
    def test_false_positive_cap_applies_before_ranking(self):
        truth = np.array([True, True, False, False])
        chosen, grid = run.select(truth, np.array([.9, .7, .8, .1]), np.array([True, False, False, False]))
        self.assertEqual(len(grid), 181)
        self.assertEqual(chosen["fp"], 0)
        self.assertGreaterEqual(chosen["threshold"], .8)
        self.assertTrue(any(not row["eligible"] for row in grid))

    def test_no_admissible_tick_is_explicit(self):
        selected, _ = run.select(np.array([True, False]), np.array([1., 1.]), np.array([True, False]))
        self.assertIsNone(selected)

    def test_control_and_expanded_share_core_exactly(self):
        frame = pd.DataFrame({"base_prediction": [620.], "nwp_radiation": [630.], "nwp_cloud": [20.],
            "solar_scale": [500.], "ecmwf_day2": [640.], "gfs_day2": [660.],
            "target_hour_sin": [0.], "target_hour_cos": [-1.], "target_season_sin": [0.], "target_season_cos": [1.]})
        core, expanded = run.features(frame, "core"), run.features(frame, "expanded")
        pd.testing.assert_frame_equal(core, expanded[run.CORE])
        self.assertEqual(list(expanded), run.CORE + run.EXTRA)
        self.assertAlmostEqual(expanded["ecmwf_minus_v2"].iloc[0], .2)
        self.assertAlmostEqual(expanded["gfs_minus_v2"].iloc[0], .4)
        self.assertAlmostEqual(expanded["forecast_disagreement"].iloc[0], .2)
        changed = frame.copy()
        changed["base_prediction"] += 10
        self.assertFalse(run.features(changed, "core").equals(core))

    def test_strict_target_before_origin(self):
        index = pd.to_datetime(["2025-01-01 23:00", "2025-01-02 00:00"])
        self.assertEqual(run.h.permitted(index, pd.Timestamp("2025-01-03")).tolist(), [True, False])


if __name__ == "__main__":
    unittest.main()
