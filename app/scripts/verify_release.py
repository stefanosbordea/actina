"""Verify a checked-out release without model fitting or authoring runtimes."""
import argparse
import datetime
import functools
import hashlib
import http.server
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
HELPERS = ("test_forecast_capture.py", "test_issued_weather.py", "test_handoff_check.py", "test_serve_workspace.py", "test_deck_notes.py")
PILOT_FILES = (
    "web/check_pilot_cli.mjs", "web/review_pilot.mjs", "web/public/pilot.mjs",
    "web/public/vendor/papaparse.min.js", "web/vendor/provenance.json",
    "web/fixtures/pilot-synthetic-declaration.json", "web/fixtures/pilot-synthetic-observations.csv",
    "web/fixtures/pilot-late-review-declaration.json", "web/fixtures/pilot-wrong-unit.csv",
)


def identity():
    files = {ROOT / name for name in (*PILOT_FILES,
        ".github/workflows/verify.yml", "scripts/verify_release.py", "scripts/serve_workspace.py", "scripts/record_forecast_handoff.py",
        "scripts/capture_issued_weather.py", "scripts/check_handoff.py", "scripts/check_deck_notes.py", "web/check_public.py", "web/review_roadmap.mjs",
        "web/package.json", "web/package-lock.json", "web/vercel.json",
        "delivery/Aktina-Pafos-2026.pptx", "delivery/Aktina-Deck-Source/Speaker-Notes.md", "delivery/Aktina-Deck-Source/build.mjs",
        "delivery/AquaShift-Roadmap-Handoff-Example.json", "delivery/AquaShift-Paired-Service-Example.json")}
    files.update(ROOT / "tests" / name for name in HELPERS)
    files.update((ROOT / "web").glob("test_*.mjs"))
    files.update(path for path in (ROOT / "web/public").rglob("*") if path.is_file())
    files.update(path for path in (ROOT / "web/fixtures").rglob("*") if path.is_file())
    files.update(path for path in (ROOT / "tests/fixtures").rglob("*") if path.is_file())
    files.update(path for path in (ROOT / "results/roadmap-handoff/independent-fixture-files").glob("*") if path.is_file())
    files.update(ROOT / "results" / name / "independent-inputs-v1.json" for name in ("temporal-water", "raw-handoff-intake", "paired-water-service"))
    files.update(ROOT / "results/paired-water-service" / name for name in ("independent-integration-inputs-v1.json", "independent-witness-expectations-v1.json"))
    files.add(ROOT / "results/water-budget-certificate/independent-inputs-v1.json")
    files.update(ROOT / "results/forecast-value-study" / name for name in ("PROTOCOL.md", "build-independent.py", "independent-inputs-v1.json"))
    files.add(ROOT / "results/paired-water-service/independent-oracle.py")
    files.update(ROOT / "web" / name for name in ("operating-envelope.mjs", "review_operating_envelope.mjs"))
    files.update(ROOT / "results/operating-envelope" / name for name in
                 ("PROTOCOL.md", "protocol-fixtures.json", "independent-water-proof.py", "independent-water-proof.json", "run-study.mjs"))
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "build/release-check")
    parser.add_argument("--install", action="store_true", help="Run locked npm ci; use a clean checkout.")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    receipt = {
        "schema": 1, "status": "RUNNING", "started_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope": "Source tests, supplied-file contracts, presentation notes and local static delivery; no model fitting, live telemetry or field validation.",
        "python": sys.version, "platform": platform.platform(), "install_requested": args.install,
        "ci_commit": os.environ.get("GITHUB_SHA"), "ci_run_id": os.environ.get("GITHUB_RUN_ID"),
        "checks": [],
    }

    def save():
        pending = output / "receipt.pending.json"
        pending.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        pending.replace(output / "receipt.json")

    def run(name, command, cwd=ROOT):
        log = output / (name + ".log")
        record = {"name": name, "command": list(map(str, command)), "cwd": str(cwd), "log": log.name}
        start = time.monotonic()
        with log.open("w", encoding="utf-8") as stream:
            try:
                result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                        timeout=600, env={**os.environ, "PYTHONUTF8": "1", "PYTHONOPTIMIZE": ""})
                record.update(exit_code=result.returncode, status="PASS" if result.returncode == 0 else "FAIL")
            except (OSError, subprocess.TimeoutExpired) as error:
                stream.write(str(error) + "\n")
                record.update(exit_code=None, status="FAIL", error=type(error).__name__)
        record.update(seconds=round(time.monotonic() - start, 3), sha256=hashlib.sha256(log.read_bytes()).hexdigest())
        receipt["checks"].append(record)
        save()
        print(f"{name}: {record['status']}", flush=True)

    save()
    try:
        receipt["input_sha256"] = identity()
        save()
        run("node-version", ["node", "--version"])
        run("npm-version", ["npm", "--version"])
        if args.install:
            run("npm-ci", ["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], ROOT / "web")
        run("workspace-tests", ["npm", "test"], ROOT / "web")
        run("operating-envelope-study", ["node", "results/operating-envelope/run-study.mjs", "--output", output / "operating-envelope-study"])
        for test in HELPERS:
            run(test.removesuffix(".py"), [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", test, "-v"])
        with tempfile.TemporaryDirectory(prefix="aquashift-release-") as temporary:
            pilot = Path(temporary) / "pilot workspace with spaces"
            for name in PILOT_FILES:
                target = pilot / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / name, target)
            run("pilot-cli", ["node", "web/check_pilot_cli.mjs"], pilot)
            if (pilot / "results").exists():
                shutil.copytree(pilot / "results", output / "pilot-cli-results")
        run("native-notes", [sys.executable, "scripts/check_deck_notes.py", "--receipt", output / "native-notes.json"])
        spec = importlib.util.spec_from_file_location("release_workspace", ROOT / "scripts/serve_workspace.py")
        workspace = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(workspace)
        assets = workspace.public_assets()
        receipt["public_sha256"] = {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()}
        handler = functools.partial(workspace.WorkspaceHandler, directory=str(workspace.PUBLIC))
        with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                run("local-http", [sys.executable, "web/check_public.py", "--base",
                    f"http://127.0.0.1:{server.server_address[1]}", "--output", output / "local-http.json"])
            finally:
                server.shutdown()
                thread.join(timeout=5)
        receipt["input_sha256_after"] = identity()
        receipt["inputs_unchanged"] = receipt["input_sha256"] == receipt["input_sha256_after"]
        receipt["status"] = "PASS" if receipt["inputs_unchanged"] and all(check["status"] == "PASS" for check in receipt["checks"]) else "FAIL"
    except Exception as error:
        receipt.update(status="FAIL", error=f"{type(error).__name__}: {error}")
    finally:
        receipt["completed_at_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(f"{receipt['status']}: {output / 'receipt.json'}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
