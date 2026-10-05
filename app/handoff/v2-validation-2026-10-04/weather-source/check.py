"""Inspect retained weather availability only. No metrics, network or training."""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ARCHIVE = ROOT / "app/experiments/nwp-archive-001"
OFFSET = timezone(timedelta(hours=3))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def times(path):
    with path.open(newline="") as stream:
        values = [datetime.fromisoformat(row["time"]) for row in csv.DictReader(stream)]
    assert values == sorted(set(values)), str(path)
    assert all(b - a == timedelta(hours=1) for a, b in zip(values, values[1:]))
    assert all(value.tzinfo is None for value in values)
    return values


def inspect():
    protocol = json.loads((ARCHIVE / "protocol.json").read_text())
    requests = json.loads((ARCHIVE / "requests.json").read_text())
    request, = [item for item in requests if item["label"] == "archive"]
    raw = json.loads((ARCHIVE / "archive.json").read_text())
    assert sha(ARCHIVE / "archive.json") == request["sha256"]
    assert request["curl_exit"] == 0 and request["http_status"] == "200"
    assert protocol["forecast_model"] == "ecmwf_ifs025"
    assert protocol["recovered_fixed_offset_seconds"] == 10800
    assert raw["utc_offset_seconds"] == 0 and raw["timezone"] == "GMT"
    hourly = raw["hourly"]
    epochs = hourly["time"]
    assert all(type(value) is int for value in epochs)
    assert epochs == sorted(set(epochs))
    assert all(b - a == 3600 for a, b in zip(epochs, epochs[1:]))
    positions = {value: index for index, value in enumerate(epochs)}
    fields = protocol["fields"]
    assert all(len(hourly[field]) == len(epochs) for field in fields)
    assert all(value is None or math.isfinite(value)
               for field in fields for value in hourly[field])

    def coverage(indices):
        return {field: {"available": sum(hourly[field][i] is not None for i in indices),
                        "null": sum(hourly[field][i] is None for i in indices)}
                for field in fields}

    features = times(ROOT / "data/features.csv")
    cv = times(ROOT / "eval/cv_predictions.csv")
    test = times(ROOT / "eval/test_predictions.csv")
    rest_count = math.ceil(len(features) * 0.4)
    test_count = math.ceil(rest_count * 0.5)
    train_count = len(features) - rest_count
    assert cv == features[train_count:-test_count]
    assert test == features[-test_count:]
    periods = {}
    for name, origins in (("original_training", features[:train_count]),
                          ("original_validation", cv), ("original_test", test),
                          ("original_final_training", features[:-test_count])):
        targets = [value.replace(tzinfo=OFFSET) + timedelta(hours=24) for value in origins]
        target_epochs = [int(value.timestamp()) for value in targets]
        indices = [positions[value] for value in target_epochs if value in positions]
        periods[name] = {
            "hours": len(origins), "matched_archive_hours": len(indices),
            "missing_archive_hours": len(origins) - len(indices),
            "origin_first_naive": origins[0].isoformat(),
            "origin_last_naive": origins[-1].isoformat(),
            "target_first_fixed_plus03": targets[0].isoformat(),
            "target_last_fixed_plus03": targets[-1].isoformat(),
            "target_first_utc": targets[0].astimezone(timezone.utc).isoformat(),
            "target_last_utc": targets[-1].astimezone(timezone.utc).isoformat(),
            "fields": coverage(indices),
        }
    null_times = {}
    for field in fields:
        missing = [epoch for epoch, value in zip(epochs, hourly[field]) if value is None]
        null_times[field] = {
            "hours": len(missing),
            "first_fixed_plus03": datetime.fromtimestamp(missing[0], OFFSET).isoformat() if missing else None,
            "last_fixed_plus03": datetime.fromtimestamp(missing[-1], OFFSET).isoformat() if missing else None,
        }
    sources = [ARCHIVE / name for name in ("archive.json", "protocol.json", "requests.json")]
    sources += [ROOT / name for name in ("data/features.csv", "eval/cv_predictions.csv",
                "eval/test_predictions.csv", "model/model.py", "model/final_model.py")]
    return {
        "kind": "retained_weather_availability_only", "status": "PASS",
        "check_sha256": sha(Path(__file__)),
        "reproduce": "python3 app/handoff/v2-validation-2026-10-04/weather-source/check.py --check",
        "input_sha256": {str(path.relative_to(ROOT)): sha(path) for path in sources},
        "request": request,
        "model_pin": protocol["forecast_model"],
        "returned_metadata": {key: raw[key] for key in
                              ("latitude", "longitude", "elevation", "timezone", "utc_offset_seconds")},
        "units": raw["hourly_units"],
        "raw_hours": len(epochs), "raw_coverage": coverage(range(len(epochs))),
        "raw_null_ranges": null_times, "periods": periods,
        "split_definition": "Original chronological 60/20/20 split, checked against both saved evaluation timestamp sets. Final training is train plus validation. No 24-hour purge is applied in these original split counts.",
        "clock": "Archive UTC epoch seconds. Original naive CSV origin labels are interpreted at recovered fixed +03:00, not Europe/Nicosia DST. Target = origin + 24 hours.",
        "availability_limit": "day1/day2 are provider-declared nominal previous-day offsets, not verified issuance or publication times. At target = origin +24h, day1 is nominally at origin and day2 nominally 24h before origin. Saved coverage does not prove live availability or original operational vintages.",
        "work_performed": "Only timestamps and weather fields were inspected. No outcome values, predictions, training or skill metrics were used. No network requests made.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true", help="Create the receipt once without overwriting")
    modes.add_argument("--check", action="store_true", help="Verify the existing receipt without writing")
    args = parser.parse_args()
    result = inspect()
    output = HERE / "ecmwf-source.json"
    if args.check:
        assert json.loads(output.read_text()) == result, "Saved source receipt differs"
        print(json.dumps({"status": "PASS", "inputs": len(result["input_sha256"]),
                          "raw_hours": result["raw_hours"], "receipt_sha256": sha(output)}))
    elif args.write:
        with output.open("x") as stream:
            stream.write(json.dumps(result, indent=2) + "\n")
        print(output)
    else:
        print(json.dumps(result, indent=2))
