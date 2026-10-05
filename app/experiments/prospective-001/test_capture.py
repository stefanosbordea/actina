import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("prospective_capture", HERE / "capture.py")
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


def fixture():
    start = int(datetime(2026, 10, 4, tzinfo=timezone.utc).timestamp())
    return {"utc_offset_seconds": 0, "hourly_units": {"time": "unixtime", "shortwave_radiation": "W/m²", "cloud_cover": "%"},
            "hourly": {"time": [start + 3600 * index for index in range(168)],
                       "shortwave_radiation": [600, 600.1, None] + [0] * 165,
                       "cloud_cover": [None] + [20] * 167}}


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        _, self.rows = capture.parse_payload(json.dumps(self.data))

    def test_all_rows_nulls_and_strict_threshold_retained(self):
        self.assertEqual(len(self.rows), 168)
        self.assertEqual([row["event_gt_600"] for row in self.rows[:3]], [0, 1, None])
        self.assertIsNone(self.rows[0]["cloud_cover_percent"])
        self.assertIsNone(self.rows[2]["shortwave_radiation_w_m2"])
        self.assertEqual(len(capture.csv_bytes(self.rows).splitlines()), 169)
        self.assertTrue(capture.csv_bytes(self.rows).splitlines()[3].endswith(b",,20,"))

    def test_exact_and_fractional_capture_boundaries(self):
        base = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        for microseconds, expected_hour in ((0, 10), (1, 11)):
            finished = base + timedelta(microseconds=microseconds)
            selected = capture.targets(self.rows, finished)
            primary, secondary = selected["primary"]["intervals"], selected["secondary"]["intervals"]
            self.assertEqual((len(primary), len(secondary)), (24, 24))
            self.assertEqual(primary[0]["interval_start_utc"], capture.iso(base.replace(day=5, hour=expected_hour)))
            self.assertEqual(primary[-1]["valid_time_utc"], secondary[0]["interval_start_utc"])
            for rows, minimum in ((primary, 24), (secondary, 48)):
                self.assertGreaterEqual(rows[0]["start_lead_seconds"], minimum * 3600)
                self.assertLess(rows[0]["start_lead_seconds"], (minimum + 1) * 3600)
                self.assertTrue(all(datetime.fromisoformat(row["valid_time_utc"]) - datetime.fromisoformat(row["interval_start_utc"])
                                    == timedelta(hours=1) for row in rows))

    def test_selected_null_never_changes_membership(self):
        finished = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        target_start = capture.iso(datetime(2026, 10, 5, 10, tzinfo=timezone.utc))
        for row in self.rows:
            if row["interval_start_utc"] == target_start:
                row["shortwave_radiation_w_m2"] = row["event_gt_600"] = None
        selected = capture.targets(self.rows, finished)["primary"]
        self.assertEqual(selected["null_radiation_count"], 1)
        self.assertEqual(selected["intervals"][0]["interval_start_utc"], target_start)

    def test_duplicate_missing_unordered_and_nonhourly_timestamps_rejected(self):
        for replacement in (self.data["hourly"]["time"][0], self.data["hourly"]["time"][1] + 3600,
                            self.data["hourly"]["time"][1] - 7200, self.data["hourly"]["time"][1] + 1):
            data = copy.deepcopy(self.data)
            data["hourly"]["time"][1] = replacement
            with self.assertRaises(ValueError):
                capture.parse_payload(json.dumps(data))

    def test_bad_units_values_and_offset_rejected(self):
        for field, value in (("shortwave_radiation", -1), ("cloud_cover", 101), ("cloud_cover", True),
                             ("shortwave_radiation", float("nan")), ("shortwave_radiation", float("inf"))):
            data = copy.deepcopy(self.data)
            data["hourly"][field][3] = value
            with self.assertRaises(ValueError):
                capture.parse_payload(json.dumps(data))
        self.data["utc_offset_seconds"] = 10800
        with self.assertRaises(ValueError):
            capture.parse_payload(json.dumps(self.data))
        self.data = fixture()
        self.data["hourly_units"]["shortwave_radiation"] = "kWh"
        with self.assertRaises(ValueError):
            capture.parse_payload(json.dumps(self.data))

    def test_target_missing_duplicate_and_naive_completion_rejected(self):
        finished = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
        for rows in (self.rows[:40], self.rows + self.rows[:1]):
            with self.assertRaises(ValueError):
                capture.targets(rows, finished)
        with self.assertRaises(ValueError):
            capture.targets(self.rows, finished.replace(tzinfo=None))

    def test_existing_output_refused_before_network_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "preserve.txt"
            sentinel.write_bytes(b"unchanged")
            with patch.object(capture.urllib.request, "urlopen") as network:
                with self.assertRaises(FileExistsError):
                    capture.run(Path(directory))
                network.assert_not_called()
            self.assertEqual(sentinel.read_bytes(), b"unchanged")
            self.assertEqual(list(Path(directory).iterdir()), [sentinel])

    def test_network_failure_is_retained_and_attempt_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "attempt"
            with patch.object(capture.urllib.request, "urlopen", side_effect=OSError("fixture offline")):
                with self.assertRaises(OSError):
                    capture.run(output)
            self.assertEqual(json.loads((output / "failure.json").read_text())["status"], "FAILED")
            self.assertTrue((output / "request.json").is_file())
            with self.assertRaises(FileExistsError):
                capture.run(output)


if __name__ == "__main__":
    unittest.main()
