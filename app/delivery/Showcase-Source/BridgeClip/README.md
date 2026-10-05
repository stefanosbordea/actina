# BridgeClip export

AquaShift's composed film is finished with BridgeMind's **BridgeClip** local rendering engine. The upstream source is unmodified and pinned to:

- Repository: <https://github.com/bridge-mind/bridgeclip>
- Commit: `b996820ef80fa324a3ad233bef1aac5cc6936804`
- License: MIT; upstream notices are retained in `LICENSE` and `ENGINE-LICENSE`.

The adapter is `scripts/export_bridgeclip_showcase.py` in the AquaShift repository. It calls BridgeClip's `RenderingService.render_clip()` with a `RenderRequest`, an explicit full-frame `ClipLayoutPlan`, and manually selected source intervals. BridgeClip builds the synchronized video/audio edit and performs its own output timing checks.

The export uses 16:9, the source frame rate, natural timing, and source audio. BridgeClip normalizes the audio and encodes H.264/AAC. It adds no captions or title overlays. On macOS, upstream selects VideoToolbox with software fallback allowed.

No Electron or Chrome window, transcription, automatic clipping, AI planning, face analysis, upload, API key, or cloud provider is used. The adapter blocks Python internet connections; upstream restricts media input protocols to local files and pipes. The film's music-only composition is made before this export; the adapter does not detect or remove speech.

## Reproduce

Run from the AquaShift repository with Python 3.12, Git, FFmpeg, and FFprobe installed. The commands below use the mounted work volume used for this render; verify it is mounted before creating files there. Use a fresh output filename, since the adapter refuses to overwrite an existing film or receipt.

```sh
git clone https://github.com/bridge-mind/bridgeclip build/bridgeclip-src
git -C build/bridgeclip-src checkout --detach b996820ef80fa324a3ad233bef1aac5cc6936804

bridgeclip_work=/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip
python3.12 -m venv "$bridgeclip_work/reproduce-venv"
"$bridgeclip_work/reproduce-venv/bin/python" -m pip install -r delivery/Showcase-Source/BridgeClip/requirements-lock.txt

"$bridgeclip_work/reproduce-venv/bin/python" scripts/export_bridgeclip_showcase.py \
  --source "$bridgeclip_work/AquaShift-Showcase-master.mp4" \
  --output "$bridgeclip_work/AquaShift-Showcase-reproduced.mp4"
```

If `build/bridgeclip-src` already contains the pinned checkout, omit the clone. The adapter verifies the exact commit and rejects modifications inside the engine directory.

For a shorter edit, append ordered, nonoverlapping `--keep START:END` options in source seconds. For example, `--keep 0:8 --keep 18:34` keeps 24 seconds. Each selection must fit inside the source; no automatic pacing may alter it. Use the actual delivery receipt's `manual_ranges_ms` to reproduce a delivered cut.

## Evidence

Each successful export writes `<output-name>.bridgeclip.json` beside the MP4. It records source/output SHA-256, exact selected intervals, upstream commit/license hashes, runtime versions, invoked media commands, actual start/end times, and verification results. The adapter checks dimensions, frame rate, duration, audio presence, source stability, and a complete strict decode. Hardware encoding may produce different bytes on another machine.

The lock file records the installed runtime packages used for this integration, including Pillow from the bundled Python runtime. OpenCV is unnecessary for these explicit landscape edits. Some cloud-related packages are import dependencies of upstream's service package; their services are never instantiated for this export.
