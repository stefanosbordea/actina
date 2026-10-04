"""Behavior checks for chronological cutoffs and prediction-file trust boundaries."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.train import FEATURES, WEATHER, assert_feature_cutoffs, build_features, choose_threshold, issue_time_persistence, load_weather, split_frames
from eval.evaluate import confusion, validate_metadata, validate_predictions


class FeatureTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        times = pd.date_range("2026-05-01", "2026-07-20T23:00", freq="h", tz="Asia/Nicosia")
        cls.weather = pd.DataFrame({column: np.arange(len(times), dtype=float) + 1
                                    for column in WEATHER}, index=times)
        cls.frame = build_features(cls.weather)

    def test_all_sources_precede_issue(self):
        assert_feature_cutoffs(self.frame)
        self.assertTrue((self.frame.lag2_source_time <= self.frame.forecast_issue_time).all())
        self.assertTrue((self.frame.lag3_source_time <= self.frame.forecast_issue_time).all())

    def test_late_afternoon_persistence_is_available(self):
        target = pd.Timestamp("2026-07-10T23:00", tz="Asia/Nicosia")
        row = self.frame.loc[target]
        self.assertEqual(row.lag2_source_time, pd.Timestamp("2026-07-08T23:00", tz="Asia/Nicosia"))
        self.assertEqual(row.forecast_issue_time, pd.Timestamp("2026-07-09T18:00", tz="Asia/Nicosia"))

    def test_target_day_weather_cannot_change_its_features(self):
        changed = self.weather.copy()
        mask = changed.index.strftime("%Y-%m-%d") == "2026-07-10"
        changed.loc[mask, WEATHER] += 10000
        features = build_features(changed)
        targets = self.frame.index.strftime("%Y-%m-%d") == "2026-07-10"
        pd.testing.assert_frame_equal(self.frame.loc[targets, FEATURES], features.loc[targets, FEATURES])

    def test_a_tampered_future_source_is_rejected(self):
        changed = self.frame.iloc[:1].copy()
        changed["lag2_source_time"] = changed.forecast_issue_time + pd.Timedelta(hours=1)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            assert_feature_cutoffs(changed)

    def test_training_cutoff_is_frozen(self):
        train, test = split_frames(self.frame)
        self.assertTrue((train.index.month < 7).all())
        self.assertTrue((test.index.month == 7).all())
        with self.assertRaisesRegex(ValueError, "Frozen"):
            split_frames(self.frame, train_before="2026-08-01")

    def test_latest_same_hour_baseline_changes_at_issue_cutoff(self):
        targets = pd.date_range("2026-07-10T18:00", periods=2, freq="h", tz="Asia/Nicosia")
        persistence = issue_time_persistence(self.weather, targets)
        self.assertEqual(persistence.iloc[0].baseline_source_time, pd.Timestamp("2026-07-09T18:00", tz="Asia/Nicosia"))
        self.assertEqual(persistence.iloc[1].baseline_source_time, pd.Timestamp("2026-07-08T19:00", tz="Asia/Nicosia"))

    def test_dst_duplicate_local_hours_are_unambiguous(self):
        times = pd.date_range("2025-10-23", "2025-10-29", freq="h", tz="Asia/Nicosia")
        weather = pd.DataFrame({column: np.ones(len(times)) for column in WEATHER}, index=times)
        frame = build_features(weather)
        self.assertFalse(frame.index.has_duplicates)
        assert_feature_cutoffs(frame)

    def test_weather_hour_continuity_handles_pandas_time_units(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "weather.csv"
            weather = self.weather.iloc[:4].copy()
            weather.index.name = "time"
            weather.to_csv(path)
            self.assertEqual(len(load_weather(path)), 4)
            weather.drop(weather.index[1]).to_csv(path)
            with self.assertRaisesRegex(ValueError, "contiguous"):
                load_weather(path)


class PredictionValidationTests(unittest.TestCase):
    def setUp(self):
        self.index = pd.date_range("2026-07-01", periods=3, freq="h", tz="Asia/Nicosia")
        issues = pd.DatetimeIndex([pd.Timestamp("2026-06-30T18:00", tz="Asia/Nicosia")] * 3)
        self.expected = pd.DataFrame({"actual": [0., 0., 1.], "baseline": [0., 0., 2.],
                                      "baseline_day2": [0., 0., 2.], "baseline_source_time": self.index - pd.Timedelta(days=1),
                                      "climatology": [0., 0., 3.], "forecast_issue_time": issues}, index=self.index)
        self.supplied = pd.DataFrame({"time": [t.isoformat() for t in self.index],
                                      "actual": [0., 0., 1.], "predicted": [0., .1, 1.5],
                                      "baseline": [0., 0., 2.]})

    def test_valid_four_column_handoff(self):
        frame = validate_predictions(self.supplied, self.expected)
        self.assertEqual(len(frame), 3)
        self.assertIn("forecast_issue_time", frame)

    def test_bare_prediction_join_uses_canonical_authority(self):
        bare = self.supplied[["time", "predicted"]]
        frame = validate_predictions(bare, self.expected, join_canonical=True)
        pd.testing.assert_series_equal(frame.actual, self.expected.actual, check_names=False, check_freq=False)
        pd.testing.assert_series_equal(frame.baseline, self.expected.baseline, check_names=False, check_freq=False)

    def test_bare_prediction_requires_explicit_join(self):
        with self.assertRaisesRegex(ValueError, "Missing prediction columns"):
            validate_predictions(self.supplied[["time", "predicted"]], self.expected)

    def test_join_does_not_overwrite_forged_supplied_truth(self):
        bad = self.supplied.drop(columns="baseline")
        bad.loc[0, "actual"] = 99.
        with self.assertRaisesRegex(ValueError, "canonical"):
            validate_predictions(bad, self.expected, join_canonical=True)

    def test_join_preserves_full_coverage_requirement(self):
        with self.assertRaisesRegex(ValueError, "every canonical"):
            validate_predictions(self.supplied[["time", "predicted"]].iloc[:2], self.expected, join_canonical=True)

    def test_join_rejects_missing_timezone(self):
        bad = self.supplied[["time", "predicted"]].copy()
        bad["time"] = [t.tz_localize(None).isoformat() for t in self.index]
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            validate_predictions(bad, self.expected, join_canonical=True)

    def test_join_checks_supplied_issue_time(self):
        bad = self.supplied[["time", "predicted"]].copy()
        bad["forecast_issue_time"] = "2026-07-01T18:00:00+03:00"
        with self.assertRaisesRegex(ValueError, "preceding date"):
            validate_predictions(bad, self.expected, join_canonical=True)

    def test_extreme_finite_prediction_is_rejected_before_scoring(self):
        bad = self.supplied.copy()
        bad.loc[0, "predicted"] = 1e200
        with self.assertRaisesRegex(ValueError, "study input range"):
            validate_predictions(bad, self.expected)

    def test_supplied_baseline_source_time_is_checked(self):
        bad = self.supplied.copy()
        bad["baseline_source_time"] = "2027-01-01T00:00:00+02:00"
        with self.assertRaisesRegex(ValueError, "source time"):
            validate_predictions(bad, self.expected, join_canonical=True)
        bad["baseline_source_time"] = [t.isoformat() for t in self.expected.baseline_source_time]
        validate_predictions(bad, self.expected, join_canonical=True)

    def test_naive_baseline_source_time_is_rejected(self):
        bad = self.supplied.copy()
        bad["baseline_source_time"] = "2026-06-30T00:00:00"
        with self.assertRaisesRegex(ValueError, "explicit timezone"):
            validate_predictions(bad, self.expected, join_canonical=True)

    def test_duplicate_timestamp_is_rejected(self):
        bad = pd.concat([self.supplied, self.supplied.iloc[:1]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            validate_predictions(bad, self.expected)

    def test_nonfinite_values_are_rejected(self):
        for value in [np.nan, np.inf, -np.inf]:
            with self.subTest(value=value):
                bad = self.supplied.copy()
                bad.loc[0, "predicted"] = value
                with self.assertRaisesRegex(ValueError, "Nonfinite"):
                    validate_predictions(bad, self.expected)

    def test_wrong_split_timestamp_is_rejected(self):
        bad = self.supplied.copy()
        bad.loc[0, "time"] = "2026-06-30T23:00:00+03:00"
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_predictions(bad, self.expected)

    def test_wrong_truth_or_unsafe_baseline_is_rejected(self):
        for column in ["actual", "baseline"]:
            with self.subTest(column=column):
                bad = self.supplied.copy()
                bad.loc[0, column] = 100.
                with self.assertRaisesRegex(ValueError, "canonical"):
                    validate_predictions(bad, self.expected)

    def test_missing_hours_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "every canonical"):
            validate_predictions(self.supplied.iloc[:2], self.expected)

    def test_wrong_issue_timestamp_is_rejected(self):
        bad = self.supplied.copy()
        bad["forecast_issue_time"] = "2026-07-01T18:00:00+03:00"
        with self.assertRaisesRegex(ValueError, "18:00 local"):
            validate_predictions(bad, self.expected)

    def test_confusion_counts_include_negative_hours(self):
        counts = confusion([700, 100, 700, 100], [700, 700, 100, 100], 600)
        self.assertEqual([counts[k] for k in ["tp", "fp", "tn", "fn"]], [1, 1, 1, 1])
        self.assertEqual(counts["precision"], .5)
        self.assertEqual(counts["recall"], .5)

    def test_threshold_selection_has_fixed_candidates(self):
        threshold, rows = choose_threshold(np.tile([100., 750.], 100), np.tile([100., 750.], 100))
        self.assertEqual(threshold, 600)
        self.assertEqual([row["threshold_w_m2"] for row in rows], [400, 500, 600, 700])

    def test_model_metadata_rejects_leaking_train_target(self):
        metadata = {"train_target_before": "2026-07-01", "train_last_target": "2026-07-01T00:00:00+03:00"}
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_metadata(metadata, ROOT / "unused.csv")

    def test_model_metadata_rejects_test_tuning(self):
        metadata = {"train_target_before": "2026-07-01", "train_last_target": "2026-06-30T23:00:00+03:00",
                    "leakage_audit": {"test_tuning": True}}
        with self.assertRaisesRegex(ValueError, "test tuning"):
            validate_metadata(metadata, ROOT / "unused.csv")


if __name__ == "__main__":
    unittest.main()
