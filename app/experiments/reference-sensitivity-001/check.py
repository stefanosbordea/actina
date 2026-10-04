#!/usr/bin/env python3
"""Audit fixed predictions under two references; never fit, select or fetch."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INPUTS_SHA = "bf531f74aa236079ee6a20ccd52b54f4133963e9635413e0275e0dc8df6ba45b"
AMENDMENT_SHA = "18d32d96714916383870f9df1b49236377c10cad59054ee4e149df37618e9ce1"
METHODS = ("original", "persistence", "nwp_day2", "median_bias", "ridge_bias", "global_residual", "analogue_raw", "analogue_solar")
SCENARIOS = set(METHODS[-3:])
OFFSET = timezone(timedelta(hours=3))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)


def read_csv(raw):
    return list(csv.DictReader(io.StringIO(raw.decode())))


def table_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


def number(value):
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("Nonfinite forecast/reference value")
    return result


def naive_hour(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is not None or result.minute or result.second or result.microsecond:
        raise ValueError("Expected naive whole-hour source label")
    return result


def utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def default_prediction(row, method):
    point, probability = number(row["point_w_m2"]), number(row["probability"])
    if not 0 <= probability <= 1 or row["default_positive"] not in ("0", "1"):
        raise ValueError("Invalid probability/default decision")
    predicted = int(row["default_positive"])
    expected = int(probability > .5) if method in SCENARIOS else int(point > 600)
    if predicted != expected or (method not in SCENARIOS and probability != expected):
        raise ValueError("Saved default decision contradicts the fixed rule")
    return point, predicted


def scores(actual, points, decisions):
    if len(actual) != len(points) or len(actual) != len(decisions):
        raise ValueError("Unequal metric membership")
    tp = fp = fn = tn = 0
    for value, decision in zip(actual, decisions):
        positive = value > 600
        if decision:
            if positive: tp += 1
            else: fp += 1
        elif positive: fn += 1
        else: tn += 1
    count = len(actual)
    return {"hours": count, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
            "mae": math.fsum(abs(p - a) for p, a in zip(points, actual)) / count if count else None,
            "rmse": math.sqrt(math.fsum((p - a) ** 2 for p, a in zip(points, actual)) / count) if count else None}


def missing_spans(epochs):
    result = []
    for epoch in epochs:
        if result and epoch == result[-1][1] + 3600:
            result[-1][1], result[-1][2] = epoch, result[-1][2] + 1
        else:
            result.append([epoch, epoch, 1])
    return [{"first_valid_time_utc": utc(first), "last_valid_time_utc": utc(last), "hours": count}
            for first, last, count in result]


def assess_split(original, predictions, joins, satellite):
    if set(predictions) != set(METHODS) or any(len(rows) != len(original) for rows in predictions.values()):
        raise ValueError("Missing method or forecast rows; no prediction intersection allowed")
    origins = [naive_hour(row["time"]) for row in original]
    if len(set(origins)) != len(origins) or origins != sorted(origins):
        raise ValueError("Duplicate or unordered original origins")
    membership, serialization = [], []
    for index, source in enumerate(original):
        origin = origins[index]
        actual = number(source["actual"])
        target = origin + timedelta(hours=24)
        epoch = int(target.replace(tzinfo=OFFSET).timestamp())
        if origin not in joins or joins[origin] != (target, epoch):
            raise ValueError("Missing/changed target join or fixed+03 disagreement")
        if epoch not in satellite:
            raise ValueError("Satellite timestamp absent, not a declared null")
        reference = satellite[epoch]
        if reference is not None and (type(reference) not in (int, float) or not math.isfinite(reference) or reference < 0):
            raise ValueError("Invalid satellite reference")
        row = {"feature_time": source["time"], "target_time": target.isoformat(sep=" "),
               "target_epoch_utc": epoch, "valid_time_utc": utc(epoch), "weather_reference_w_m2": actual,
               "satellite_reference_w_m2": reference, "reference_available": int(reference is not None)}
        for method in METHODS:
            prediction = predictions[method][index]
            if naive_hour(prediction["feature_time"]) != origin or naive_hour(prediction["target_time"]) != target:
                raise ValueError(f"Changed or missing forecast membership: {method}")
            if number(prediction["actual_w_m2"]) != actual:
                raise ValueError("Changed saved weather reference")
            point, decision = default_prediction(prediction, method)
            if method in ("original", "persistence"):
                supplied = number(source["predicted" if method == "original" else "baseline"])
                if point != supplied:
                    difference = abs(point - supplied)
                    ulps = difference / max(math.ulp(point), math.ulp(supplied))
                    if method != "original" or ulps > 4 or decision != int(supplied > 600):
                        raise ValueError(f"Changed supplied {method} prediction beyond the amendment")
                    serialization.append({"feature_time": source["time"], "supplied_point_text": source["predicted"],
                                          "saved004_point_text": prediction["point_w_m2"], "absolute_difference": difference, "ulps": ulps})
            row[method + "_point_w_m2"] = point
            row[method + "_default_positive"] = decision
        membership.append(row)
    available = [row for row in membership if row["reference_available"]]
    null_epochs = [row["target_epoch_utc"] for row in membership if not row["reference_available"]]
    coverage = {"original_hours": len(membership), "scored_hours": len(available), "unscored_hours": len(null_epochs),
                "scored_fraction": len(available) / len(membership) if membership else None,
                "unscored_fraction": len(null_epochs) / len(membership) if membership else None,
                "unscored_spans": missing_spans(null_epochs)}
    cross = {"weather0_satellite0": 0, "weather0_satellite1": 0, "weather1_satellite0": 0, "weather1_satellite1": 0}
    for row in available:
        cross[f"weather{int(row['weather_reference_w_m2'] > 600)}_satellite{int(row['satellite_reference_w_m2'] > 600)}"] += 1
    metrics = {}
    for method in METHODS:
        metrics[method] = {}
        for basis, rows, reference in (("weather_full", membership, "weather_reference_w_m2"),
                                        ("weather_common", available, "weather_reference_w_m2"),
                                        ("satellite_common", available, "satellite_reference_w_m2")):
            metrics[method][basis] = scores([row[reference] for row in rows], [row[method + "_point_w_m2"] for row in rows],
                                             [row[method + "_default_positive"] for row in rows])
    return {"coverage": coverage, "reference_event_cross_tabulation": cross, "methods": metrics,
            "original_control_serialization": {"different_rows": len(serialization),
                "maximum_ulps": max((row["ulps"] for row in serialization), default=0),
                "maximum_absolute_difference": max((row["absolute_difference"] for row in serialization), default=0),
                "event_changes": 0, "differences": serialization}}, membership


def run(output):
    output = Path(output)
    output.mkdir()
    try:
        frozen_raw = (HERE / "inputs.json").read_bytes()
        if sha(frozen_raw) != INPUTS_SHA:
            raise ValueError("Frozen input manifest changed")
        if sha((HERE / "serialization-amendment.json").read_bytes()) != AMENDMENT_SHA:
            raise ValueError("Reviewed serialization amendment changed")
        frozen = json.loads(frozen_raw)
        if sha((HERE / "PROTOCOL.md").read_bytes()) != frozen["protocol_sha256"]:
            raise ValueError("Reviewed protocol changed")
        files = {}
        for relative, identity in frozen["inputs"].items():
            raw = (REPO / relative).read_bytes()
            if sha(raw) != identity["sha256"] or len(raw) != identity["bytes"]:
                raise ValueError(f"Frozen input changed: {relative}")
            files[relative] = raw
        source = json.loads(files["app/experiments/satellite-reference-001/result/response.json"])
        if source["utc_offset_seconds"] != 0 or source["hourly_units"] != {"time": "unixtime", "shortwave_radiation": "W/m²"}:
            raise ValueError("Satellite time/units changed")
        times, values = source["hourly"]["time"], source["hourly"]["shortwave_radiation"]
        if len(times) != len(values) or any(type(t) is not int for t in times) or any(b - a != 3600 for a, b in zip(times, times[1:])):
            raise ValueError("Satellite timestamps duplicate/missing or array lengths differ")
        satellite = dict(zip(times, values))
        joins = {}
        for row in read_csv(files["app/experiments/f1-004/result/joined-inputs.csv"]):
            origin = naive_hour(row["feature_time"])
            target, epoch = naive_hour(row["target_time"]), int(row["target_epoch_utc"])
            if origin in joins or target != origin + timedelta(hours=24) or epoch != int(target.replace(tzinfo=OFFSET).timestamp()):
                raise ValueError("Invalid or duplicate004 join")
            joins[origin] = (target, epoch)
        report = {"status": "COMPLETE_REFERENCE_SENSITIVITY_NOT_MODEL_PROMOTION", "started_at_utc": now(),
                  "script_sha256": sha(Path(__file__).read_bytes()), "inputs_sha256": INPUTS_SHA,
                  "protocol_sha256": frozen["protocol_sha256"], "serialization_amendment_sha256": AMENDMENT_SHA,
                  "scope": "Already-inspected splits; satellite estimate, not ground sensor; no fitting or selection",
                  "splits": {}}
        flat = []
        for split, original_path, count in (("validation", "eval/cv_predictions.csv", 3566), ("test", "eval/test_predictions.csv", 3567)):
            original = read_csv(files[original_path])
            if len(original) != count:
                raise ValueError("Original split count changed")
            predictions = {method: read_csv(files[f"app/experiments/f1-004/result/predictions/{split}-{method}.csv"]) for method in METHODS}
            result, membership = assess_split(original, predictions, joins, satellite)
            save(output / f"{split}-membership.csv", table_bytes(membership))
            report["splits"][split] = result
            for method, bases in result["methods"].items():
                for basis, metrics in bases.items():
                    flat.append({"split": split, "method": method, "basis": basis, **metrics})
        report["finished_at_utc"] = now()
        save(output / "metrics.csv", table_bytes(flat))
        save(output / "report.json", report)
        return report
    except Exception as error:
        save(output / "failure.json", {"status": "FAILED", "at_utc": now(), "error": f"{type(error).__name__}: {error}"})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    try:
        report = run(parser.parse_args().output)
        print(json.dumps({"status": report["status"], "coverage": {key: value["coverage"] for key, value in report["splits"].items()}}, indent=2))
    except Exception as error:
        print(f"FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
