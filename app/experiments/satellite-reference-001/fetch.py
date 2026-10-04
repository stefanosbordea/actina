#!/usr/bin/env python3
"""Fixed-period satellite-reference acquisition; coverage checks only, never forecast scoring."""
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
import urllib.error
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
PARAMETERS = {"latitude": "34.7744", "longitude": "32.4229", "start_date": "2024-09-13", "end_date": "2026-10-01",
              "hourly": "shortwave_radiation", "models": "eumetsat_sarah3", "timezone": "GMT", "timeformat": "unixtime"}
URL = "https://satellite-api.open-meteo.com/v1/archive?" + urllib.parse.urlencode(PARAMETERS)
SAMPLE_DAYS = ("2025-12-10", "2026-07-03", "2026-10-01")
LIMIT = 2 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return {"bytes": len(raw), "sha256": sha(raw)}


def inspect(raw):
    def nonfinite(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    data = json.loads(raw, parse_constant=nonfinite)
    if type(data.get("utc_offset_seconds")) is not int or data["utc_offset_seconds"] != 0:
        raise ValueError("Response must declare UTC offset zero")
    for key, bound in (("latitude", 90), ("longitude", 180)):
        coordinate = data.get(key)
        if type(coordinate) not in (float, int) or not math.isfinite(coordinate) or abs(coordinate) > bound:
            raise ValueError(f"Invalid returned {key}")
    units = data["hourly_units"]
    if units["time"] != "unixtime" or units["shortwave_radiation"] != "W/m²":
        raise ValueError("Wrong time or radiation units")
    times, values = data["hourly"]["time"], data["hourly"]["shortwave_radiation"]
    start = datetime.fromisoformat(PARAMETERS["start_date"]).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(PARAMETERS["end_date"]).replace(tzinfo=timezone.utc) + timedelta(days=1)
    expected = list(range(int(start.timestamp()), int(end.timestamp()), 3600))
    if not isinstance(times, list) or any(type(t) is not int for t in times) or times != expected:
        raise ValueError("Wrong period, duplicate, unordered or missing UTC hours")
    if not isinstance(values, list) or len(values) != len(times):
        raise ValueError("Radiation array length differs")
    if any(value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0) for value in values):
        raise ValueError("Invalid radiation value")
    def utc(epoch):
        return datetime.fromtimestamp(epoch, timezone.utc).isoformat()
    missing = []
    first = None
    for index, value in enumerate(values + [0]):
        if value is None and first is None:
            first = index
        elif value is not None and first is not None:
            missing.append({"first_valid_time_utc": utc(times[first]), "last_valid_time_utc": utc(times[index - 1]), "hours": index - first})
            first = None
    report = {"expected_hours": len(expected), "returned_hours": len(times), "first_valid_time_utc": utc(times[0]),
              "last_valid_time_utc": utc(times[-1]), "first_interval_start_utc": utc(times[0] - 3600),
              "null_hours": values.count(None), "missing_spans": missing, "timestamp_gaps": 0,
              "returned_grid": {key: data.get(key) for key in ("latitude", "longitude", "elevation")},
              "returned_timezone": data.get("timezone"), "scope": "Satellite-derived estimate; schema and coverage only"}
    table = io.StringIO(newline="")
    writer = csv.writer(table)
    writer.writerow(("valid_time_utc", "interval_start_utc", "shortwave_radiation_w_m2", "is_missing"))
    writer.writerows((utc(t), utc(t - 3600), value, int(value is None)) for t, value in zip(times, values))
    return report, table.getvalue().encode()


def run(output):
    output = Path(output)
    output.mkdir()
    protocol = {"declared_at_utc": now(), "url": URL, "parameters": PARAMETERS,
                "script_sha256": sha(Path(__file__).read_bytes()), "protocol_sha256": sha((HERE / "PROTOCOL.md").read_bytes()),
                "known_availability_samples": [{"date": day, "raw_sha256": sha((HERE.parent / "satellite-intake-001/result" / f"{day}.json").read_bytes()),
                    "receipt_sha256": sha((HERE.parent / "satellite-intake-001/result" / f"{day}-receipt.json").read_bytes())} for day in SAMPLE_DAYS],
                "scope": "Full fixed period, no forecast scoring or target replacement"}
    save(output / "protocol.json", protocol)
    request = {"started_at_utc": now(), "url": URL}
    save(output / "request.json", request)
    started = time.monotonic()
    try:
        try:
            response = urllib.request.urlopen(urllib.request.Request(URL, headers={"User-Agent": "Aktina-satellite-intake/1", "Accept": "application/json"}), timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(LIMIT + 1)
            metadata = {"status": response.status, "url": response.geturl(), "headers": response.headers.as_string(),
                        "http_date": response.headers.get("Date"), "finished_at_utc": now(), "elapsed_monotonic_seconds": time.monotonic() - started}
        identity = save(output / "response.json", raw)
        save(output / "response-metadata.json", metadata)
        if len(raw) > LIMIT:
            raise ValueError("Response exceeds two MiB; retained prefix is incomplete")
        if metadata["status"] != 200 or metadata["url"] != URL:
            raise ValueError("Fixed endpoint did not return HTTP 200")
        if datetime.fromisoformat(metadata["finished_at_utc"]) < datetime.fromisoformat(request["started_at_utc"]):
            raise ValueError("Local clock moved backwards during request")
        report, table = inspect(raw)
        table_identity = save(output / "reference-full.csv", table)
        summary = {"status": "SCHEMA_AND_COVERAGE_VERIFIED", "forecast_scoring_performed": False,
                   "finished_at_utc": now(), "raw_response": identity, "full_csv": table_identity, **report}
        save(output / "summary.json", summary)
        return summary
    except Exception as error:
        save(output / "failure.json", {"status": "FAILED", "at_utc": now(), "error": f"{type(error).__name__}: {error}"})
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New attempt directory; never reused")
    try:
        print(json.dumps(run(parser.parse_args().output), indent=2))
    except Exception as error:
        print(f"FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
