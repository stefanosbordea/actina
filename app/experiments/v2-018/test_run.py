import unittest
import numpy as np
import pandas as pd
import context
import run


class CausalContextTests(unittest.TestCase):
    def history(self, times):
        return pd.DataFrame({"v2_prediction": 100., "ecmwf_prediction": 120.,
            "v2_source_origin": (times - pd.Timedelta(hours=24)).astype(str)}, index=times)

    def test_exact_window_boundaries(self):
        origin = pd.Timestamp("2025-02-01")
        times = pd.DatetimeIndex([origin-pd.Timedelta(hours=337), origin-pd.Timedelta(hours=336),
                                 origin-pd.Timedelta(hours=1), origin])
        observed = pd.DataFrame({"actual": [9000., 50., 70., 9000.]}, index=times)
        features, audit = context.build(pd.DatetimeIndex([origin]), self.history(times), observed)
        self.assertAlmostEqual(features.iloc[0]["past_v2_bias"], .4)
        self.assertAlmostEqual(features.iloc[0]["past_v2_mae"], .4)
        self.assertAlmostEqual(features.iloc[0]["past_ecmwf_bias"], .6)
        self.assertEqual(audit.iloc[0]["v2_count"], 2)
        self.assertEqual(audit.iloc[0]["v2_latest_target"], str(origin-pd.Timedelta(hours=1)))

    def test_future_observations_cannot_change_features_or_call(self):
        origin = pd.Timestamp("2025-02-01")
        times = pd.date_range(origin-pd.Timedelta(hours=400), periods=800, freq="h")
        observed = pd.DataFrame({"actual": np.arange(800, dtype=float)}, index=times)
        changed = observed.copy()
        changed.loc[changed.index >= origin, "actual"] = 1e12
        before, before_audit = context.build(pd.DatetimeIndex([origin]), self.history(times), observed)
        after, after_audit = context.build(pd.DatetimeIndex([origin]), self.history(times), changed)
        pd.testing.assert_frame_equal(before, after)
        pd.testing.assert_frame_equal(before_audit, after_audit)
        fixed_weights = np.array([1., -.5, .25, -.1])
        self.assertEqual(bool(before.to_numpy()[0] @ fixed_weights > .2),
                         bool(after.to_numpy()[0] @ fixed_weights > .2))

    def test_empty_and_separate_source_coverage(self):
        origin = pd.Timestamp("2025-02-01")
        times = pd.DatetimeIndex([origin-pd.Timedelta(hours=1), origin])
        history = self.history(times)
        history["ecmwf_prediction"] = np.nan
        observed = pd.DataFrame({"actual": [80., 20.]}, index=times)
        values, audit = context.build(pd.DatetimeIndex([origin]), history, observed)
        self.assertEqual(audit.iloc[0]["v2_count"], 1)
        self.assertEqual(audit.iloc[0]["ecmwf_count"], 0)
        self.assertEqual(values.iloc[0]["past_ecmwf_bias"], 0)
        self.assertEqual(values.iloc[0]["past_ecmwf_mae"], 0)

    def test_prediction_origin_is_24_hours_before_target(self):
        times = pd.date_range("2025-01-01", periods=3, freq="h")
        history = self.history(times)
        run.issued_history(history)
        history.iloc[0, history.columns.get_loc("v2_source_origin")] = str(times[0])
        with self.assertRaises(AssertionError):
            run.issued_history(history)


if __name__ == "__main__":
    unittest.main()
