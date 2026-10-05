import unittest
import numpy as np
import pandas as pd
import run


class ChronologyAndPolicyTests(unittest.TestCase):
    def test_strict_target_purge(self):
        held = pd.Timestamp("2025-01-03")
        origins = pd.to_datetime(["2025-01-01 23:00", "2025-01-02 00:00", "2025-01-02 01:00"])
        self.assertEqual(run.permitted(origins, held).tolist(), [True, False, False])

    def test_inner_purge_and_28_day_stop(self):
        index = pd.date_range("2024-01-01", periods=90 * 24, freq="h")
        fit, stop = run.inner_split(index)
        self.assertEqual(int(stop.sum()), 28 * 24)
        self.assertEqual(int((~fit & ~stop).sum()), 24)
        self.assertLess((index[fit] + run.DAY).max(), index[stop].min())

    def test_strict_events_and_counts(self):
        observed = run.counts(np.array([True, False, True, False]), np.array([0.5, 0.6, 0.7, 0.4]) > 0.5)
        self.assertEqual([observed[k] for k in ("tp", "fp", "fn", "tn")], [1, 1, 1, 1])
        self.assertEqual(observed["f1_exact"], "1/2")

    def test_integer_probability_grid_tie(self):
        chosen, table = run.select_threshold(np.array([True, False]), np.array([0.99, 0.01]))
        self.assertEqual(len(table), 181)
        self.assertEqual((table[0]["tick"], table[-1]["tick"]), (10, 190))
        self.assertEqual(chosen["tick"], 100)

    def test_base_prediction_is_head_input(self):
        frame = pd.DataFrame({"nwp_radiation": [620.0], "nwp_cloud": [40.0], "hour": [12], "month": [6]})
        first = run.head_features(np.array([600.0]), frame)
        second = run.head_features(np.array([610.0]), frame)
        self.assertEqual(list(first), run.HEAD_FEATURES)
        self.assertAlmostEqual(second.iloc[0]["base_margin"] - first.iloc[0]["base_margin"], 0.1)
        self.assertAlmostEqual(second.iloc[0]["nwp_minus_base"] - first.iloc[0]["nwp_minus_base"], -0.1)
        self.assertAlmostEqual(second.iloc[0]["margin_cloud"] - first.iloc[0]["margin_cloud"], 0.04)

    def test_one_class_head_fails_before_fit(self):
        with self.assertRaises(AssertionError):
            run.fit_head("logistic", np.zeros((3, 8)), np.zeros(3))

    def test_no_calls_keep_undefined_precision(self):
        row = run.counts(np.array([True, False]), np.array([False, False]))
        self.assertIsNone(row["precision"])
        self.assertEqual(row["recall"], 0)
        self.assertIsNone(run.metric_difference(row["precision"], 0.9))

    def test_empty_bootstrap_f1_keeps_null_intervals(self):
        index = pd.date_range("2025-01-01", periods=3, freq="h")
        truth = np.zeros(3, dtype=bool)
        names = list(run.ARMS) + ["base_refit", "supplied_v2_600", "supplied_v2_562", "fixed008"]
        result = run.bootstrap(index, truth, {name: truth.copy() for name in names})
        for row in result["comparisons"].values():
            self.assertIsNone(row["lower_025"])
            self.assertIsNone(row["upper_975"])
            self.assertEqual(row["undefined_replicates"], 2000)


if __name__ == "__main__":
    unittest.main()
