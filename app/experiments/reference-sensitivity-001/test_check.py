from datetime import datetime, timedelta
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("reference_sensitivity", Path(__file__).with_name("check.py"))
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def fixture():
    original, predictions, joins, satellite = [], {method: [] for method in check.METHODS}, {}, {}
    for index, (actual, point, reference) in enumerate(((700, 700, 700), (500, 700, 700), (700, 0, None))):
        origin = datetime(2026, 1, 1) + timedelta(hours=index)
        target = origin + timedelta(hours=24)
        epoch = int(target.replace(tzinfo=check.OFFSET).timestamp())
        original.append({"time": str(origin), "actual": str(actual), "predicted": str(point), "baseline": str(point)})
        joins[origin], satellite[epoch] = (target, epoch), reference
        for method in check.METHODS:
            predictions[method].append({"feature_time": str(origin), "target_time": str(target), "actual_w_m2": str(actual),
                                        "point_w_m2": str(point), "probability": str(int(point > 600)),
                                        "default_positive": str(int(point > 600)), "predicted_positive": "0"})
    return original, predictions, joins, satellite


class SensitivityTests(unittest.TestCase):
    def test_same_subset_isolates_reference_change(self):
        result, rows = check.assess_split(*fixture())
        self.assertEqual((result["coverage"]["original_hours"], result["coverage"]["scored_hours"], result["coverage"]["unscored_hours"]), (3, 2, 1))
        self.assertEqual(len(rows), 3)
        self.assertIsNone(rows[-1]["satellite_reference_w_m2"])
        self.assertEqual(rows[-1]["reference_available"], 0)
        for method in check.METHODS:
            bases = result["methods"][method]
            self.assertEqual(bases["weather_full"]["recall"], .5)
            self.assertEqual(bases["weather_common"]["precision"], .5)
            self.assertEqual(bases["weather_common"]["recall"], 1)
            self.assertEqual(bases["satellite_common"]["precision"], 1)
            self.assertEqual(bases["satellite_common"]["mae"], 0)
            self.assertEqual(bases["weather_common"]["hours"], bases["satellite_common"]["hours"])
        self.assertEqual(result["reference_event_cross_tabulation"], {"weather0_satellite0": 0, "weather0_satellite1": 1, "weather1_satellite0": 0, "weather1_satellite1": 1})

    def test_null_reference_never_hides_missing_forecast(self):
        args = fixture()
        args[1]["ridge_bias"][-1]["point_w_m2"] = ""
        with self.assertRaises(ValueError):
            check.assess_split(*args)
        args = fixture()
        args[1]["ridge_bias"].pop()
        with self.assertRaises(ValueError):
            check.assess_split(*args)

    def test_scenario_default_uses_probability_not_median_or_selected(self):
        row = {"point_w_m2": "601", "probability": "0.5", "default_positive": "0", "predicted_positive": "1"}
        self.assertEqual(check.default_prediction(row, "analogue_solar"), (601, 0))
        row["probability"], row["default_positive"] = "0.5001", "1"
        self.assertEqual(check.default_prediction(row, "analogue_solar"), (601, 1))
        row.update(point_w_m2="600", probability="0", default_positive="0")
        self.assertEqual(check.default_prediction(row, "nwp_day2"), (600, 0))

    def test_strict_reference_boundary_and_undefined_scores(self):
        result = check.scores([600, 600.1], [600, 600], [0, 0])
        self.assertEqual((result["tn"], result["fn"], result["f1"]), (1, 1, 0))
        self.assertIsNone(result["precision"])
        empty = check.scores([], [], [])
        self.assertEqual(empty["hours"], 0)
        self.assertTrue(all(empty[key] is None for key in ("precision", "recall", "f1", "mae", "rmse")))

    def test_changed_control_membership_or_target_rejected(self):
        for method, field, value in (("original", "point_w_m2", "701"), ("persistence", "actual_w_m2", "701"),
                                     ("median_bias", "feature_time", "2026-01-02 00:00:00")):
            args = fixture()
            args[1][method][0][field] = value
            with self.assertRaises(ValueError):
                check.assess_split(*args)
        args = fixture()
        args[2][datetime(2026, 1, 1)] = (datetime(2026, 1, 2), 0)
        with self.assertRaises(ValueError):
            check.assess_split(*args)

    def test_absent_reference_hour_does_not_become_null(self):
        args = fixture()
        args[3].pop(next(iter(args[3])))
        with self.assertRaises(ValueError):
            check.assess_split(*args)

    def test_original_serialization_allowance_is_narrow_and_reported(self):
        args = fixture()
        point = 700.0
        for _ in range(4):
            point = math.nextafter(point, math.inf)
        args[1]["original"][0]["point_w_m2"] = repr(point)
        result, _ = check.assess_split(*args)
        self.assertEqual(result["original_control_serialization"]["different_rows"], 1)
        self.assertEqual(result["original_control_serialization"]["maximum_ulps"], 4)
        args[1]["original"][0]["point_w_m2"] = repr(math.nextafter(point, math.inf))
        with self.assertRaises(ValueError):
            check.assess_split(*args)
        args = fixture()
        args[0][0]["predicted"] = "600"
        args[1]["original"][0]["point_w_m2"] = repr(math.nextafter(600, math.inf))
        with self.assertRaises(ValueError):
            check.assess_split(*args)

    def test_null_spans_preserve_nonadjacent_hours(self):
        spans = check.missing_spans([0, 3600, 10800])
        self.assertEqual([span["hours"] for span in spans], [2, 1])
        self.assertEqual(spans[0]["last_valid_time_utc"], "1970-01-01T01:00:00+00:00")

    def test_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "keep"
            original.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                check.run(directory)
            self.assertEqual(original.read_bytes(), b"preserve")
            self.assertEqual(list(Path(directory).iterdir()), [original])


if __name__ == "__main__":
    unittest.main()
