#!/usr/bin/env python3
"""Capture supplied files locally; verify bytes, never publication or forecast timing."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

ROLES = ("predictions", "weather", "features", "metadata")
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_MANIFEST_BYTES = 128 * 1024
SCOPE = ("Local first-observed capture times only; not original NWP publication, "
         "forecast issue or training times. No source authentication or timestamp attestation.")
UNVERIFIED = {"source": "unverified", "training": "unverified", "feature_timing": "unverified"}
TOOL = "AquaShift supplied-file capture"
READ_SEMANTICS = "One bounded raw read per supplied role; hashes and payloads use that snapshot."


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def read_once(path, limit):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Symlink inputs/payloads are not accepted")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("Only regular files are accepted")
        if info.st_size > limit:
            raise ValueError("File exceeds byte limit")
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds byte limit")
    return data


def write_new(path, data):
    with Path(path).open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def utc_time(value):
    value = datetime.fromisoformat(value)
    if value.tzinfo is None or value.utcoffset().total_seconds() != 0:
        raise ValueError("Capture times must have an explicit UTC offset")
    return value


def capture(inputs, output):
    if not inputs.get("predictions") or set(inputs) - set(ROLES):
        raise ValueError("Predictions are mandatory; unknown input role")
    output = Path(output)
    if output.name in ("", ".", ".."):
        raise ValueError("Output must name a new directory")
    output = output.parent.resolve(strict=True) / output.name
    started = now_utc()
    output.mkdir(mode=0o700)  # An interrupted directory is never reused.
    (output / "payloads").mkdir(mode=0o700)
    roles, saved, total = {}, set(), 0
    for role in ROLES:
        if not inputs.get(role):
            continue
        path = Path(inputs[role])
        raw = read_once(path, MAX_FILE_BYTES)
        observed = now_utc()
        total += len(raw)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Combined inputs exceed byte limit")
        digest = hashlib.sha256(raw).hexdigest()
        payload = f"payloads/{digest}.bin"
        if digest not in saved:
            write_new(output / payload, raw)
            saved.add(digest)
        roles[role] = {"basename": path.name, "bytes": len(raw), "sha256": digest,
                       "payload": payload, "first_observed_here_at_utc": observed}
    manifest = {"schema": 1, "tool": TOOL, "scope": SCOPE,
                "capture_started_at_utc": started, "capture_finished_at_utc": now_utc(),
                "read_semantics": READ_SEMANTICS,
                "provenance_status": dict(UNVERIFIED), "roles": roles}
    pending = output / ".manifest.pending"
    write_new(pending, (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    # Atomically publish the complete manifest without overwriting a concurrent file.
    os.link(pending, output / "manifest.json")
    pending.unlink()
    checked = verify(output)
    return {**checked, "status": "CAPTURED_UNVERIFIED", "directory": str(output)}


def verify(directory):
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Capture must be an existing regular directory")
    manifest_path = directory / "manifest.json"
    if not manifest_path.exists():
        raise ValueError("Incomplete capture: no finalized manifest")
    raw = read_once(manifest_path, MAX_MANIFEST_BYTES)
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or type(manifest.get("schema")) is not int or manifest["schema"] != 1:
        raise ValueError("Unsupported capture schema")
    if set(manifest) != {"schema", "tool", "scope", "capture_started_at_utc", "capture_finished_at_utc",
                         "read_semantics", "provenance_status", "roles"}:
        raise ValueError("Unsupported manifest fields")
    if manifest["tool"] != TOOL or manifest["read_semantics"] != READ_SEMANTICS:
        raise ValueError("Unsupported tool or read semantics")
    if manifest.get("scope") != SCOPE or manifest.get("provenance_status") != UNVERIFIED:
        raise ValueError("Capture provenance must remain explicitly unverified")
    roles = manifest.get("roles")
    if not isinstance(roles, dict) or "predictions" not in roles or set(roles) - set(ROLES):
        raise ValueError("Invalid capture role mapping")
    start = utc_time(manifest["capture_started_at_utc"])
    end = utc_time(manifest["capture_finished_at_utc"])
    if end < start:
        raise ValueError("Capture time interval is reversed")
    payloads = directory / "payloads"
    if payloads.is_symlink() or not payloads.is_dir():
        raise ValueError("Payload directory must be a regular directory")
    total = 0
    for role, record in roles.items():
        if not isinstance(record, dict) or set(record) != {"basename", "bytes", "sha256", "payload", "first_observed_here_at_utc"}:
            raise ValueError("Invalid or unsupported role fields")
        digest, size = record.get("sha256"), record.get("bytes")
        name = record.get("basename")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ValueError("Invalid payload digest")
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise ValueError("Invalid payload byte count")
        if not isinstance(name, str) or name in ("", ".", "..") or "/" in name:
            raise ValueError("Invalid source basename")
        relative = f"payloads/{digest}.bin"
        if record.get("payload") != relative:
            raise ValueError("Payload path must match its content digest")
        observed = utc_time(record["first_observed_here_at_utc"])
        if not start <= observed <= end:
            raise ValueError("First-observed time is outside the local capture interval")
        data = read_once(directory / relative, MAX_FILE_BYTES)
        if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError(f"Payload bytes/hash mismatch: {role}")
        total += len(data)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Combined inputs exceed byte limit")
    return {"status": "VERIFIED_BYTES", "scope": SCOPE, "manifest_sha256": hashlib.sha256(raw).hexdigest(),
            "roles": roles, "provenance_status": dict(UNVERIFIED)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("capture", help="Reserve a new directory and capture supplied raw bytes")
    record.add_argument("--predictions", required=True, type=Path)
    for role in ROLES[1:]:
        record.add_argument(f"--{role}", type=Path)
    record.add_argument("--output", required=True, type=Path,
                        help="New directory under an existing parent; never overwritten")
    check = sub.add_parser("verify", help="Check a finalized capture against its manifest; no authentication")
    check.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        result = (capture({role: getattr(args, role) for role in ROLES}, args.output)
                  if args.command == "capture" else verify(args.directory))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
