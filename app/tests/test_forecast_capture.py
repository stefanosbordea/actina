"""Stdlib tests for local supplied-file snapshots, never source/timing attestation."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_forecast_handoff.py"
spec = importlib.util.spec_from_file_location("capture_handoff", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root / "synthetic-predictions.csv"
        self.raw = b"\xef\xbb\xbftime,predicted\r\n2026-10-03T00:00:00+03:00,123.5\r\n"
        self.input.write_bytes(self.raw)
        self.out = self.root / "capture"

    def capture(self, **inputs):
        return tool.capture({"predictions": self.input, **inputs}, self.out)

    def manifest(self):
        return json.loads((self.out / "manifest.json").read_bytes())

    def alter_manifest(self, alter):
        value = self.manifest()
        alter(value)
        (self.out / "manifest.json").write_text(json.dumps(value))

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True)

    def test_raw_bom_crlf_preserved_and_verified(self):
        result = self.capture()
        row = result["roles"]["predictions"]
        self.assertEqual((self.out / row["payload"]).read_bytes(), self.raw)
        self.assertEqual(row["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(row["bytes"], len(self.raw))
        self.assertEqual(tool.verify(self.out)["status"], "VERIFIED_BYTES")
        self.assertEqual(result["manifest_sha256"], hashlib.sha256((self.out / "manifest.json").read_bytes()).hexdigest())
        self.assertFalse((self.out / ".manifest.pending").exists())

    def test_all_optional_roles_unverified_and_opaque(self):
        paths = {}
        for role in tool.ROLES[1:]:
            paths[role] = self.root / (role + ".dat")
            paths[role].write_bytes(b'{"original_issue_time":"1999-01-01","synthetic":true}\r\n')
        result = self.capture(**paths)
        self.assertEqual(set(result["roles"]), set(tool.ROLES))
        self.assertEqual(result["provenance_status"], tool.UNVERIFIED)
        self.assertIn("No source authentication or timestamp attestation", result["scope"])

    def test_equal_content_deduplicates_payloads(self):
        other = self.root / "weather.csv"
        other.write_bytes(self.raw)
        result = self.capture(weather=other)
        self.assertEqual(result["roles"]["weather"]["payload"], result["roles"]["predictions"]["payload"])
        self.assertEqual(len(list((self.out / "payloads").iterdir())), 1)

    def test_same_basename_distinct_content_keeps_roles(self):
        folder = self.root / "another"
        folder.mkdir()
        other = folder / self.input.name
        other.write_bytes(b"synthetic weather\r\n")
        result = self.capture(weather=other)
        self.assertEqual(result["roles"]["weather"]["basename"], self.input.name)
        self.assertNotEqual(result["roles"]["weather"]["payload"], result["roles"]["predictions"]["payload"])

    def test_original_is_read_once_and_mutation_does_not_change_snapshot(self):
        read = tool.read_once
        reads = []
        def mutate(path, limit):
            value = read(path, limit)
            if Path(path) == self.input:
                reads.append(path)
                self.input.write_bytes(b"changed after read")
            return value
        with patch.object(tool, "read_once", side_effect=mutate):
            result = self.capture()
        self.assertEqual(len(reads), 1)
        self.assertEqual((self.out / result["roles"]["predictions"]["payload"]).read_bytes(), self.raw)
        self.assertNotEqual(self.input.read_bytes(), self.raw)
        self.assertEqual(tool.verify(self.out)["roles"]["predictions"]["sha256"], hashlib.sha256(self.raw).hexdigest())

    def test_existing_output_preserved_without_reading_inputs(self):
        self.out.mkdir()
        sentinel = self.out / "keep"
        sentinel.write_bytes(b"existing")
        with patch.object(tool, "read_once") as read:
            with self.assertRaises(FileExistsError):
                self.capture()
            read.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"existing")

    def test_distinct_captures_never_overwrite(self):
        self.capture()
        old = (self.out / "manifest.json").read_bytes()
        second = tool.capture({"predictions": self.input}, self.root / "second")
        self.assertEqual(second["status"], "CAPTURED_UNVERIFIED")
        self.assertEqual((self.out / "manifest.json").read_bytes(), old)

    def test_missing_prediction_and_unknown_role(self):
        for inputs in ({}, {"weather": self.input}, {"predictions": self.input, "other": self.input}):
            with self.subTest(inputs=list(inputs)), self.assertRaises(ValueError):
                tool.capture(inputs, self.out)
        self.assertFalse(self.out.exists())

    def test_size_guards_leave_unfinalized_output(self):
        with patch.object(tool, "MAX_FILE_BYTES", 2), self.assertRaises(ValueError):
            self.capture()
        self.assertFalse((self.out / "manifest.json").exists())
        with self.assertRaises(ValueError):
            tool.verify(self.out)

    def test_total_guard_counts_roles_even_if_identical(self):
        with patch.object(tool, "MAX_TOTAL_BYTES", len(self.raw)), self.assertRaises(ValueError):
            self.capture(weather=self.input)
        self.assertFalse((self.out / "manifest.json").exists())

    def test_interruption_keeps_partial_and_never_reuses_it(self):
        write = tool.write_new
        def interrupt(path, data):
            if Path(path).name == ".manifest.pending":
                raise OSError("simulated interruption")
            write(path, data)
        with patch.object(tool, "write_new", side_effect=interrupt), self.assertRaises(OSError):
            self.capture()
        self.assertTrue(any((self.out / "payloads").iterdir()))
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            tool.verify(self.out)
        with self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual(self.input.read_bytes(), self.raw)

    def test_atomic_manifest_publication_never_overwrites(self):
        link = os.link
        def collision(source, target):
            Path(target).write_bytes(b"existing manifest")
            link(source, target)
        with patch.object(tool.os, "link", side_effect=collision), self.assertRaises(FileExistsError):
            self.capture()
        self.assertEqual((self.out / "manifest.json").read_bytes(), b"existing manifest")

    def test_tampered_or_missing_blob_rejected(self):
        result = self.capture()
        payload = self.out / result["roles"]["predictions"]["payload"]
        payload.write_bytes(b"x" * len(self.raw))
        with self.assertRaisesRegex(ValueError, "mismatch"):
            tool.verify(self.out)
        payload.unlink()
        with self.assertRaises(FileNotFoundError):
            tool.verify(self.out)

    def test_manifest_traversal_rejected(self):
        self.capture()
        self.alter_manifest(lambda m: m["roles"]["predictions"].update(payload="../../outside"))
        with self.assertRaisesRegex(ValueError, "Payload path"):
            tool.verify(self.out)

    def test_symlink_input_capture_and_payload_rejected(self):
        alias = self.root / "alias"
        alias.symlink_to(self.input)
        with self.assertRaises(ValueError):
            tool.capture({"predictions": alias}, self.root / "alias-capture")
        result = self.capture()
        capture_alias = self.root / "out-alias"
        capture_alias.symlink_to(self.out)
        with self.assertRaises(ValueError):
            tool.verify(capture_alias)
        payload = self.out / result["roles"]["predictions"]["payload"]
        payload.unlink()
        payload.symlink_to(self.input)
        with self.assertRaises(ValueError):
            tool.verify(self.out)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO unsupported")
    def test_nonregular_input_rejected_without_blocking(self):
        pipe = self.root / "pipe"
        os.mkfifo(pipe)
        with self.assertRaises(ValueError):
            tool.capture({"predictions": pipe}, self.out)

    def test_unverified_status_and_invalid_count_rejected(self):
        self.capture()
        self.alter_manifest(lambda m: m["provenance_status"].update(training="verified"))
        with self.assertRaises(ValueError):
            tool.verify(self.out)
        self.alter_manifest(lambda m: m.update(provenance_status=dict(tool.UNVERIFIED)))
        self.alter_manifest(lambda m: m["roles"]["predictions"].update(bytes=True))
        with self.assertRaises(ValueError):
            tool.verify(self.out)

    def test_local_current_utc_times_and_invalid_time_rejected(self):
        before = datetime.now(timezone.utc)
        self.capture()
        after = datetime.now(timezone.utc)
        manifest = self.manifest()
        self.assertLessEqual(before, tool.utc_time(manifest["capture_started_at_utc"]))
        self.assertLessEqual(tool.utc_time(manifest["capture_finished_at_utc"]), after)
        self.alter_manifest(lambda m: m["roles"]["predictions"].update(first_observed_here_at_utc="1999-01-01T00:00:00+00:00"))
        with self.assertRaises(ValueError):
            tool.verify(self.out)

    def test_output_parent_must_exist_and_dotdot_rejected(self):
        with self.assertRaises(FileNotFoundError):
            tool.capture({"predictions": self.input}, self.root / "missing" / "new")
        with self.assertRaises(ValueError):
            tool.capture({"predictions": self.input}, self.root / "..")
        self.assertFalse((self.root / "missing").exists())

    def test_boolean_schema_rejected(self):
        self.capture()
        self.alter_manifest(lambda m: m.update(schema=True))
        with self.assertRaisesRegex(ValueError, "schema"):
            tool.verify(self.out)

    def test_role_approval_claims_rejected(self):
        self.capture()
        original = (self.out / "manifest.json").read_bytes()
        for field in ("source_verified", "training_approved", "original_issue_time"):
            with self.subTest(field=field):
                (self.out / "manifest.json").write_bytes(original)
                self.alter_manifest(lambda m: m["roles"]["predictions"].update({field: True}))
                with self.assertRaisesRegex(ValueError, "role fields"):
                    tool.verify(self.out)

    def test_top_level_claims_and_identity_rejected(self):
        self.capture()
        original = (self.out / "manifest.json").read_bytes()
        for field, value in (("source_verified", True), ("tool", "Provider attestation"), ("read_semantics", [])):
            with self.subTest(field=field):
                (self.out / "manifest.json").write_bytes(original)
                self.alter_manifest(lambda m: m.update({field: value}))
                with self.assertRaises(ValueError):
                    tool.verify(self.out)

    def test_unknown_capture_role_rejected(self):
        self.capture()
        self.alter_manifest(lambda m: m["roles"].update(approved=m["roles"]["predictions"]))
        with self.assertRaisesRegex(ValueError, "role mapping"):
            tool.verify(self.out)

    def test_cli_capture_verify_tamper_and_backdate_rejection(self):
        result = self.cli("capture", "--predictions", self.input, "--output", self.out)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "CAPTURED_UNVERIFIED")
        self.assertEqual(self.cli("verify", self.out).returncode, 0)
        duplicate = self.cli("capture", "--predictions", self.input, "--output", self.out)
        self.assertEqual(duplicate.returncode, 1)
        payload = self.out / self.manifest()["roles"]["predictions"]["payload"]
        payload.write_bytes(b"tampered")
        self.assertEqual(self.cli("verify", self.out).returncode, 1)
        backdate = self.cli("capture", "--predictions", self.input, "--output", self.root / "new",
                            "--issue-time", "1999-01-01")
        self.assertEqual(backdate.returncode, 2)
        self.assertFalse((self.root / "new").exists())


if __name__ == "__main__":
    unittest.main()
