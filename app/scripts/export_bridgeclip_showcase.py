#!/usr/bin/env python3
"""Export a local 16:9 film through BridgeMind's unmodified BridgeClip engine.

No transcription, AI planning, cloud upload, browser, or automatic reframing.
BridgeClip (MIT): https://github.com/bridge-mind/bridgeclip
The upstream checkout and Python dependencies are supplied separately.
"""

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time


UPSTREAM_COMMIT = "b996820ef80fa324a3ad233bef1aac5cc6936804"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True).stdout


def probe(path):
    return json.loads(command([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe,fd",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height,r_frame_rate,duration,sample_rate,channels",
        "-of", "json", str(path),
    ]))


def selected_ranges(values, duration_ms):
    ranges = []
    for value in values or [f"0:{Fraction(duration_ms, 1000)}"]:
        fields = value.split(":")
        if len(fields) != 2:
            raise ValueError("Each --keep must contain START:END in seconds")
        start, end = (Fraction(field) * 1000 for field in fields)
        if start.denominator != 1 or end.denominator != 1:
            raise ValueError("Use millisecond-precise selection boundaries")
        start, end = int(start), int(end)
        if start < 0 or end <= start or end > duration_ms or (ranges and start < ranges[-1][1]):
            raise ValueError("Selections must be ordered, nonoverlapping, and inside the source")
        ranges.append((start, end))
    if len(ranges) > 12:
        raise ValueError("At most 12 manual selections per export")
    return ranges


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--bridgeclip", type=Path, default=Path(__file__).resolve().parents[1] / "build/bridgeclip-src")
    parser.add_argument("--deps", type=Path, help="Optional isolated Python dependency directory")
    parser.add_argument("--keep", action="append", help="Retain START:END seconds; repeat for ordered manual cuts")
    args = parser.parse_args()
    source, output, upstream = args.source.resolve(strict=True), args.output.absolute(), args.bridgeclip.resolve(strict=True)
    receipt_path = output.with_suffix(".bridgeclip.json")
    if not source.is_file() or output.suffix.lower() != ".mp4":
        raise ValueError("Provide a local video and a new .mp4 output")
    if output.exists() or receipt_path.exists() or not output.parent.is_dir():
        raise ValueError("Output and receipt must be new files in an existing directory")
    commit = command(["git", "-C", str(upstream), "rev-parse", "HEAD"]).strip()
    if commit != UPSTREAM_COMMIT or command(["git", "-C", str(upstream), "status", "--porcelain", "--", "engine"]).strip():
        raise ValueError("Require the reviewed, unmodified BridgeClip engine commit")
    source_probe = probe(source)
    video = next(stream for stream in source_probe["streams"] if stream["codec_type"] == "video")
    if video["width"] * 9 != video["height"] * 16:
        raise ValueError("This showcase exporter preserves a 16:9 source composition")
    duration_ms = round(float(video.get("duration", source_probe["format"]["duration"])) * 1000)
    ranges = selected_ranges(args.keep, duration_ms)
    expected_ms = sum(end - start for start, end in ranges)
    source_sha = digest(source)
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve(strict=True)))
    sys.path.insert(0, str(upstream / "engine"))
    os.environ["LOCAL_MODE"] = "true"
    os.environ["OPENROUTER_API_KEY"] = ""
    os.environ["JEV_ENABLED"] = "false"
    commands = []
    blocked_connections = []

    def audit(event, event_args):
        if event == "socket.connect" and event_args[0].family in (socket.AF_INET, socket.AF_INET6):
            blocked_connections.append("blocked")
            raise RuntimeError("This BridgeClip export is offline; network connection denied")
        if event == "subprocess.Popen":
            commands.append(list(event_args[1]))

    sys.addaudithook(audit)
    from clip_engine.services.rendering_service import RenderRequest, RenderingService
    from clip_engine.services.layout_analyzer import ClipLayoutPlan, LayoutType, ShotLayout

    started = datetime.now(timezone.utc).isoformat()
    clock = time.monotonic()
    plan = ClipLayoutPlan(
        shots=[ShotLayout(0, duration_ms, LayoutType.SCREEN, source="style")],
        source_width=video["width"], source_height=video["height"],
    )
    last_percent = -10

    def progress(stage, percent):
        nonlocal last_percent
        if percent is not None and percent >= last_percent + 10:
            print(f"BridgeClip export {percent}%", flush=True)
            last_percent = percent

    with tempfile.TemporaryDirectory(prefix="bridgeclip-export-", dir=output.parent) as scratch:
        temporary = Path(scratch) / "export.mp4"
        request = RenderRequest(
            video_path=str(source), output_path=str(temporary),
            start_time_ms=0, end_time_ms=duration_ms,
            source_width=video["width"], source_height=video["height"],
            include_captions=False, include_title=False, include_audio=True,
            apply_padding=False, aspect_ratio="16:9", pacing="natural",
            manual_plan=plan, manual_ranges_ms=ranges, progress_callback=progress,
        )
        result = asyncio.run(RenderingService().render_clip(request))
        exported = probe(temporary)
        actual_video = next(stream for stream in exported["streams"] if stream["codec_type"] == "video")
        expected_audio = any(stream["codec_type"] == "audio" for stream in source_probe["streams"])
        actual_audio = any(stream["codec_type"] == "audio" for stream in exported["streams"])
        if (result.render_fallback is not None or result.duration_ms != expected_ms
                or actual_video["width"] != video["width"] or actual_video["height"] != video["height"]
                or Fraction(actual_video["r_frame_rate"]) != Fraction(video["r_frame_rate"])
                or abs(float(exported["format"]["duration"]) - expected_ms / 1000) > 0.08
                or actual_audio != expected_audio):
            raise ValueError("BridgeClip export did not preserve the requested picture, clock, or audio track")
        command(["ffmpeg", "-v", "error", "-xerror", "-nostdin", "-protocol_whitelist", "file,pipe,fd",
                 "-i", str(temporary), "-f", "null", "-"])
        if digest(source) != source_sha or blocked_connections:
            raise ValueError("Source changed during export or a network connection was attempted")
        output_sha = digest(temporary)
        os.link(temporary, output)
    result_data = asdict(result)
    result_data["output_path"] = str(output)
    packages = {name: importlib.metadata.version(name) for name in
                ("Pillow", "pydantic", "pydantic-settings", "httpx", "yt-dlp", "boto3", "aiofiles")}
    receipt = {
        "schema": 1, "status": "EXPORTED_AND_DECODED", "started_at_utc": started,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(time.monotonic() - clock, 3),
        "upstream": {"url": "https://github.com/bridge-mind/bridgeclip", "commit": commit,
                     "license": "MIT", "license_sha256": digest(upstream / "LICENSE"),
                     "engine_license_sha256": digest(upstream / "engine/LICENSE")},
        "source": {"path": str(source), "sha256": source_sha, "probe": source_probe},
        "output": {"path": str(output), "sha256": output_sha, "probe": exported},
        "manual_ranges_ms": ranges, "result": result_data,
        "processing": "Upstream RenderingService; explicit manual selections; source audio retained and normalized by BridgeClip; no captions or generated title",
        "network": {"python_internet_connections": "denied by audit hook", "attempts": len(blocked_connections),
                    "media_protocols": ["file", "pipe", "fd"]},
        "runtime": {"python": sys.version, "packages": packages,
                    "ffmpeg": command(["ffmpeg", "-version"]).splitlines()[0]},
        "adapter_sha256": digest(Path(__file__).resolve()),
        "invocation": [sys.executable, *sys.argv], "media_commands": commands,
        "verification": {"complete_decode": "passed", "source_unchanged": True, "dimensions_fps_duration_audio": "passed"},
    }
    with receipt_path.open("x") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": receipt["status"], "output": str(output), "receipt": str(receipt_path), "sha256": output_sha}))


if __name__ == "__main__":
    main()
