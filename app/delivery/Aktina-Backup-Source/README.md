# Aktina backup walkthrough

Eight actual interface screenshots, held for 60 seconds in total. This is a screenshot walkthrough, not a live interaction recording. There is no audio, added caption, synthetic cursor, generated scene or branding overlay. All visible results belong to the captured interface.

The sequence covers the product, summer schedule and costs, winter schedule and costs, a changing-weather day, the benchmark and the complete experiment comparison. The original 1600 × 900 screenshots are retained in `captures/`; JPEG screenshots retain their original bytes with the correct `.jpg` extension. The output is 1920 × 1080, 30 frames per second, H.264. Captures are upscaled with Lanczos, without cropping, because this pinned BridgeClip engine requires at least 1080p landscape output. This adds no source detail.

`render.py` composes the unchanged screenshots locally with FFmpeg, then exports through the existing reviewed adapter in `app/scripts/export_bridgeclip_showcase.py` and the unmodified BridgeClip engine at commit `b996820ef80fa324a3ad233bef1aac5cc6936804`. BridgeClip's MIT notices are retained beside this file, outside the video. The adapter disables network access, captions and generated titles.

From the repository root, with the existing Python runtime, FFmpeg, pinned engine and dependencies:

```sh
python3 app/delivery/Aktina-Backup-Source/render.py \
  --bridgeclip /path/to/bridgeclip-src \
  --deps /path/to/existing/runtime/deps \
  --output app/delivery/Aktina-Backup-reproduction.mp4 \
  --work-dir app/delivery/Aktina-Backup-Source/reproduction
```

The output and work directory must be new. `--captures` may point to the original capture directory on the first run; subsequent runs use retained captures. No package installation or browser is required. The adapter receipt records the engine, runtime and source identities; `render-retry1/verification.json` records screenshot hashes, timeline, commands, output identity and checks for 1,800 frames, a 60-second duration, no audio and a successful complete decode. The earlier 900p export was rejected by the adapter's dimension check; its log remains in `render/bridgeclip.log`.
