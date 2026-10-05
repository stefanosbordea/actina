import copy
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("satellite_reference", Path(__file__).with_name("fetch.py"))
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.parameters = patch.dict(fetch.PARAMETERS, {"start_date": "2026-10-01", "end_date": "2026-10-01"})
        self.parameters.start()
        self.addCleanup(self.parameters.stop)
        start = int(datetime(2026, 10, 1, tzinfo=timezone.utc).timestamp())
        self.data = {"utc_offset_seconds": 0, "latitude": 34.775, "longitude": 32.425, "elevation": 71,
                     "hourly_units": {"time": "unixtime", "shortwave_radiation": "W/m²"},
                     "hourly": {"time": [start + index * 3600 for index in range(24)],
                                "shortwave_radiation": [None, None] + [10] * 21 + [None]}}

    def test_all_hours_and_null_spans_retained(self):
        report, table = fetch.inspect(json.dumps(self.data))
        self.assertEqual(report["returned_hours"], 24)
        self.assertEqual(report["null_hours"], 3)
        self.assertEqual([span["hours"] for span in report["missing_spans"]], [2, 1])
        self.assertEqual(report["first_interval_start_utc"], "2026-09-30T23:00:00+00:00")
        self.assertEqual(len(table.splitlines()), 25)
        self.assertEqual(sum(line.endswith(b",,1") for line in table.splitlines()), 3)

    def test_duplicate_missing_or_wrong_period_rejected(self):
        for timestamps in (self.data["hourly"]["time"][:-1], self.data["hourly"]["time"][:1] * 24,
                           [t + 86400 for t in self.data["hourly"]["time"]]):
            data = copy.deepcopy(self.data)
            data["hourly"]["time"] = timestamps
            with self.assertRaises(ValueError):
                fetch.inspect(json.dumps(data))

    def test_wrong_units_and_time_basis_rejected(self):
        data = copy.deepcopy(self.data)
        data["hourly_units"]["time"] = "iso8601"
        with self.assertRaises(ValueError):
            fetch.inspect(json.dumps(data))
        self.data["utc_offset_seconds"] = 10800
        with self.assertRaises(ValueError):
            fetch.inspect(json.dumps(self.data))

    def test_nonfinite_negative_and_boolean_radiation_rejected(self):
        for value in (-1, float("nan"), float("inf"), True):
            self.data["hourly"]["shortwave_radiation"][2] = value
            with self.assertRaises(ValueError):
                fetch.inspect(json.dumps(self.data))

    def test_bad_grid_or_array_length_rejected(self):
        data = copy.deepcopy(self.data)
        data["latitude"] = None
        with self.assertRaises(ValueError):
            fetch.inspect(json.dumps(data))
        self.data["hourly"]["shortwave_radiation"].pop()
        with self.assertRaises(ValueError):
            fetch.inspect(json.dumps(self.data))

    def test_no_overwrite_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "keep"
            original.write_bytes(b"original")
            with patch.object(fetch.urllib.request, "urlopen") as network:
                with self.assertRaises(FileExistsError):
                    fetch.run(Path(directory))
                network.assert_not_called()
            self.assertEqual(original.read_bytes(), b"original")
            self.assertEqual(list(Path(directory).iterdir()), [original])


if __name__ == "__main__":
    unittest.main()
