"""Serve the included operations workspace on localhost without model dependencies."""
import argparse
import functools
import http.client
import http.server
import json
from pathlib import Path
import urllib.parse
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "web/public"
HEADERS = json.loads((ROOT / "web/vercel.json").read_text())["headers"][0]["headers"]


def public_assets():
    if PUBLIC.is_symlink() or PUBLIC.parent.is_symlink():
        raise ValueError("The public workspace must not use symlink directories")
    assets = {}
    for file in sorted(PUBLIC.rglob("*")):
        if file.is_symlink() or not file.resolve().is_relative_to(PUBLIC.resolve()):
            raise ValueError(f"Unsafe public asset: {file.relative_to(PUBLIC)}")
        if file.is_file():
            assets[file.relative_to(PUBLIC).as_posix()] = file.read_bytes()
    required = {"index.html", "workspace.js", "workspace.css", "core.mjs", "temporal-water.mjs", "paired-water-service.mjs", "execution-review.mjs", "execution-review-ui.mjs", "roadmap-handoff.mjs", "roadmap-handoff-ui.mjs", "forecast-decision.mjs", "pilot.mjs", "pilot-ui.mjs", "pilot-builder.mjs",
                "storage-frontier.mjs", "plan-resilience.mjs", "resilience-ui.mjs", "plan-sequence.mjs", "plan-sequence-ui.mjs", "sequence-revision.mjs", "observation-reconciliation.mjs", "reconciliation-ui.mjs", "observation-restart.mjs", "plan-revision.mjs", "plan-revision-ui.mjs", "data.json", "manifest.json", "research.json", "vendor/papaparse.min.js"}
    if not required.issubset(assets):
        raise ValueError("Required public workspace assets are missing")
    return assets


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def matching_workspace(url, assets):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    expected_headers = {header["key"]: header["value"] for header in HEADERS}
    expected_headers["Cache-Control"] = "no-store"
    try:
        for name, content in assets.items():
            request = urllib.request.Request(url + "/" + urllib.parse.quote(name, safe="/"),
                                             headers={"Accept-Encoding": "identity"})
            with opener.open(request, timeout=2) as response:
                if response.status != 200 or response.read(len(content) + 1) != content:
                    return False
                if any(response.headers.get(key) != value for key, value in expected_headers.items()):
                    return False
    except (OSError, ValueError, http.client.HTTPException):
        return False
    return True


class WorkspaceHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        # Development reloads need full module responses, including old cache validators.
        del self.headers["If-Modified-Since"]
        return super().send_head()

    def end_headers(self):
        for header in HEADERS:
            self.send_header(header["key"], header["value"])
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def list_directory(self, path):
        self.send_error(404, "No directory listing")
        return None

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8510)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Port must be between 1 and 65535")
    try:
        assets = public_assets()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Workspace assets could not be verified: {error}") from error
    url = f"http://127.0.0.1:{args.port}"
    handler = functools.partial(WorkspaceHandler, directory=str(PUBLIC))
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        if not matching_workspace(url, assets):
            raise SystemExit(f"Port {args.port} is in use. Choose another port with --port. No running service was changed.") from error
        print(f"AquaShift is already available: {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return
    print(f"AquaShift operations workspace: {url}\nFiles and review records stay in this browser. Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
