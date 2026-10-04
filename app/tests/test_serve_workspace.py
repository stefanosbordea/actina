"""Probe occupied-port reuse using owned, ephemeral loopback subprocesses."""
from pathlib import Path
import functools
import datetime
import hashlib
import http.server
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/serve_workspace.py"
PROBES = []


def serve_fixture(root, mode):
    spec = importlib.util.spec_from_file_location("workspace", root / "scripts/serve_workspace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class RedirectHandler(module.WorkspaceHandler):
        def do_GET(self):
            with (root / "redirect-hits.txt").open("a") as log:
                log.write(self.path + "\n")
            self.send_response(302)
            self.send_header("Location", "/redirect-target")
            self.end_headers()
    handler = RedirectHandler if mode == "redirect" else module.WorkspaceHandler if mode == "workspace" else http.server.SimpleHTTPRequestHandler
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(root / "web/public")))
    print(server.server_address[1], flush=True)
    server.serve_forever()


class OccupiedPortTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="aquashift-port-")
        self.fixture = Path(self.temp.name) / "workspace copy with spaces"
        shutil.copytree(ROOT / "web/public", self.fixture / "web/public")
        (self.fixture / "scripts").mkdir()
        shutil.copy2(SCRIPT, self.fixture / "scripts/serve_workspace.py")
        shutil.copy2(ROOT / "web/vercel.json", self.fixture / "web/vercel.json")
        self.children = []

    def tearDown(self):
        for child in self.children:
            child.terminate()
            child.wait(timeout=5)
            child.stdout.close()
        self.temp.cleanup()

    def server(self, mode="workspace"):
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--serve", str(self.fixture), mode],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.children.append(child)
        port = int(child.stdout.readline())
        return child, port

    def probe(self, name, port, expected_exit):
        args = [sys.executable, str(SCRIPT), "--port", str(port), "--no-browser"]
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected_exit, result.stderr)
        PROBES.append({"name": name, "arguments": args, "exit_status": result.returncode,
                       "stdout": result.stdout.strip(), "stderr": result.stderr.strip()})
        return result

    def test_matching_workspace(self):
        child, port = self.server()
        result = self.probe("matching workspace reused", port, 0)
        self.assertIn("already available", result.stdout)
        self.assertIsNone(child.poll())
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2) as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
            self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        with self.assertRaises(urllib.error.HTTPError) as listing:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/vendor/", timeout=2)
        self.assertEqual(listing.exception.code, 404)

    def test_conditional_script_requests_return_complete_modules(self):
        child, port = self.server()
        for name in ["workspace.js", "core.mjs"]:
            with self.subTest(asset=name):
                url = f"http://127.0.0.1:{port}/{name}"
                expected = (self.fixture / "web/public" / name).read_bytes()
                with urllib.request.urlopen(url, timeout=2) as response:
                    modified = response.headers["Last-Modified"]
                    self.assertIsNotNone(modified)
                    self.assertEqual(response.read(), expected)
                for _ in range(2):
                    request = urllib.request.Request(url, headers={"If-Modified-Since": modified})
                    with urllib.request.urlopen(request, timeout=2) as response:
                        self.assertEqual(response.status, 200)
                        self.assertEqual(response.read(), expected)
                        self.assertIn(response.headers.get_content_type(), ["text/javascript", "application/javascript"])
                        self.assertEqual(response.headers["Cache-Control"], "no-store")
                        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        self.assertIsNone(child.poll())

    def test_stale_javascript_with_same_manifest(self):
        path = self.fixture / "web/public/workspace.js"
        path.write_bytes(path.read_bytes() + b"\n// stale copy\n")
        self.assertEqual((self.fixture / "web/public/manifest.json").read_bytes(), (ROOT / "web/public/manifest.json").read_bytes())
        child, port = self.server()
        self.probe("stale JavaScript; unchanged manifest", port, 1)
        self.assertIsNone(child.poll())

    def test_stale_css_with_same_manifest(self):
        path = self.fixture / "web/public/workspace.css"
        path.write_bytes(path.read_bytes() + b"\n/* stale copy */\n")
        child, port = self.server()
        self.probe("stale CSS; unchanged manifest", port, 1)
        self.assertIsNone(child.poll())

    def test_stale_pilot_with_same_manifest(self):
        path = self.fixture / "web/public/pilot-ui.mjs"
        path.write_bytes(path.read_bytes() + b"\n// stale pilot\n")
        child, port = self.server()
        self.probe("stale Pilot; unchanged manifest", port, 1)
        self.assertIsNone(child.poll())

    def test_foreign_server_same_bytes_missing_headers(self):
        child, port = self.server("foreign")
        self.probe("foreign server; missing workspace headers", port, 1)
        self.assertIsNone(child.poll())

    def test_missing_asset(self):
        (self.fixture / "web/public/pilot.mjs").unlink()
        child, port = self.server()
        self.probe("occupied service missing Pilot asset", port, 1)
        self.assertIsNone(child.poll())

    def test_missing_local_builder_refuses_reuse(self):
        (self.fixture / "web/public/pilot-builder.mjs").unlink()
        child, port = self.server()
        args = [sys.executable, str(self.fixture / "scripts/serve_workspace.py"), "--port", str(port), "--no-browser"]
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Workspace assets could not be verified", result.stderr)
        self.assertNotIn("already available", result.stdout)
        self.assertIsNone(child.poll())
        PROBES.append({"name": "missing local builder refuses occupied service reuse", "arguments": args,
                       "exit_status": result.returncode, "stderr": result.stderr.strip()})

    def test_missing_local_builder_refuses_start(self):
        (self.fixture / "web/public/pilot-builder.mjs").unlink()
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        args = [sys.executable, str(self.fixture / "scripts/serve_workspace.py"), "--port", str(port), "--no-browser"]
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Workspace assets could not be verified", result.stderr)
        self.assertNotIn("operations workspace:", result.stdout)
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", port))
        PROBES.append({"name": "missing local builder refuses new service start", "arguments": args,
                       "exit_status": result.returncode, "stderr": result.stderr.strip(),
                       "port_rebind_after_refusal": "PASS"})

    def test_missing_frontier_refuses_start(self):
        (self.fixture / "web/public/storage-frontier.mjs").unlink()
        result = subprocess.run([sys.executable, str(self.fixture / "scripts/serve_workspace.py"),
                                 "--port", "8510", "--no-browser"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Required public workspace assets are missing", result.stderr)
        self.assertNotIn("operations workspace:", result.stdout)

    def test_missing_sequence_module_refuses_start(self):
        (self.fixture / "web/public/plan-sequence.mjs").unlink()
        result = subprocess.run([sys.executable, str(self.fixture / "scripts/serve_workspace.py"),
                                 "--port", "8510", "--no-browser"], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Required public workspace assets are missing", result.stderr)
        self.assertNotIn("operations workspace:", result.stdout)

    def test_redirect_not_followed(self):
        child, port = self.server("redirect")
        self.probe("redirect refused without following", port, 1)
        self.assertEqual(len((self.fixture / "redirect-hits.txt").read_text().splitlines()), 1)
        self.assertIsNone(child.poll())

    def test_local_symlink_rejected(self):
        outside = self.fixture / "outside.txt"
        outside.write_text("This is outside the public folder.")
        (self.fixture / "web/public/outside-link.txt").symlink_to(outside)
        args = [sys.executable, str(self.fixture / "scripts/serve_workspace.py"), "--port", "8510", "--no-browser"]
        result = subprocess.run(args, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unsafe public asset", result.stderr)
        PROBES.append({"name": "local symlink rejected before binding", "arguments": args,
                       "exit_status": result.returncode, "stderr": result.stderr.strip()})


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--serve":
        serve_fixture(Path(sys.argv[2]), sys.argv[3])
    else:
        result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(OccupiedPortTests))
        hashes = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted((ROOT / "web/public").rglob("*")) if p.is_file() and not p.is_symlink()}
        receipt = {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
                   "completed_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "reproduction": "python3 tests/test_serve_workspace.py", "python": sys.version,
                   "server_script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
                   "test_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   "headers_config_sha256": hashlib.sha256((ROOT / "web/vercel.json").read_bytes()).hexdigest(),
                   "public_asset_sha256": hashes, "probes": PROBES,
                   "scope": "Ephemeral loopback subprocesses only; no browser opened. Existing services untouched; only owned test subprocesses cleaned up."}
        (ROOT / "results").mkdir(exist_ok=True)
        (ROOT / "results/launcher-asset-identity-check.json").write_text(json.dumps(receipt, indent=2) + "\n")
        raise SystemExit(0 if result.wasSuccessful() else 1)
