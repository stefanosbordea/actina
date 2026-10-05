# Aktina competition backup

A silent, 44-second screenshot walkthrough of the supplied product demo. Six actual interface views show the homepage, summer production/storage and costs, winter production/storage and costs, and changing weather. Research candidates and benchmark scores are not featured. No narration, music, generated scene, animated cursor, title, caption or branding overlay is added.

The retained screenshots are 1600 × 900. They are upscaled without cropping to 1920 × 1080 at 30 fps because the pinned BridgeClip engine requires at least 1080p landscape output. Upscaling adds no source detail. Readable holds and hard cuts total 1,320 frames. This is a screenshot walkthrough, not a live interaction recording.

The product uses the supplied schedule and illustrative plant/prices. Its visible source caveat and cost comparison conditions remain in the frames. It supplies no claim of a stronger research model, verified operating savings or recovered curtailment. Earlier backup videos remain unchanged.

`capture-provenance.json` identifies the exact screenshot sources. `render/verification.json` retains commands, timeline, output identity and full-decode, frame-count, dimension, duration and zero-audio checks. `visual-review.json` records inspection of decoded final frames. The sibling `Aktina-Backup-Final.bridgeclip.json` records the pinned engine, runtime and adapter. MIT notices stay here, outside the video.

From the repository root, using the existing Python runtime, FFmpeg and dependencies:

```sh
python3 app/delivery/Aktina-Backup-Final-Source/render.py \
  --bridgeclip /path/to/existing/bridgeclip-src \
  --deps /path/to/existing/runtime/deps \
  --output app/delivery/Aktina-Backup-Final-reproduction.mp4 \
  --work-dir app/delivery/Aktina-Backup-Final-Source/reproduction
```

Output and work paths must be new. Rendering uses the reviewed adapter in `app/scripts/export_bridgeclip_showcase.py` and unmodified BridgeClip commit `b996820ef80fa324a3ad233bef1aac5cc6936804`. No browser, network connection or installation is required.
