# Aktina backup walkthrough, version 2

A silent, 60-second screenshot walkthrough. The first six views retain version 1’s actual product, summer, winter and changing-weather captures. The last two show the rebuilt ActinaBench original forecast and Direct classifier views from UI commit `80747b7`, including all seven methods, full-test scores and the precision/recall tradeoff. No narration, music, generated scene, cursor animation, caption or branding overlay is added. Version 1 remains unchanged.

Eight original 1600 × 900 JPEG screenshots are retained in `captures/`. They are upscaled with Lanczos, without cropping, to 1920 × 1080 at 30 fps because the pinned BridgeClip engine requires at least 1080p landscape output. Upscaling adds no source detail. Holds and hard cuts total 1,800 frames.

`render.py` composes the screenshots locally with FFmpeg, then uses the existing reviewed adapter in `app/scripts/export_bridgeclip_showcase.py` and unmodified BridgeClip commit `b996820ef80fa324a3ad233bef1aac5cc6936804`. MIT notices remain beside this file, outside the video. No browser, network connection or installation is needed.

From the repository root, with the existing Python runtime, FFmpeg, engine and dependencies:

```sh
python3 app/delivery/Aktina-Backup-v2-Source/render.py \
  --bridgeclip /path/to/bridgeclip-src \
  --deps /path/to/existing/runtime/deps \
  --output app/delivery/Aktina-Backup-v2-reproduction.mp4 \
  --work-dir app/delivery/Aktina-Backup-v2-Source/reproduction
```

Output and work paths must be new. `capture-provenance.json` records input identities; `render/verification.json` records the timeline, commands, output identity and full decode, frame-count, duration, dimension and zero-audio checks. The sibling `.bridgeclip.json` records the pinned engine, runtime and adapter. `v1-preservation.json` records the unchanged first-version files.
