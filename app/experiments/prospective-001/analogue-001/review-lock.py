#!/usr/bin/env python3
"""Independent stdlib reconstruction of frozen prospective analogue artifacts."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
LOCK = HERE / "lock-001"
CAPTURE = HERE.parent / "capture-001"
ZONE = timezone(timedelta(hours=3))
METHODS = ("nwp_live", "analogue_raw", "analogue_solar")
GEOMETRY_KEYS = ("solar_scale", "mean_coszen", "solar_hour_sin", "solar_hour_cos")
ERRORS = {}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def records(raw):
    return list(csv.DictReader(io.StringIO(raw.decode())))


def close(actual, expected, category):
    assert math.isfinite(actual) and math.isfinite(expected), category
    error = abs(actual - expected)
    ERRORS[category] = max(ERRORS.get(category, 0), error)
    assert math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-10), (category, actual, expected)


def geometry(local_end):
    def solar(local):
        day = (local.date() - datetime(local.year, 1, 1).date()).days
        days = (datetime(local.year + 1, 1, 1) - datetime(local.year, 1, 1)).days
        hours = local.hour + local.minute / 60 + local.second / 3600
        angle = 2 * math.pi * (day + (hours - 12) / 24) / days
        sine, cosine = math.sin(angle), math.cos(angle)
        equation = 229.18 * (.000075 + .001868 * cosine - .032077 * sine - .014615 * math.cos(2 * angle) - .040849 * math.sin(2 * angle))
        declination = .006918 - .399912 * cosine + .070257 * sine - .006758 * math.cos(2 * angle) + .000907 * math.sin(2 * angle) - .002697 * math.cos(3 * angle) + .00148 * math.sin(3 * angle)
        minutes = hours * 60 + equation + 4 * 32.4229 - 180
        latitude = math.radians(34.7744)
        coszen = math.sin(latitude) * math.sin(declination) + math.cos(latitude) * math.cos(declination) * math.cos(math.radians(minutes / 4 - 180))
        phase = minutes * 2 * math.pi / 1440
        return coszen, math.sin(phase), math.cos(phase)
    start = local_end - timedelta(hours=1)
    samples = [solar(start + timedelta(minutes=i))[0] for i in (5, 15, 25, 35, 45, 55)]
    _, sine, cosine = solar(start + timedelta(minutes=30))
    return max(100, 1000 * math.fsum(max(0, c) for c in samples) / 6), math.fsum(samples) / 6, sine, cosine


def quantile(values, fraction):
    ordered = sorted(values)
    position = (len(values) - 1) * fraction
    lower = math.floor(position)
    return ordered[lower] + (ordered[min(lower + 1, len(values) - 1)] - ordered[lower]) * (position - lower)


def keyed(rows, fields):
    result = {tuple(row[key] for key in fields): row for row in rows}
    assert len(result) == len(rows), ("duplicate keys", fields)
    return result


def run():
    manifest_raw = (LOCK / "manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    assert sha(manifest_raw) == "e20601b627197a67a81b1e4867625de4697cb755ec5c9d2b1886f0bb3b5a8f8c"
    assert sha((HERE / "PROTOCOL.md").read_bytes()) == manifest["protocol_sha256"]
    assert sha((HERE / "run.py").read_bytes()) == manifest["adapter_sha256"]
    identities = (HERE / "input-identities.json").read_bytes()
    assert sha(identities) == manifest["input_identities_sha256"]
    assert json.loads(identities) == manifest["input_sha256"]
    sources = {}
    for relative, digest in manifest["input_sha256"].items():
        sources[relative] = (ROOT / relative).read_bytes()
        assert sha(sources[relative]) == digest, relative
    outputs = {}
    for name, digest in manifest["output_sha256"].items():
        outputs[name] = (LOCK / name).read_bytes()
        assert sha(outputs[name]) == digest, name
    capture_raw = (CAPTURE / "capture/manifest.json").read_bytes()
    assert sha(capture_raw) == manifest["capture_manifest_sha256"]
    capture = json.loads(capture_raw)
    for role in capture["roles"].values():
        payload = (CAPTURE / "capture" / role["payload"]).read_bytes()
        assert sha(payload) == role["sha256"] and len(payload) == role["bytes"]
        assert payload == (CAPTURE / role["basename"]).read_bytes()
    selected = json.loads((CAPTURE / "selected-targets.json").read_bytes())
    raw_live = json.loads((CAPTURE / "response.json").read_bytes())["hourly"]
    live = {t: (q, c) for t, q, c in zip(raw_live["time"], raw_live["shortwave_radiation"], raw_live["cloud_cover"])}
    cutoff = datetime.fromisoformat(capture["capture_finished_at_utc"])
    starts = [datetime.fromisoformat(row["interval_start_utc"]) for group in selected["targets"].values() for row in group["intervals"]]
    lock_start, lock_end = (datetime.fromisoformat(manifest[key]) for key in ("lock_started_at_utc", "lock_finished_at_utc"))
    assert cutoff <= lock_start <= lock_end < min(starts)
    source_features = records(sources["data/features.csv"])
    weather = {row["time"]: float(row["shortwave_radiation"]) for row in records(sources["data/paphos_weather_data.csv"])}
    archive = json.loads(sources["app/experiments/nwp-archive-001/archive.json"])["hourly"]
    historical = {t: (q, c) for t, q, c in zip(archive["time"], archive["shortwave_radiation_previous_day2"], archive["cloud_cover_previous_day2"])}
    bank = records(outputs["training-bank.csv"])
    expected = []
    for source in source_features:
        origin = datetime.fromisoformat(source["time"])
        target = origin + timedelta(hours=24)
        epoch = int(target.replace(tzinfo=ZONE).timestamp())
        if datetime.fromtimestamp(epoch, timezone.utc) < cutoff:
            assert float(source["target"]) == weather[str(target)]
            expected.append((source, target, epoch))
    assert len(bank) == len(expected) == manifest["training"]["hours"] == 17832
    assert len(set(row["feature_time"] for row in bank)) == len(bank)
    reconstructed = []
    for row, (source, target, epoch) in zip(bank, expected):
        assert row["feature_time"] == source["time"] and row["target_time_fixed_plus03"] == str(target)
        assert int(row["target_epoch_utc"]) == epoch
        q, cloud = historical[epoch]
        actual = float(source["target"])
        assert float(row["reference_w_m2"]) == actual and float(row["nwp_day2_w_m2"]) == q
        assert int(row["cloud_missing"]) == int(cloud is None)
        assert (row["cloud_percent"] == "") if cloud is None else float(row["cloud_percent"]) == cloud
        g = geometry(target)
        for key, value in zip(GEOMETRY_KEYS, g): close(float(row[key]), value, "geometry")
        close(float(row["residual_w_m2"]), actual - q, "residual")
        reconstructed.append((q, cloud, g, actual - q))
    assert datetime.fromtimestamp(expected[-1][2], timezone.utc).isoformat() == manifest["training"]["latest_target_utc"]
    parameters = json.loads(outputs["parameters.json"])
    median = statistics.median(cloud for _, cloud, _, _ in reconstructed if cloud is not None)
    assert median == parameters["cloud_median"]
    assert parameters["K"] == 64 and parameters["probability_cutoff"] == .5 and parameters["event_threshold_w_m2"] == 600
    features = [[q / g[0], median if cloud is None else cloud, int(cloud is None), *g[1:]] for q, cloud, g, _ in reconstructed]
    means = [math.fsum(column) / len(bank) for column in zip(*features)]
    standard = [math.sqrt(math.fsum((row[i] - means[i]) ** 2 for row in features) / len(bank)) or 1 for i in range(6)]
    for expected_value, actual_value in zip(means, parameters["feature_mean"]): close(actual_value, expected_value, "mean")
    for expected_value, actual_value in zip(standard, parameters["feature_std"]): close(actual_value, expected_value, "std")
    train = [[(value - means[i]) / standard[i] for i, value in enumerate(row)] for row in features]
    predictions = keyed(json.loads(outputs["predictions.json"]), ("target_set", "valid_time_utc", "method"))
    queries = keyed(json.loads(outputs["queries.json"]), ("target_set", "valid_time_utc"))
    scenarios = keyed(json.loads(outputs["scenarios.json"]), ("target_set", "valid_time_utc", "method"))
    neighbours = keyed(json.loads(outputs["neighbors.json"]), ("target_set", "valid_time_utc", "rank"))
    assert len(predictions) == 144 and len(queries) == 48 and len(scenarios) == 96 and len(neighbours) == 3072
    threshold_margin = math.inf
    for group, data in selected["targets"].items():
        assert len(data["intervals"]) == 24
        earliest = cutoff + timedelta(hours=24 if group == "primary" else 48)
        first = earliest.replace(minute=0, second=0, microsecond=0)
        if first < earliest: first += timedelta(hours=1)
        for order, row in enumerate(data["intervals"]):
            valid = datetime.fromisoformat(row["valid_time_utc"])
            start = datetime.fromisoformat(row["interval_start_utc"])
            assert start == first + timedelta(hours=order) and valid - start == timedelta(hours=1)
            assert row["start_lead_seconds"] == (start - cutoff).total_seconds() and row["valid_time_lead_seconds"] == (valid - cutoff).total_seconds()
            q, cloud = live[int(valid.timestamp())]
            assert q == row["shortwave_radiation_w_m2"] and cloud == row["cloud_cover_percent"]
            key = (group, row["valid_time_utc"])
            query = queries[key]
            assert all(query[k] == v for k, v in row.items())
            g = geometry(valid.astimezone(ZONE).replace(tzinfo=None))
            for field, value in zip(GEOMETRY_KEYS, g): close(query[field], value, "query_geometry")
            raw_prediction = predictions[(*key, "nwp_live")]
            assert raw_prediction["point_w_m2"] == q and raw_prediction["probability"] == int(q > 600)
            assert raw_prediction["predicted_positive"] == int(q > 600)
            assert raw_prediction["interval_low_w_m2"] is None and raw_prediction["interval_high_w_m2"] is None
            raw_features = [q / g[0], median if cloud is None else cloud, int(cloud is None), *g[1:]]
            transformed = [(value - means[i]) / standard[i] for i, value in enumerate(raw_features)]
            distances = [math.fsum((a - b) ** 2 for a, b in zip(row, transformed)) for row in train]
            chosen = sorted(range(len(bank)), key=lambda i: (distances[i], expected[i][0]["time"]))[:64]
            for rank, index in enumerate(chosen):
                saved = neighbours[(*key, rank)]
                assert saved["source_feature_time"] == expected[index][0]["time"], (key, rank, saved["source_feature_time"], expected[index][0]["time"])
                assert saved["source_target_epoch_utc"] == expected[index][2]
                close(saved["distance_squared"], distances[index], "distance")
            for method in METHODS:
                prediction = predictions[(*key, method)]
                assert prediction["status"] == "known"
                for field in ("interval_start_utc", "start_lead_seconds", "valid_time_lead_seconds"):
                    assert prediction[field] == row[field]
                if method == "nwp_live": continue
                values = [max(0, q + reconstructed[i][3] * (g[0] / reconstructed[i][2][0] if method == "analogue_solar" else 1)) for i in chosen]
                saved = scenarios[(*key, method)]
                for i, value in enumerate(values):
                    close(saved[f"scenario_{i}"], value, "scenario")
                    threshold_margin = min(threshold_margin, abs(value - 600))
                probability = sum(value > 600 for value in values) / 64
                assert prediction["probability"] == probability and prediction["predicted_positive"] == int(probability > .5)
                close(prediction["point_w_m2"], statistics.median(values), "median")
                close(prediction["interval_low_w_m2"], quantile(values, .05), "quantile")
                close(prediction["interval_high_w_m2"], quantile(values, .95), "quantile")
    csv_predictions = records(outputs["predictions.csv"])
    assert len(csv_predictions) == 144
    for row in csv_predictions:
        saved = predictions[(row["target_set"], row["valid_time_utc"], row["method"])]
        for field, value in saved.items():
            if value is None: assert row[field] == ""
            elif type(value) in (int, float): close(float(row[field]), value, "prediction_csv")
            else: assert row[field] == value
    return {"status": "PASS_NO_BLOCKER", "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "review_script_sha256": sha(Path(__file__).read_bytes()), "lock_manifest_sha256": sha(manifest_raw),
            "input_files_verified": len(sources), "output_files_verified": len(outputs), "historical_rows_reconstructed": len(bank),
            "queries_reconstructed": 48, "shared_neighbors_reconstructed": 3072, "scenario_values_reconstructed": 6144,
            "predictions_reconstructed": 144, "maximum_absolute_numeric_errors": ERRORS,
            "numeric_comparison": "stdlib independent algebra; relative1e-11/absolute1e-10 only for real-valued reconstruction; IDs, membership and decisions exact",
            "minimum_scenario_distance_from_event_threshold_w_m2": threshold_margin,
            "minimum_capture_to_interval_start_hours": (min(starts) - cutoff).total_seconds() / 3600,
            "minimum_candidate_lock_to_interval_start_hours": (min(starts) - lock_end).total_seconds() / 3600,
            "minimum_candidate_lock_to_valid_endpoint_hours": (min(starts) + timedelta(hours=1) - lock_end).total_seconds() / 3600,
            "limits": ["First candidate interval starts less than24h after candidate lock; capture-based lead is a distinct clock.",
                       "Archive training vintage differs from this live capture; provider issuance/publication unverified.",
                       "No future reference, accuracy, joint-trajectory claim or promotion assessed."]}


if __name__ == "__main__":
    try:
        result = run()
    except Exception as error:
        result = {"status": "FAIL", "at_utc": datetime.now(timezone.utc).isoformat(),
                  "review_script_sha256": sha(Path(__file__).read_bytes()), "error": f"{type(error).__name__}: {error}"}
    with (HERE / "review-lock-result.json").open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS_NO_BLOCKER" else 1)
