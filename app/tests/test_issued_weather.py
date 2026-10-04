"""Synthetic, offline checks for retained forecast bytes and local timing claims."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
weather = importlib.import_module("capture_issued_weather")
handoff = importlib.import_module("record_forecast_handoff")
sys.path.pop(0)


class IssuedWeatherTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.out = self.root / "weather"
        self.run = datetime(2026, 10, 2, 6, tzinfo=timezone.utc)
        self.start = datetime(2026, 10, 3, tzinfo=timezone.utc)
        self.end = self.start + timedelta(hours=3)
        self.received = self.start - timedelta(hours=6)
        source_hours = int((self.end - self.run).total_seconds() / 3600) + 1
        self.forecast = {
            "latitude": 34.78, "longitude": 32.43, "elevation": 80.0,
            "utc_offset_seconds": 0, "timezone": "GMT", "timezone_abbreviation": "GMT",
            "hourly_units": {"time": "unixtime", "shortwave_radiation": "W/m²",
                             "temperature_2m": "°C", "cloud_cover": "%"},
            "hourly": {"time": [int((self.run + timedelta(hours=i)).timestamp()) for i in range(source_hours)],
                       "shortwave_radiation": [0.0] * (source_hours - 3) + [50.0, 100.0, 150.0],
                       "temperature_2m": [20.0] * source_hours, "cloud_cover": [10] * source_hours},
        }
        self.bundle_count = 0
        self.network = patch.object(weather.urllib.request, "build_opener",
                                    side_effect=AssertionError("Tests must not use the network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def raw(self, value):
        return (json.dumps(value, ensure_ascii=False, indent=1) + "\r\n").encode()

    def capture(self, received=None, begun=None, status=200):
        received = received or self.received
        begun = begun or received - timedelta(seconds=1)
        raw = self.raw(self.forecast)
        status_raw = self.raw({"last_run_initialisation_time": int(self.run.timestamp())})
        def download(url):
            is_forecast = url.startswith(weather.API + "?")
            payload = raw if is_forecast else status_raw
            begin, end = (begun, received) if is_forecast else (
                begun - timedelta(seconds=2), begun - timedelta(seconds=1))
            request = {"method": "GET", "url": url, "headers": dict(weather.HEADERS), "body": None}
            return {
                "request": request, "request_sha256": weather.digest(weather.encode(request)),
                "response_status": status if is_forecast else 200, "response_url": url,
                "response_headers": [["Content-Type", "application/json"]],
                "request_started_at_utc": begin.isoformat(), "retrieval_finished_at_utc": end.isoformat(),
                "monotonic_elapsed_seconds": (end - begin).total_seconds(),
                "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
            }, payload
        with patch.object(weather, "download", side_effect=download) as fetch, patch.object(
                weather, "now_utc", side_effect=[(begun - timedelta(seconds=3)).isoformat(),
                                               (received + timedelta(seconds=1)).isoformat()]):
            result = weather.capture(self.out, self.run.isoformat(), self.start.isoformat(), self.end.isoformat())
        self.assertEqual(fetch.call_count, 2)
        return result

    def manifest(self):
        return json.loads((self.out / "manifest.json").read_bytes())

    def alter_manifest(self, change):
        manifest = self.manifest()
        change(manifest)
        (self.out / "manifest.json").write_bytes(weather.encode(manifest))

    def alter_response(self, change, role="forecast"):
        path = self.out / f"{role}.json"
        value = json.loads(path.read_bytes())
        change(value)
        raw = self.raw(value)
        path.write_bytes(raw)
        self.alter_manifest(lambda m: m["http"][role].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))

    def bundle(self, change=None, csv=None, observed=None, features=True, extra_weather=False):
        self.bundle_count += 1
        directory = self.root / f"bundle-{self.bundle_count}"
        source = self.root / f"input-{self.bundle_count}"
        source.mkdir()
        if csv is None:
            csv = "\ufefftime,predicted\r\n" + "".join(
                f"{(self.start + timedelta(hours=i)).isoformat()},123.5\r\n" for i in (1, 2, 3))
        prediction_raw = csv.encode()
        inputs = {"predictions": source / "predictions.csv"}
        inputs["predictions"].write_bytes(prediction_raw)
        if features:
            inputs["features"] = source / "features.json"
            inputs["features"].write_bytes(b'{"synthetic":true}\r\n')
        if extra_weather:
            inputs["weather"] = self.out / "forecast.json"
        checked = weather.verify(self.out)
        meta = {
            "schema": 1, "contract": "aquashift_prospective_forecast",
            "weather_manifest_sha256": checked["manifest_sha256"],
            "weather_response_sha256": checked["forecast_response_sha256"],
            "predictions_sha256": hashlib.sha256(prediction_raw).hexdigest(),
            "features_sha256": hashlib.sha256(inputs["features"].read_bytes()).hexdigest() if features else None,
            "model_label": "synthetic test fixture", "declared_model_sha256": "a" * 64,
            "forecast_issue_time": (self.received + timedelta(minutes=1)).isoformat(),
            "target_support": "preceding_hour_mean",
        }
        if change:
            change(meta)
        inputs["metadata"] = source / "metadata.json"
        inputs["metadata"].write_bytes(self.raw(meta))
        times = {role: (observed or {}).get(role, self.start) for role in inputs}
        clocks = [min(times.values()) - timedelta(seconds=1)]
        clocks.extend(times[role] for role in handoff.ROLES if role in inputs)
        clocks.append(max(times.values()) + timedelta(seconds=1))
        with patch.object(handoff, "now_utc", side_effect=[t.isoformat() for t in clocks]):
            handoff.capture(inputs, directory)
        return directory

    def test_capture_preserves_raw_bytes_hashes_and_request(self):
        result = self.capture()
        self.assertEqual(result["status"], "VERIFIED_BYTES")
        self.assertEqual((self.out / "forecast.json").read_bytes(), self.raw(self.forecast))
        self.assertEqual(result["forecast_response_sha256"], hashlib.sha256(self.raw(self.forecast)).hexdigest())
        self.assertEqual(result["manifest_sha256"], hashlib.sha256((self.out / "manifest.json").read_bytes()).hexdigest())
        self.assertEqual(result["locally_prospective_hours"], 3)
        self.assertEqual(result["hours"], 3)
        self.assertEqual(result["retained_source_hours"], 22)
        self.assertTrue(result["provider_status_matches_requested_run"])
        self.assertIsNone(result["provider_publication_time"])
        self.assertFalse((self.out / ".manifest.pending").exists())
        url = self.manifest()["http"]["forecast"]["request"]["url"]
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query["run"], ["2026-10-02T06:00"])
        self.assertEqual(query["forecast_hours"], ["22"])
        self.assertNotIn("start_hour", query)
        self.assertNotIn("end_hour", query)
        self.assertEqual(query["models"], ["ecmwf_ifs"])
        self.assertEqual(query["timezone"], ["GMT"])
        self.assertEqual(query["timeformat"], ["unixtime"])

    def test_as_of_before_exactly_at_and_after_support_start(self):
        self.capture()
        for delta, expected in [(-1, True), (0, True), (1, False)]:
            with self.subTest(seconds=delta):
                result = weather.verify(self.out, (self.start + timedelta(seconds=delta)).isoformat())
                self.assertEqual(result["rows"][0]["locally_prospective"], expected)
        before_receipt = weather.verify(self.out, (self.received - timedelta(seconds=1)).isoformat())
        self.assertFalse(before_receipt["weather_available_by_as_of"])
        self.assertEqual(before_receipt["locally_prospective_hours"], 0)

    def test_receipt_before_exactly_at_and_after_support_start(self):
        for delta, expected in [(-1, True), (0, True), (1, False)]:
            with self.subTest(seconds=delta):
                self.out = self.root / f"receipt-{delta}"
                result = self.capture(received=self.start + timedelta(seconds=delta))
                self.assertEqual(result["rows"][0]["locally_prospective"], expected)

    def test_request_spanning_boundary_uses_completion(self):
        result = self.capture(begun=self.start - timedelta(minutes=1), received=self.start + timedelta(minutes=1))
        self.assertFalse(result["rows"][0]["locally_prospective"])
        self.assertEqual(result["locally_prospective_hours"], 2)

    def test_small_clock_rollback_cannot_make_boundary_crossing_timely(self):
        received = self.start - timedelta(microseconds=100000)
        self.capture(begun=self.start - timedelta(microseconds=600000), received=received)
        self.alter_manifest(lambda m: m["http"]["forecast"].update(monotonic_elapsed_seconds=1.0))
        result = weather.verify(self.out)
        self.assertEqual(weather.instant(result["weather_received_at_utc"]), received)
        self.assertEqual(weather.instant(result["weather_available_at_utc"]), self.start + timedelta(microseconds=400000))
        self.assertFalse(result["rows"][0]["locally_prospective"])
        self.assertFalse(weather.verify(self.out, received.isoformat())["weather_available_by_as_of"])
        bundle = self.bundle(change=lambda m: m.update(forecast_issue_time=self.start.isoformat()))
        self.assertFalse(weather.check_predictions(self.out, bundle)["weather_available_by_declared_issue"])

    def test_null_radiation_is_unknown_not_zero_or_prospective(self):
        self.forecast["hourly"]["shortwave_radiation"][-3] = None
        result = self.capture()
        self.assertIsNone(result["rows"][0]["shortwave_radiation_w_m2"])
        self.assertFalse(result["rows"][0]["locally_prospective"])
        self.assertEqual(result["missing_radiation_hours"], 1)
        self.assertEqual(weather.check_predictions(self.out, self.bundle())["locally_prospective_hours"], 2)

    def test_unselected_source_hours_do_not_change_window_counts(self):
        self.forecast["hourly"]["shortwave_radiation"][0] = None
        result = self.capture()
        self.assertEqual(result["missing_radiation_hours"], 0)
        self.assertEqual(result["locally_prospective_hours"], 3)
        self.assertEqual(weather.instant(result["rows"][0]["support_start_utc"]), self.start)

    def test_schema_selection_and_request_identity_rejected(self):
        self.capture()
        original = (self.out / "manifest.json").read_bytes()
        changes = [lambda m: m.update(schema=True), lambda m: m.update(schema=2),
                   lambda m: m.update(extra="unsupported"),
                   lambda m: m["selection"].update(model="best_match"),
                   lambda m: m["http"]["forecast"]["request"].update(url=weather.API),
                   lambda m: m["http"]["forecast"].update(request_sha256="0" * 64),
                   lambda m: m["http"]["forecast"].update(response_url=weather.API)]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                (self.out / "manifest.json").write_bytes(original)
                self.alter_manifest(change)
                with self.assertRaises(ValueError):
                    weather.verify(self.out)

    def test_units_timezone_and_exact_hour_coverage_rejected(self):
        changes = [lambda f: f["hourly_units"].update(shortwave_radiation="kW/m²"),
                   lambda f: f.update(utc_offset_seconds=10800),
                   lambda f: f.update(timezone="Asia/Nicosia"),
                   lambda f: f.update(timezone_abbreviation="EEST"),
                   lambda f: f.update(utc_offset_seconds=False),
                   lambda f: f.update(utc_offset_seconds=False),
                   lambda f: f["hourly"]["time"].reverse(),
                   lambda f: f["hourly"]["time"].pop(),
                   lambda f: f["hourly"]["time"].__setitem__(0, f["hourly"]["time"][1]),
                   lambda f: f["hourly"]["time"].__setitem__(0, float(f["hourly"]["time"][0])),
                   lambda f: f["hourly"]["cloud_cover"].pop()]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                self.out = self.root / f"invalid-{index}"
                self.capture()
                self.alter_response(change)
                with self.assertRaises(ValueError):
                    weather.verify(self.out)

    def test_invalid_values_and_provider_status_rejected(self):
        self.capture()
        for value in [True, -1, 2001, "100"]:
            with self.subTest(value=value):
                self.alter_response(lambda f: f["hourly"]["shortwave_radiation"].__setitem__(0, value))
                with self.assertRaises(ValueError):
                    weather.verify(self.out)
        self.alter_response(lambda f: f["hourly"]["shortwave_radiation"].__setitem__(0, 100))
        self.alter_response(lambda f: f.update(last_run_initialisation_time=True), "provider-status")
        with self.assertRaises(ValueError):
            weather.verify(self.out)

    def test_response_tampering_rejected(self):
        self.capture()
        path = self.out / "forecast.json"
        raw = path.read_bytes()
        path.write_bytes(raw.replace(b"50.0", b"51.0"))
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            weather.verify(self.out)

    def test_failed_http_or_download_never_finalizes_manifest(self):
        with self.assertRaises(ValueError):
            self.capture(status=503)
        self.assertFalse((self.out / "manifest.json").exists())
        self.assertTrue((self.out / "failure.json").exists())
        self.assertEqual((self.out / "forecast.json").read_bytes(), self.raw(self.forecast))
        self.out = self.root / "network-failure"
        with patch.object(weather, "download", side_effect=urllib.error.URLError("synthetic failure")), patch.object(
                weather, "now_utc", return_value=self.received.isoformat()), self.assertRaises(urllib.error.URLError):
            weather.capture(self.out, self.run.isoformat(), self.start.isoformat(), self.end.isoformat())
        self.assertFalse((self.out / "manifest.json").exists())
        self.assertTrue((self.out / "failure.json").exists())

    def test_existing_directory_and_symlink_output_not_overwritten(self):
        self.out.mkdir()
        sentinel = self.out / "keep"
        sentinel.write_bytes(b"keep me")
        alias = self.root / "alias"
        alias.symlink_to(self.out)
        with patch.object(weather, "download") as fetch:
            for destination in (self.out, alias):
                with self.subTest(destination=destination), self.assertRaises(FileExistsError):
                    weather.capture(destination, self.run.isoformat(), self.start.isoformat(), self.end.isoformat())
            fetch.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"keep me")

    def test_snapshot_and_payload_symlinks_rejected(self):
        self.capture()
        alias = self.root / "alias"
        alias.symlink_to(self.out)
        with self.assertRaises(ValueError):
            weather.verify(alias)
        for filename in ("forecast.json", "manifest.json"):
            with self.subTest(filename=filename):
                path = self.out / filename
                original = path.read_bytes()
                target = self.root / filename
                target.write_bytes(original)
                path.unlink()
                path.symlink_to(target)
                with self.assertRaises(ValueError):
                    weather.verify(self.out)
                path.unlink()
                path.write_bytes(original)

    def test_atomic_publication_does_not_overwrite_collision(self):
        link = os.link
        def collide(source, target):
            Path(target).write_bytes(b"existing manifest")
            link(source, target)
        with patch.object(weather.os, "link", side_effect=collide), self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual((self.out / "manifest.json").read_bytes(), b"existing manifest")

    def test_invalid_capture_clocks_rejected(self):
        self.capture()
        original = (self.out / "manifest.json").read_bytes()
        changes = [lambda m: m["http"]["forecast"].update(monotonic_elapsed_seconds=-1),
                   lambda m: m["http"]["forecast"].update(monotonic_elapsed_seconds=100),
                   lambda m: m["http"]["forecast"].update(retrieval_finished_at_utc=(self.received - timedelta(days=1)).isoformat()),
                   lambda m: m.update(capture_finished_at_utc=(self.received - timedelta(seconds=1)).isoformat())]
        for index, change in enumerate(changes):
            with self.subTest(case=index):
                (self.out / "manifest.json").write_bytes(original)
                self.alter_manifest(change)
                with self.assertRaises(ValueError):
                    weather.verify(self.out)

    def test_prediction_bundle_binds_weather_and_remains_declared_only(self):
        self.capture()
        for features in (False, True):
            with self.subTest(features=features):
                result = weather.check_predictions(self.out, self.bundle(features=features))
                self.assertEqual(result["status"], "TIMING_REVIEW")
                self.assertEqual(result["locally_prospective_hours"], 3)
                self.assertEqual(result["missing_prediction_hours"], 0)
                self.assertEqual(result["model_identity"], "declared_only")
                self.assertEqual(result["training_and_feature_provenance"], "unverified")
                self.assertEqual(result["weather_manifest_sha256"], weather.verify(self.out)["manifest_sha256"])
                self.assertEqual(result["features_sha256"] is not None, features)

    def test_prediction_binding_and_contract_mismatches_rejected(self):
        self.capture()
        for field, value in [("weather_manifest_sha256", "0" * 64), ("weather_response_sha256", "0" * 64),
                             ("predictions_sha256", "0" * 64), ("features_sha256", "0" * 64),
                             ("target_support", "instant"), ("schema", True), ("contract", "other"),
                             ("model_label", " "), ("declared_model_sha256", "bad")]:
            with self.subTest(field=field):
                bundle = self.bundle(change=lambda meta: meta.update({field: value}))
                with self.assertRaises(ValueError):
                    weather.check_predictions(self.out, bundle)

    def test_prediction_bundle_requires_metadata(self):
        self.capture()
        bundle = self.bundle()
        path = bundle / "manifest.json"
        manifest = json.loads(path.read_bytes())
        del manifest["roles"]["metadata"]
        path.write_bytes(self.raw(manifest))
        with self.assertRaisesRegex(ValueError, "metadata"):
            weather.check_predictions(self.out, bundle)

    def test_prediction_receipt_before_exactly_at_and_after_support_start(self):
        self.capture()
        for delta, expected in [(-1, True), (0, True), (1, False)]:
            with self.subTest(seconds=delta):
                observed = {role: self.start + timedelta(seconds=delta) for role in handoff.ROLES}
                result = weather.check_predictions(self.out, self.bundle(observed=observed))
                self.assertEqual(result["rows"][0]["prediction_bundle_timely"], expected)
                self.assertEqual(result["rows"][0]["locally_prospective"], expected)

    def test_latest_observation_of_every_role_controls_bundle_timing(self):
        self.capture()
        late = self.start + timedelta(seconds=1)
        for role in handoff.ROLES:
            with self.subTest(role=role):
                result = weather.check_predictions(self.out, self.bundle(observed={role: late}, extra_weather=True))
                self.assertEqual(weather.instant(result["bundle_observed_at_utc"]), late)
                self.assertFalse(result["rows"][0]["locally_prospective"])
                self.assertEqual(result["locally_prospective_hours"], 2)

    def test_weather_not_received_by_declared_issue_is_not_prospective(self):
        self.capture()
        bundle = self.bundle(change=lambda m: m.update(forecast_issue_time=(self.received - timedelta(seconds=1)).isoformat()))
        result = weather.check_predictions(self.out, bundle)
        self.assertFalse(result["weather_available_by_declared_issue"])
        self.assertEqual(result["locally_prospective_hours"], 0)

    def test_future_declared_issue_rejected(self):
        self.capture()
        bundle = self.bundle(change=lambda m: m.update(forecast_issue_time=(self.start + timedelta(seconds=1)).isoformat()))
        with self.assertRaisesRegex(ValueError, "after local receipt"):
            weather.check_predictions(self.out, bundle)

    def test_equivalent_offset_targets_are_duplicates(self):
        self.capture()
        bundle = self.bundle(csv="time,predicted\n2026-10-03T01:00:00+00:00,10\n2026-10-03T04:00:00+03:00,20\n")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            weather.check_predictions(self.out, bundle)

    def test_offset_targets_normalize_and_missing_predictions_stay_explicit(self):
        self.capture()
        bundle = self.bundle(csv="time,predicted\n2026-10-03T04:00:00+03:00,10\n")
        result = weather.check_predictions(self.out, bundle)
        self.assertEqual(result["submitted_hours"], 1)
        self.assertEqual(result["missing_prediction_hours"], 2)
        self.assertEqual(weather.instant(result["rows"][0]["time"]), self.start + timedelta(hours=1))

    def test_invalid_prediction_rows_rejected(self):
        self.capture()
        for csv in ["time,predicted\n", "time,predicted,extra\n2026-10-03T01:00Z,10,x\n",
                    "time,predicted\n2026-10-03T01:00,10\n", "time,predicted\n2026-10-03T04:00Z,10\n",
                    "time,predicted\n2026-10-03T01:00Z,nan\n", "time,predicted\n2026-10-03T01:00Z,-1\n"]:
            with self.subTest(csv=csv), self.assertRaises(ValueError):
                weather.check_predictions(self.out, self.bundle(csv=csv))

    def test_duplicate_json_fields_and_nonfinite_json_rejected(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"value":NaN}', b'{"value":Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                weather.parse_json(raw)


if __name__ == "__main__":
    unittest.main()
