"""Generate tiny synthetic ZIPs; test checked bytes, paths, types and modes."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_handoff.py"
spec = importlib.util.spec_from_file_location("handoff_checker", SCRIPT)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class HandoffCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def archive(self, name="fixture", *, file_type=stat.S_IFREG, extra=None,
                duplicate=False, wrong_hash=False, wrong_bytes=False,
                wrong_mode=False, launcher_mode=0o755, duplicate_manifest=False):
        target = self.root / (name + ".zip")
        records = []
        with warnings.catch_warnings(), zipfile.ZipFile(target, "w") as zipped:
            warnings.simplefilter("ignore", UserWarning)
            for relative, data, mode in [
                    ("README.md", b"x", file_type | 0o644),
                    ("Start AquaShift.command", b"#!/bin/sh\n", stat.S_IFREG | launcher_mode)]:
                info = zipfile.ZipInfo("AquaShift/" + relative)
                info.external_attr = mode << 16
                zipped.writestr(info, data)
                records.append({"path": relative, "bytes": len(data) + int(wrong_bytes),
                                "sha256": "0" * 64 if wrong_hash else hashlib.sha256(data).hexdigest(),
                                "mode": "0o600" if wrong_mode else oct(mode & 0o777)})
            if extra:
                info = zipfile.ZipInfo(extra)
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                zipped.writestr(info, b"uncovered")
            if duplicate:
                zipped.writestr("AquaShift/README.md", b"x")
            if duplicate_manifest:
                records.append(records[0])
            zipped.writestr("AquaShift/HANDOFF-MANIFEST.json", json.dumps(records))
        return target

    def test_regular_and_unspecified_member_types_pass(self):
        for file_type in (stat.S_IFREG, 0):
            with self.subTest(file_type=file_type):
                archive = self.archive(str(file_type), file_type=file_type)
                self.assertEqual(checker.check(archive), 2)
                self.assertEqual(checker.check_bytes(archive.read_bytes()), 2)

    def test_special_member_types_rejected(self):
        for file_type in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFBLK, stat.S_IFDIR, stat.S_IFSOCK):
            with self.subTest(file_type=file_type):
                with self.assertRaises(ValueError):
                    checker.check(self.archive(str(file_type), file_type=file_type))

    def test_unsafe_relative_and_absolute_paths_rejected(self):
        for number, name in enumerate(("AquaShift/../escape", "/AquaShift/file", "Other/file",
                                       "AquaShift\\file", "AquaShift/./file", "AquaShift//file")):
            with self.subTest(path=name), self.assertRaises(ValueError):
                checker.check(self.archive(str(number), extra=name))

    def test_duplicate_archive_names_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            checker.check(self.archive(duplicate=True))

    def test_manifest_covers_exact_contents_and_unique_records(self):
        for option in ({"extra": "AquaShift/uncovered"}, {"duplicate_manifest": True}):
            with self.subTest(option=option), self.assertRaisesRegex(ValueError, "exact archive"):
                checker.check(self.archive(**option))

    def test_wrong_hash_bytes_and_mode_rejected(self):
        for option in ({"wrong_hash": True}, {"wrong_bytes": True}, {"wrong_mode": True}):
            with self.subTest(option=option), self.assertRaises(ValueError):
                checker.check(self.archive(**option))

    def test_nonexecutable_launcher_rejected(self):
        with self.assertRaisesRegex(ValueError, "not executable"):
            checker.check(self.archive(launcher_mode=0o644))

    def test_missing_manifest_and_invalid_zip_rejected(self):
        archive = self.root / "missing.zip"
        with zipfile.ZipFile(archive, "w") as zipped:
            zipped.writestr("AquaShift/README.md", b"synthetic")
        with self.assertRaises(KeyError):
            checker.check(archive)
        archive.write_bytes(b"NOT A ZIP")
        with self.assertRaises(zipfile.BadZipFile):
            checker.check(archive)

    def test_main_hashes_the_snapshot_even_when_path_is_replaced(self):
        archive = self.archive()
        original = archive.read_bytes()
        check_bytes = checker.check_bytes
        captured = []
        def replace_path_after_capture(raw):
            captured.append(raw)
            archive.write_bytes(b"Replacement after raw archive capture; not a ZIP")
            return check_bytes(raw)
        output = io.StringIO()
        with patch.object(checker, "check_bytes", side_effect=replace_path_after_capture), \
                patch.object(sys, "argv", [str(SCRIPT), str(archive)]), contextlib.redirect_stdout(output):
            checker.main()
        result = json.loads(output.getvalue())
        self.assertEqual(captured, [original])
        self.assertFalse(zipfile.is_zipfile(archive))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["archive_sha256"], hashlib.sha256(original).hexdigest())
        self.assertNotEqual(result["archive_sha256"], hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
