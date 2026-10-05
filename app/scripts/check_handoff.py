"""Check a starting-point ZIP against its own manifest; hashes are not signatures."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import zipfile


def check(archive_path):
    return check_bytes(Path(archive_path).read_bytes())


def check_bytes(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive names")
        for name in names:
            parts = PurePosixPath(name).parts
            if (not parts or parts[0] != "AquaShift" or ".." in parts or "\\" in name
                    or name != PurePosixPath(name).as_posix()):
                raise ValueError(f"Unsupported archive path: {name}")
            mode = archive.getinfo(name).external_attr >> 16
            if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                raise ValueError(f"Nonregular file in archive: {name}")
        if archive.testzip() is not None:
            raise ValueError("Archive CRC check failed")
        manifest_name = "AquaShift/HANDOFF-MANIFEST.json"
        manifest = json.loads(archive.read(manifest_name))
        expected = ["AquaShift/" + item["path"] for item in manifest]
        if len(expected) != len(set(expected)) or set(names) != set(expected + [manifest_name]):
            raise ValueError("Manifest does not cover the exact archive contents")
        for item in manifest:
            name = "AquaShift/" + item["path"]
            data = archive.read(name)
            mode = (archive.getinfo(name).external_attr >> 16) & 0o777
            if len(data) != item["bytes"] or hashlib.sha256(data).hexdigest() != item["sha256"]:
                raise ValueError(f"File identity mismatch: {name}")
            if oct(mode) != item["mode"]:
                raise ValueError(f"Mode mismatch: {name}")
        launcher_mode = archive.getinfo("AquaShift/Start AquaShift.command").external_attr >> 16
        if not launcher_mode & 0o111:
            raise ValueError("Launcher is not executable in the archive")
        return len(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    raw = args.archive.read_bytes()
    count = check_bytes(raw)
    print(json.dumps({"status": "PASS", "files": count,
                      "archive_sha256": hashlib.sha256(raw).hexdigest(),
                      "scope": "Internal consistency, safe relative paths and retained modes; not source authentication or a runtime test."}))


if __name__ == "__main__":
    main()
