#!/usr/bin/env python3
"""Retain one public forecast run and audit locally observed prospective submissions."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from record_forecast_handoff import read_once, write_new, now_utc, utc_time, verify as verify_handoff

API = "https://single-runs-api.open-meteo.com/v1/forecast"
STATUS_URL = "https://api.open-meteo.com/data/ecmwf_ifs/static/meta.json"
HEADERS = {"Accept": "application/json", "User-Agent": "AquaShift-research/1.0"}
FIELDS = {"shortwave_radiation": "W/m²", "temperature_2m": "°C", "cloud_cover": "%"}
LIMIT = 2 * 1024 * 1024
SCOPE = ("Local receipt and retained bytes only; no trusted timestamp attestation, earliest publication "
         "proof, model authentication or proof of exclusive feature use. Initialization is not issue time.")
SUPPORT = "preceding_hour_mean"


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def parse_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f"Non-finite JSON value: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def instant(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("An explicit timestamp offset is required")
    return parsed.astimezone(timezone.utc)


def stamp(value):
    return value.isoformat(timespec="microseconds")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def config(run, start, end):
    times = [utc_time(value) for value in (run, start, end)]
    if any(value.minute or value.second or value.microsecond for value in times):
        raise ValueError("Run and support boundaries must be whole UTC hours")
    run, start, end = times
    if run.hour not in (0, 6, 12, 18) or not run <= start < end or end - run > timedelta(days=7):
        raise ValueError("Select a six-hour model cycle and a positive support window of at most seven days")
    return {"model": "ecmwf_ifs", "run_initialized_at_utc": stamp(run),
            "support_start_utc": stamp(start), "support_end_utc": stamp(end),
            "radiation_support": SUPPORT, "latitude": 34.7754, "longitude": 32.4245}


def urls(selection):
    start, end = (utc_time(selection[key]) for key in ("support_start_utc", "support_end_utc"))
    query = {"latitude": selection["latitude"], "longitude": selection["longitude"],
             "models": selection["model"], "run": utc_time(selection["run_initialized_at_utc"]).strftime("%Y-%m-%dT%H:%M"),
             "hourly": ",".join(FIELDS), "timezone": "GMT", "timeformat": "unixtime",
             "forecast_hours": int((end - utc_time(selection["run_initialized_at_utc"])).total_seconds() / 3600) + 1}
    return {"provider-status": STATUS_URL, "forecast": API + "?" + urllib.parse.urlencode(query)}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Forecast redirects are not accepted")


def download(url):
    request = {"method": "GET", "url": url, "headers": dict(HEADERS), "body": None}
    started, tick = now_utc(), time.monotonic()
    opener = urllib.request.build_opener(NoRedirect())
    try:
        response = opener.open(urllib.request.Request(url, headers=HEADERS), timeout=30)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(LIMIT + 1)
        finished, elapsed = now_utc(), time.monotonic() - tick
        record = {"request": request, "request_sha256": digest(encode(request)),
                  "response_status": response.status, "response_url": response.geturl(),
                  "response_headers": list(map(list, response.headers.items())),
                  "request_started_at_utc": started, "retrieval_finished_at_utc": finished,
                  "monotonic_elapsed_seconds": elapsed, "bytes": len(raw), "sha256": digest(raw)}
    if len(raw) > LIMIT:
        raise ValueError("HTTP response exceeds byte limit")
    return record, raw


def validate_record(record, url, raw):
    request = {"method": "GET", "url": url, "headers": HEADERS, "body": None}
    fields = {"request", "request_sha256", "response_status", "response_url", "response_headers",
              "request_started_at_utc", "retrieval_finished_at_utc", "monotonic_elapsed_seconds", "bytes", "sha256"}
    if set(record) != fields or record["request"] != request or record["request_sha256"] != digest(encode(request)):
        raise ValueError("Request identity mismatch")
    if type(record["bytes"]) is not int or len(raw) != record["bytes"] or digest(raw) != record["sha256"]:
        raise ValueError("Response bytes/hash mismatch")
    if record["response_status"] != 200 or record["response_url"] != url:
        raise ValueError("Snapshot needs a successful response from the exact requested endpoint")
    headers = record["response_headers"]
    if not isinstance(headers, list) or not all(isinstance(row, list) and len(row) == 2 and
            all(isinstance(value, str) for value in row) for row in headers):
        raise ValueError("Invalid response headers")
    start, end = (utc_time(record[key]) for key in ("request_started_at_utc", "retrieval_finished_at_utc"))
    elapsed = record["monotonic_elapsed_seconds"]
    if end < start or not finite(elapsed) or elapsed < 0 or abs((end - start).total_seconds() - elapsed) > 1:
        raise ValueError("Inconsistent wall and monotonic capture clocks")
    return start, end


def audit(manifest, directory, as_of=None):
    if set(manifest) != {"schema", "scope", "selection", "capture_started_at_utc", "capture_finished_at_utc", "http"}:
        raise ValueError("Unsupported snapshot fields")
    if type(manifest["schema"]) is not int or manifest["schema"] != 1 or manifest["scope"] != SCOPE:
        raise ValueError("Unsupported snapshot schema or scope")
    selection = manifest["selection"]
    expected = config(selection["run_initialized_at_utc"], selection["support_start_utc"], selection["support_end_utc"])
    if selection != expected or set(manifest["http"]) != {"provider-status", "forecast"}:
        raise ValueError("Unsupported selection or response roles")
    started, finished = (utc_time(manifest[key]) for key in ("capture_started_at_utc", "capture_finished_at_utc"))
    previous, parsed = started, {}
    for role, url in urls(selection).items():
        raw = read_once(directory / f"{role}.json", LIMIT)
        begin, end = validate_record(manifest["http"][role], url, raw)
        if not previous <= begin <= end <= finished:
            raise ValueError("Responses are outside the sequential capture window")
        if role == "forecast" and utc_time(selection["run_initialized_at_utc"]) > begin:
            raise ValueError("Requested model initialization is after retrieval began")
        parsed[role], previous = parse_json(raw), end
    record = manifest["http"]["forecast"]
    received = utc_time(record["retrieval_finished_at_utc"])
    # A small backward clock adjustment must not make a boundary-crossing read timely.
    available = max(received, utc_time(record["request_started_at_utc"]) +
                    timedelta(microseconds=math.ceil(record["monotonic_elapsed_seconds"] * 1_000_000)))
    cutoff = available if as_of is None else instant(as_of)
    forecast = parsed["forecast"]
    if (type(forecast["utc_offset_seconds"]) is not int or forecast["utc_offset_seconds"] != 0 or
            forecast["timezone"] != "GMT" or forecast["timezone_abbreviation"] != "GMT" or
            forecast["hourly_units"] != {"time": "unixtime", **FIELDS}):
        raise ValueError("Forecast units or timezone differ from the request")
    for key in ("latitude", "longitude", "elevation"):
        if not finite(forecast[key]):
            raise ValueError("Missing numeric returned grid coordinates/elevation")
    if not -90 <= forecast["latitude"] <= 90 or not -180 <= forecast["longitude"] <= 180:
        raise ValueError("Returned grid coordinates are out of range")
    start, end = (utc_time(selection[key]) for key in ("support_start_utc", "support_end_utc"))
    count = int((end - start).total_seconds() / 3600)
    hourly = forecast["hourly"]
    run = utc_time(selection["run_initialized_at_utc"])
    source_count = int((end - run).total_seconds() / 3600) + 1
    labels = [int((run + timedelta(hours=i)).timestamp()) for i in range(source_count)]
    if set(hourly) != {"time", *FIELDS} or hourly["time"] != labels or any(type(t) is not int for t in hourly["time"]):
        raise ValueError("Forecast hours must exactly cover the requested supports in UTC order")
    for key in FIELDS:
        values = hourly[key]
        if not isinstance(values, list) or len(values) != source_count:
            raise ValueError("Unequal forecast arrays")
        limits = {"shortwave_radiation": (0, 2000), "temperature_2m": (-100, 70), "cloud_cover": (0, 100)}
        low, high = limits[key]
        if any(value is not None and (not finite(value) or not low <= value <= high) for value in values):
            raise ValueError(f"Invalid {key} value")
    rows = []
    for index, label in enumerate(labels):
        support_end = datetime.fromtimestamp(label, timezone.utc)
        support_start = support_end - timedelta(hours=1)
        if support_start < start:
            continue
        value = hourly["shortwave_radiation"][index]
        rows.append({"time": stamp(support_end), "support_start_utc": stamp(support_start),
                     "support_end_utc": stamp(support_end), "shortwave_radiation_w_m2": value,
                     "locally_prospective": available <= cutoff <= support_start and value is not None})
    status = parsed["provider-status"]
    if not isinstance(status, dict) or type(status.get("last_run_initialisation_time")) is not int:
        raise ValueError("Provider status has no valid model initialization")
    return {"status": "VERIFIED_BYTES", "scope": SCOPE, "selection": selection,
            "as_of_utc": stamp(cutoff), "weather_received_at_utc": stamp(received),
            "weather_available_at_utc": stamp(available), "weather_available_by_as_of": available <= cutoff,
            "forecast_response_sha256": manifest["http"]["forecast"]["sha256"],
            "provider_status_matches_requested_run": status["last_run_initialisation_time"] == int(utc_time(selection["run_initialized_at_utc"]).timestamp()),
            "provider_publication_time": None, "boundary_policy": "receipt <= as_of <= support_start",
            "returned_grid": {key: forecast[key] for key in ("latitude", "longitude", "elevation")},
            "hours": count, "retained_source_hours": source_count,
            "missing_radiation_hours": sum(row["shortwave_radiation_w_m2"] is None for row in rows),
            "locally_prospective_hours": sum(row["locally_prospective"] for row in rows), "rows": rows}


def verify(directory, as_of=None):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Snapshot must be a regular directory")
    raw = read_once(directory / "manifest.json", 128 * 1024)
    return {**audit(parse_json(raw), directory, as_of), "manifest_sha256": digest(raw)}


def capture(output, run, start, end):
    selection = config(run, start, end)
    output = Path(output)
    output = output.parent.resolve(strict=True) / output.name
    output.mkdir(mode=0o700)
    manifest = {"schema": 1, "scope": SCOPE, "selection": selection,
                "capture_started_at_utc": now_utc(), "http": {}}
    try:
        for role, url in urls(selection).items():
            record, raw = download(url)
            write_new(output / f"{role}.json", raw)
            manifest["http"][role] = record
        manifest["capture_finished_at_utc"] = now_utc()
        audit(manifest, output)
        pending = output / ".manifest.pending"
        write_new(pending, encode(manifest))
        os.link(pending, output / "manifest.json")
        pending.unlink()
        return verify(output)
    except Exception as error:
        write_new(output / "failure.json", encode({"error": str(error), "incomplete_capture": manifest}))
        raise


def check_predictions(weather_directory, handoff_directory):
    weather = verify(weather_directory)
    handoff = verify_handoff(handoff_directory)
    roles = handoff["roles"]
    if "metadata" not in roles:
        raise ValueError("Prospective submission needs captured metadata bindings")
    def payload(role):
        raw = read_once(Path(handoff_directory) / roles[role]["payload"], 25 * 1024 * 1024)
        if digest(raw) != roles[role]["sha256"]:
            raise ValueError("Handoff changed during review")
        return raw
    meta = parse_json(payload("metadata"))
    fields = {"schema", "contract", "weather_manifest_sha256", "weather_response_sha256", "predictions_sha256",
              "features_sha256", "model_label", "declared_model_sha256", "forecast_issue_time", "target_support"}
    if set(meta) != fields or type(meta["schema"]) is not int or meta["schema"] != 1 or meta["contract"] != "aquashift_prospective_forecast":
        raise ValueError("Unsupported prospective submission contract")
    bindings = {"weather_manifest_sha256": weather["manifest_sha256"], "weather_response_sha256": weather["forecast_response_sha256"],
                "predictions_sha256": roles["predictions"]["sha256"], "features_sha256": roles.get("features", {}).get("sha256")}
    if any(meta[key] != value for key, value in bindings.items()) or meta["target_support"] != SUPPORT:
        raise ValueError("Submission binding or target support mismatch")
    if not isinstance(meta["model_label"], str) or not meta["model_label"].strip() or not isinstance(meta["declared_model_sha256"], str) or not re.fullmatch("[0-9a-f]{64}", meta["declared_model_sha256"]):
        raise ValueError("Declare model label and artifact hash; these remain unauthenticated")
    # The verified role times are first-observed times. Use the latest bound role,
    # including metadata/features, so a late attachment cannot inherit an early prediction time.
    observed = max(utc_time(row["first_observed_here_at_utc"]) for row in roles.values())
    issued = instant(meta["forecast_issue_time"])
    if issued > observed:
        raise ValueError("Declared issue is after local receipt of the bundle")
    weather_timely = utc_time(weather["weather_available_at_utc"]) <= issued
    expected = {instant(row["time"]): row for row in weather["rows"]}
    reader = csv.DictReader(io.StringIO(payload("predictions").decode("utf-8-sig"), newline=""))
    if reader.fieldnames != ["time", "predicted"]:
        raise ValueError("Prospective CSV requires exactly time,predicted, with W/m² targets")
    rows, seen = [], set()
    for row in reader:
        target, value = instant(row["time"]), float(row["predicted"])
        if set(row) != {"time", "predicted"} or target in seen or target not in expected or not math.isfinite(value) or not 0 <= value <= 2000:
            raise ValueError("Invalid, duplicate or out-of-window prediction")
        seen.add(target)
        support = expected[target]
        timely = observed <= instant(support["support_start_utc"])
        rows.append({**support, "predicted_w_m2": value, "prediction_bundle_timely": timely,
                     "locally_prospective": weather_timely and timely and support["shortwave_radiation_w_m2"] is not None})
    if not rows:
        raise ValueError("Empty prediction file")
    return {"status": "TIMING_REVIEW", "scope": SCOPE, **bindings,
            "handoff_manifest_sha256": handoff["manifest_sha256"], "declared_model_sha256": meta["declared_model_sha256"],
            "model_label": meta["model_label"], "model_identity": "declared_only",
            "training_and_feature_provenance": "unverified", "declared_issue_time_utc": stamp(issued),
            "bundle_observed_at_utc": stamp(observed), "weather_available_by_declared_issue": weather_timely,
            "submitted_hours": len(rows), "missing_prediction_hours": len(expected) - len(rows),
            "locally_prospective_hours": sum(row["locally_prospective"] for row in rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("capture")
    for name in ("output", "run", "start", "end"):
        record.add_argument("--" + name, required=True)
    check = sub.add_parser("verify")
    check.add_argument("directory")
    check.add_argument("--as-of")
    predictions = sub.add_parser("check-predictions")
    predictions.add_argument("--weather", required=True)
    predictions.add_argument("--handoff", required=True)
    args = parser.parse_args()
    try:
        if args.command == "capture":
            result = capture(args.output, args.run, args.start, args.end)
        elif args.command == "verify":
            result = verify(args.directory, args.as_of)
        else:
            result = check_predictions(args.weather, args.handoff)
        print(encode(result).decode(), end="")
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError, csv.Error) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
