#!/usr/bin/env python3
"""One immutable prospective forecast capture; no truth download or accuracy scoring."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time
import types
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
HELPER_PATH = HERE.parents[1] / "scripts/record_forecast_handoff.py"
FIELDS = ("shortwave_radiation", "cloud_cover")
PARAMETERS = {"latitude": "34.7744", "longitude": "32.4229", "hourly": ",".join(FIELDS),
              "models": "ecmwf_ifs025", "timezone": "GMT", "timeformat": "unixtime", "forecast_days": "7"}
URL = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(PARAMETERS)
HOUR = timedelta(hours=1)
MAX_RESPONSE = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc)


def iso(value):
    return value.isoformat(timespec="microseconds")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"bytes": len(raw), "sha256": digest(raw)}


def parse_payload(raw):
    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    data = json.loads(raw, parse_constant=invalid_constant)
    if not isinstance(data, dict) or type(data.get("utc_offset_seconds")) is not int or data["utc_offset_seconds"] != 0:
        raise ValueError("Response must declare UTC offset zero")
    units = data.get("hourly_units", {})
    if units.get("time") != "unixtime" or units.get(FIELDS[0]) != "W/m²" or units.get(FIELDS[1]) != "%":
        raise ValueError("Unexpected hourly units")
    hourly = data.get("hourly")
    if not isinstance(hourly, dict) or any(not isinstance(hourly.get(key), list) for key in ("time", *FIELDS)):
        raise ValueError("Missing hourly arrays")
    times = hourly["time"]
    if len(times) != 168 or any(type(t) is not int or t % 3600 for t in times):
        raise ValueError("Expected 168 whole UTC hourly timestamps")
    if times[0] % 86400 or any(b - a != 3600 for a, b in zip(times, times[1:])):
        raise ValueError("Duplicate, missing, unordered hours or non-midnight start")
    for key in FIELDS:
        if len(hourly[key]) != len(times):
            raise ValueError("Hourly array lengths differ")
        for value in hourly[key]:
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value)
                                      or value < 0 or (key == "cloud_cover" and value > 100)):
                raise ValueError(f"Invalid {key} value")
    rows = []
    for endpoint, radiation, cloud in zip(times, hourly[FIELDS[0]], hourly[FIELDS[1]]):
        end = datetime.fromtimestamp(endpoint, timezone.utc)
        rows.append({"interval_start_utc": iso(end - HOUR), "valid_time_utc": iso(end),
                     "shortwave_radiation_w_m2": radiation, "cloud_cover_percent": cloud,
                     "event_gt_600": None if radiation is None else int(radiation > 600)})
    return data, rows


def csv_bytes(rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def targets(rows, finished):
    if finished.tzinfo is None or finished.utcoffset() != timedelta(0):
        raise ValueError("Capture completion must be explicit UTC")
    by_start = {row["interval_start_utc"]: row for row in rows}
    if len(by_start) != len(rows):
        raise ValueError("Duplicate target intervals")
    result = {}
    for name, hours in (("primary", 24), ("secondary", 48)):
        cutoff = finished + hours * HOUR
        start = cutoff.replace(minute=0, second=0, microsecond=0)
        if start < cutoff:
            start += HOUR
        selected = []
        for index in range(24):
            interval_start = start + index * HOUR
            row = by_start.get(iso(interval_start))
            if row is None or row["valid_time_utc"] != iso(interval_start + HOUR):
                raise ValueError(f"Incomplete {name} target coverage")
            selected.append({**row, "start_lead_seconds": (interval_start - finished).total_seconds(),
                             "valid_time_lead_seconds": (interval_start + HOUR - finished).total_seconds()})
        result[name] = {"minimum_interval_start_lead_hours": hours, "intervals": selected,
                        "null_radiation_count": sum(row["shortwave_radiation_w_m2"] is None for row in selected)}
    return result


def run(output):
    output = Path(output)
    output.mkdir()  # Never reuse or overwrite an attempt, including an interrupted one.
    identities = {"protocol": digest((HERE / "PROTOCOL.md").read_bytes()),
                  "script": digest(Path(__file__).read_bytes()), "helper": digest(HELPER_PATH.read_bytes())}
    request_record = {"url": URL, "parameters": PARAMETERS, "identities_sha256": identities,
                      "started_at_utc": iso(now()), "scope": "Capture only; no accuracy or verified issuance claim"}
    save(output / "request.json", request_record)
    started = time.monotonic()
    try:
        request = urllib.request.Request(URL, headers={"User-Agent": "Aktina-prospective-capture/1", "Accept": "application/json"})
        try:
            response = urllib.request.urlopen(request, timeout=90)
        except urllib.error.HTTPError as error:
            response = error  # Retain HTTP failure bodies and headers too.
        with response:
            raw = response.read(MAX_RESPONSE + 1)
            response_record = {"status": response.status, "url": response.geturl(),
                               "headers": response.headers.as_string(), "http_date": response.headers.get("Date"),
                               "finished_at_utc": iso(now()), "elapsed_monotonic_seconds": time.monotonic() - started}
        response_identity = save(output / "response.json", raw)
        save(output / "response-metadata.json", response_record)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("Response exceeds two MiB limit; retained prefix is incomplete")
        if response_record["status"] != 200 or response_record["url"] != URL:
            raise ValueError("Request did not return HTTP 200 at the fixed endpoint")
        if datetime.fromisoformat(response_record["finished_at_utc"]) < datetime.fromisoformat(request_record["started_at_utc"]):
            raise ValueError("Local wall clock moved backwards during retrieval")
        data, rows = parse_payload(raw)
        predictions_identity = save(output / "predictions-full.csv", csv_bytes(rows))
        metadata = {"request": request_record, "response": response_record,
                    "raw_response": response_identity, "predictions_full": predictions_identity,
                    "returned_location": {key: data.get(key) for key in ("latitude", "longitude", "elevation", "timezone", "utc_offset_seconds")},
                    "hour_count": len(rows), "null_counts": {key: data["hourly"][key].count(None) for key in FIELDS},
                    "timing": "Observed retrieval, not model issuance; no authenticated timestamp or source attestation"}
        save(output / "capture-metadata.json", metadata)
        helper_raw = HELPER_PATH.read_bytes()
        if digest(helper_raw) != identities["helper"]:
            raise ValueError("Capture helper changed during retrieval")
        helper = types.ModuleType("supplied_capture")
        exec(compile(helper_raw, str(HELPER_PATH), "exec"), helper.__dict__)
        helper.capture({"predictions": output / "predictions-full.csv", "weather": output / "response.json",
                        "metadata": output / "capture-metadata.json"}, output / "capture")
        verified = helper.verify(output / "capture")
        save(output / "byte-verification.json", verified)
        manifest = json.loads((output / "capture/manifest.json").read_bytes())
        finished = datetime.fromisoformat(manifest["capture_finished_at_utc"])
        if finished < datetime.fromisoformat(response_record["finished_at_utc"]):
            raise ValueError("Capture completion predates retrieval")
        selection = {"schema": 1, "threshold_w_m2": 600, "event_operator": ">", "capture_finished_at_utc": iso(finished),
                     "capture_manifest_sha256": verified["manifest_sha256"], "identities_sha256": identities,
                     "raw_response": response_identity, "predictions_full": predictions_identity,
                     "frozen_at_utc": iso(now()), "targets": targets(rows, finished),
                     "scope": "Prospective forecast only; no accuracy claim, issuance proof or original-model comparison"}
        if datetime.fromisoformat(selection["frozen_at_utc"]) < finished:
            raise ValueError("Target generation predates capture completion")
        if datetime.fromisoformat(selection["frozen_at_utc"]) >= datetime.fromisoformat(selection["targets"]["primary"]["intervals"][0]["interval_start_utc"]):
            raise ValueError("Target manifest was not frozen before the first target")
        selected_identity = save(output / "selected-targets.json", selection)
        receipt = {"status": "CAPTURED_BYTES_VERIFIED_NO_ACCURACY", "finished_at_utc": iso(now()),
                   "capture_finished_at_utc": iso(finished), "http_date": response_record["http_date"],
                   "all_hours": len(rows), "selected_hours": 48, "selected_targets": selected_identity,
                   "raw_response": response_identity, "null_counts": metadata["null_counts"]}
        save(output / "receipt.json", receipt)
        return receipt
    except Exception as error:
        save(output / "failure.json", {"status": "FAILED", "at_utc": iso(now()), "error": f"{type(error).__name__}: {error}"})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New attempt directory; never reused")
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.output), indent=2))
    except Exception as error:
        print(f"FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
