"""Build the verified competition pack; exclude historical exports and preserve prior packs."""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
import zipfile

APP = Path(__file__).resolve().parents[1]
VIDEO = "Aktina-Backup-Final.mp4"
DECK = "Aktina-Pafos-2026.pptx"
SITE_TYPES = {".html", ".css", ".js", ".mjs", ".json", ".csv", ".svg", ".png", ".jpg", ".webp", ".ico", ".woff", ".woff2", ".txt"}
QR_FILES = ('Aktina-Forecast-QR.png', 'Aktina-Forecast-QR.svg', 'Aktina-Forecast-QR-Slide.svg', 'Aktina-Forecast-QR.txt')
FORECAST_URL = 'https://aktina-pafos-2026.vercel.app/forecast.html'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def static_paths(root):
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Missing or unsafe site directory: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlink in site: {path}")
        if any(part.lower() in {'private', 'messages', 'whatsapp', 'team-settings', 'screenshots'}
               for part in path.relative_to(root).parts):
            raise ValueError(f"Private handoff material is not a site asset: {path}")
        if any(part.startswith((".", "~$")) or part in {"drafts", "attempts", "__pycache__", "node_modules"}
               for part in path.relative_to(root).parts):
            continue
        if path.is_file() and path.suffix.lower() not in {".tmp", ".bak", ".lock", ".map", ".pyc"}:
            if path.suffix.lower() not in SITE_TYPES:
                raise ValueError(f"Unexpected site artifact; review before packaging: {path}")
            result[path.relative_to(root).as_posix()] = path
    return result


def run_order(duration):
    return f"""AKTINA — PRESENTATION RUN ORDER

1. PREPARE
Unzip the complete Aktina folder. Open presentation/{DECK}; the accompanying
Aktina-Speaker-Notes.md matches its source notes. Keep {VIDEO} ready.
Shotter handles the final presentation. This existing deck is a factual reference.
documents/Aktina-Technical-Summary.tex contains the current technical summary.
qr/ contains the forecast QR in PNG and SVG, a slide card and usage notes.

2. OPEN OFFLINE
From the unzipped Aktina folder, with Python 3 already installed, run:
python3 -m http.server 8527 --bind 127.0.0.1 --directory site
Open http://127.0.0.1:8527/ in your browser. Keep the server running during
the presentation; Ctrl+C stops it. The product data, scripts and fonts are
included. Internet access is needed only for external links.
Online fallback: https://aktina-pafos-2026.vercel.app/

3. REVIEW THE DEMO
The forecast page at /forecast.html shows Current forecast and its comparisons.
Precision is 94.08%, recall 88.24% and F1 91.06% across 3,566 validation hours.
Relative to the research comparison it has four fewer false alarms and one
additional missed hour. Validation was reused and the uncertainty interval
includes zero. This does not prove superiority on unseen data.
Forecast link for the QR: {FORECAST_URL}

For the existing schedule demonstration, show 3 July 2026, 10 December 2025 and
16 March 2026: sun, production, tank, then cost. Open AktinaBench for the
full-period comparisons. If the browser is unavailable, play the {duration:g}-second
silent backup for this earlier schedule sequence. It uses historical screenshots
predating the current forecast page. It does not show the new event correction.

4. KEEP THE TWO RESULTS SEPARATE
The product displays Stefanos's supplied 7,104-row schedule, covering 296 days.
Its plan input is persistence; the original LightGBM forecast is shown separately.
Water, electricity prices and plant limits are illustrative, not measured savings.
The current event correction uses a retained refit curve. Original forecast
options restore the supplied curve. Neither changes the supplied schedule.

5. CHECK BEFORE SUBMISSION
Confirm the intended schedule and team/contact declarations with Stefanos, and
complete the team rehearsals. The pack is ready for review; it has not been submitted.
documents/ contains the current technical summary and earlier standalone proposal
sources for team review. The older Technical-Proposal predates the current
forecast comparison. Use the Technical-Summary for the current model result.
No standalone PDF was generated or included. Private messages, team settings,
private screenshots, old videos and research datasets are excluded.
MANIFEST.json records packaged hashes. verification/ retains artifact checks.
""".encode("utf-8")


def collect(app):
    app = Path(app).resolve()
    delivery, files, inputs = app / "delivery", {}, {}

    def read(path):
        path = Path(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Missing or unsafe prerequisite: {path}")
        if path not in inputs:
            inputs[path] = path.read_bytes()
        return inputs[path]

    def include(path, name):
        if name in files:
            raise ValueError(f"Duplicate package entry: {name}")
        files[name] = read(path)

    current = static_paths(app / "site")
    current.update({"workspace/" + name: path for name, path in static_paths(app / "web/public").items()})
    built = static_paths(app / "dist")
    if current.keys() != built.keys():
        raise ValueError("Offline dist file set is stale; run the app build before packaging")
    for name, source in current.items():
        if read(source) != read(built[name]):
            raise ValueError(f"Offline dist is stale at {name}; run the app build before packaging")
        include(built[name], "site/" + name)
    required = {"site/index.html", "site/site.css", "site/site.mjs", "site/data.js", "site/schedule_hourly.csv",
                "site/benchmark.html", "site/benchmark.mjs", "site/benchmark-data.js", "site/workspace/index.html",
                "site/forecast.html", "site/forecast.mjs", "site/forecast.css", "site/forecast-data.js"}
    if not required <= files.keys():
        raise ValueError("Complete offline product and benchmark are required")
    if files["site/schedule_hourly.csv"] != read(app.parent / "eval/schedule_hourly.csv"):
        raise ValueError("Offline schedule differs from the supplied schedule")

    verification_path = delivery / "Aktina-Deck-Source/verification.json"
    verification = json.loads(read(verification_path))
    deck = read(delivery / DECK)
    if sha(deck) != verification["sha256"] or len(deck) != verification["bytes"]:
        raise ValueError("Current PowerPoint does not match its final verification receipt")
    with zipfile.ZipFile(io.BytesIO(deck)) as archive:
        slide_count = sum(bool(re.fullmatch(r"ppt/slides/slide\d+\.xml", name)) for name in archive.namelist())
        if archive.testzip() is not None or slide_count != 12 or verification["slides"] != 12:
            raise ValueError("PowerPoint package or slide count failed verification")
    if verification["checks"]["build_exit_code"] != 0 or verification["checks"]["package_integrity"] != "pass":
        raise ValueError("PowerPoint build/package verification has not passed")
    pins_path = delivery / "Aktina-Deck-Source/inputs.sha256.json"
    pins = json.loads(read(pins_path))
    notes_path = delivery / "Aktina-Deck-Source/Speaker-Notes.md"
    if "delivery/Aktina-Deck-Source/Speaker-Notes.md" not in pins:
        raise ValueError("Verified deck must identify its source notes")
    for relative, expected in pins.items():
        source = app / relative
        if not source.resolve().is_relative_to(app) or sha(read(source)) != expected:
            raise ValueError(f"Deck source changed since verification: {relative}")
    include(delivery / DECK, "presentation/" + DECK)
    include(notes_path, "presentation/Aktina-Speaker-Notes.md")
    include(verification_path, "verification/PowerPoint.json")
    include(pins_path, "verification/PowerPoint-inputs.json")
    for name in ("Business-Model-Canvas", "Executive-Summary", "Technical-Proposal"):
        source = delivery / f"AquaShift-{name}.tex"
        if re.search(r"(?:Aktina-Backup(?:-v\d+)?|AquaShift-[\w-]+|ActinaBench-[\w-]+)\.(?:mp4|mov)",
                     read(source).decode()):
            raise ValueError(f"Document still references a superseded video: {source}")
        include(source, f"documents/Aktina-{name}.tex")

    include(delivery / 'Aktina-Technical-Summary.tex', 'documents/Aktina-Technical-Summary.tex')
    qr_notes = read(delivery / 'Aktina-Forecast-QR.txt').decode()
    if FORECAST_URL not in qr_notes:
        raise ValueError('QR handoff points to a different forecast URL')
    for name in QR_FILES:
        if name.endswith(('.png', '.svg')) and f'{sha(read(delivery / name))}  {name}' not in qr_notes:
            raise ValueError(f'QR asset differs from its verification notes: {name}')
        include(delivery / name, 'qr/' + name)

    video_path = delivery / VIDEO
    video_receipt = delivery / "Aktina-Backup-Final-Source/render/verification.json"
    missing = [str(path) for path in (video_path, video_receipt) if not path.is_file()]
    if missing:
        raise ValueError("Final silent-video prerequisites missing: " + "; ".join(missing))
    video, video_check = read(video_path), json.loads(read(video_receipt))
    if sha(video) != video_check["output"]["sha256"]:
        raise ValueError("Final video bytes differ from their verification receipt")
    duration = video_check["duration_seconds"]
    if (video_check["status"] != "EXPORTED_AND_DECODED" or video_check["audio_tracks"] != 0
            or video_check["verification"]["no_audio"] is not True
            or video_check["verification"]["full_decode"] != "passed"
            or type(duration) not in (int, float) or not 0 < duration <= 60
            or video_check["width"] != 1920 or video_check["height"] != 1080 or video_check["fps"] != 30):
        raise ValueError("Final video must have verified full decode, no audio, 1080p/30fps, and duration at most 60s")
    notes = read(notes_path).decode()
    if VIDEO not in notes or re.search(r"Aktina-Backup(?:-v2)?\.mp4|60[- ]second", notes):
        raise ValueError("Verified speaker notes still point to an old backup; update/rebuild the deck first")
    if f"{duration:g}-second backup" not in notes:
        raise ValueError("Verified speaker notes and final video duration disagree")
    include(video_path, VIDEO)
    include(video_receipt, "verification/Silent-video.json")
    files["READ-ME.txt"] = run_order(duration)
    facts = {"slides": slide_count, "site_files": len(built), "video_seconds": duration,
             "audio_tracks": 0, "stale_pdf_exports_included": False,
             "current_forecast_included": True, "technical_summary_source_included": True,
             "qr_assets": list(QR_FILES), "private_handoff_material_included": False,
             "source_notes_sha256": sha(read(notes_path)), "deck_sha256": sha(deck), "video_sha256": sha(video)}
    return files, inputs, facts


def build(app, output, check_only=False):
    files, inputs, facts = collect(app)
    if check_only:
        return {"status": "READY", **facts, "packaged_entries": len(files) + 1}
    output = Path(output)
    receipt_path = output.with_suffix(".manifest.json")
    if output.suffix != ".zip" or not output.parent.is_dir() or output.exists() or receipt_path.exists():
        raise ValueError("Choose a new .zip filename in an existing directory; prior packs are never overwritten")
    manifest = {"schema": 2, "created_at_utc": datetime.now(timezone.utc).isoformat(), "verified": facts,
                "files": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in sorted(files.items())}}
    files["MANIFEST.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".aktina-pack-", suffix=".zip", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(files.items()):
                info = zipfile.ZipInfo("Aktina/" + name, date_time=(2026, 10, 4, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED if name.endswith((".mp4", ".pptx")) else zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, raw)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None or len(archive.namelist()) != len(files):
                raise ValueError("Archive integrity or entry count failed")
            for name, raw in files.items():
                if archive.read("Aktina/" + name) != raw:
                    raise ValueError(f"Archive content mismatch: {name}")
        for source, raw in inputs.items():
            if source.is_symlink() or source.read_bytes() != raw:
                raise ValueError(f"Input changed while packaging: {source}")
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    receipt = {"status": "PACKAGED_AND_VERIFIED", "file": output.name, "bytes": output.stat().st_size,
               "sha256": sha(output.read_bytes()), "entries": len(files), **facts, "contents": manifest["files"]}
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    return {key: value for key, value in receipt.items() if key != "contents"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate prerequisites without creating a pack")
    parser.add_argument("--output", type=Path, default=APP / "delivery/Aktina-Competition-Pack.zip")
    args = parser.parse_args()
    try:
        print(json.dumps(build(APP, args.output, args.check), indent=2))
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "BLOCKED", "error": str(error)}, indent=2))
        raise SystemExit(1)
