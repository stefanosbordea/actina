"""Package the reviewable AquaShift starting point without private source messages."""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT.parent / "AquaShift-Stefanos-Starting-Point-2026-10-02.zip"
TOP_FILES = {"README.md", "requirements.txt", "requirements-lock.txt", "requirements-review.txt",
             "Start AquaShift.command", ".gitattributes", ".gitignore"}
DIRECTORIES = {"app", "data", "delivery", "eval", "model", "results", "scripts", "tests", "web", ".streamlit", ".github"}
EXCLUDED_PARTS = {".git", ".venv", "node_modules", ".npm-cache", ".vercel", "__pycache__", "build", "tmp", ".DS_Store"}
EXCLUDED_PREFIXES = ("delivery/demo-frames/", "delivery/native-24-candidate/", "web/archived-initial/")
EXCLUDED_FILES = {
    "delivery/AquaShift-90s-Backup.mp4", "delivery/AquaShift-Backup-Captions.srt",
    "delivery/build_documents.py", "scripts/build_backup.py", "results/handoff-package.json",
    "results/delivery-check.json", "results/deck_check-before-notes.json",
    "results/handoff-pdf-review.json", "results/package-smoke-check.json",
    "results/backup-video.json", "results/backup-video.log", "results/backup-video-attempt-1.log",
    "delivery/WhatsApp-draft-for-approval.txt", "results/package-smoke-final.json",
}

def included(path):
    name = path.relative_to(ROOT).as_posix()
    parts = path.relative_to(ROOT).parts
    if path.is_symlink() or not path.is_file():
        return False
    if name not in TOP_FILES and parts[0] not in DIRECTORIES:
        return False
    if any(p in EXCLUDED_PARTS or p.startswith(".env") for p in parts):
        return False
    if name.startswith(EXCLUDED_PREFIXES) or name in EXCLUDED_FILES or path.suffix == ".pyc":
        return False
    if parts[0] == "web" and path.suffix == ".log":
        return False
    return True

def selected_files():
    files = []
    for directory, names, filenames in os.walk(ROOT, followlinks=False):
        base = Path(directory)
        names[:] = [n for n in names if n not in EXCLUDED_PARTS and not n.startswith(".env")
                    and not (base / n).is_symlink()
                    and (base != ROOT or n in DIRECTORIES)]
        files.extend((base / n).relative_to(ROOT).as_posix() for n in filenames if included(base / n))
    return sorted(files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    output = parser.parse_args().output.resolve()
    if not output.parent.is_dir():
        parser.error("Output parent directory must already exist")
    if output.exists():
        parser.error("Output already exists; choose a new release filename")
    files = selected_files()
    assert "README.md" in files and "data/paphos_weather.csv" in files
    entries = []
    with tempfile.NamedTemporaryFile(prefix=output.stem + "-", suffix=".zip.part", dir=output.parent, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in files:
                path = ROOT / name
                data = path.read_bytes()
                info = zipfile.ZipInfo.from_file(path, "AquaShift/" + name)
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data)
                entries.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                                "mode": oct((info.external_attr >> 16) & 0o777)})
            archive.writestr("AquaShift/HANDOFF-MANIFEST.json", json.dumps(entries, indent=2) + "\n")
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None
            for entry in entries:
                assert hashlib.sha256(archive.read("AquaShift/" + entry["path"])).hexdigest() == entry["sha256"]
            assert (archive.getinfo("AquaShift/Start AquaShift.command").external_attr >> 16) & 0o111
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    record = {
        "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "output": str(output), "files": len(entries), "bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "verified": True,
        "excluded": ["Private source attachments, email/WhatsApp content, unsent draft and receipt metadata",
                     "Git history, internal state, local environment, build/package caches and Vercel credentials",
                     "Superseded backup film, old UI captures/builders and obsolete artifact receipts"],
        "contents_manifest": "AquaShift/HANDOFF-MANIFEST.json",
    }
    (ROOT / "results/handoff-package.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
