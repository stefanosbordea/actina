# AquaShift showcase

84 seconds, 1920 × 1080, 24 fps. Instrumental music only. The final file is `../AquaShift-Showcase.mp4`.

The opening illustrates Loucas Louka’s original solar-to-desalination concept. The walkthrough shows the current product using synthetic readings on 1 July and separate illustrative plan comparisons on 15 July. These are not plant results or submissions from Stefanos. Primary forecasting and scheduling remain Stefanos’s responsibility.

| Time | What is shown |
|---|---|
| 0–24 s | New symbol; solar electricity, desalination, water storage and later supply |
| 24–40 s | A noon tank reading; assessment of the remaining plan; a four-hour production stop |
| 40–54 s | Original and returned supplied plans; matching water and energy totals |
| 54–72 s | Conditional solar use: +340 kWh in one allocation, zero additional use in a saturated allocation |
| 72–84 s | Actual exported review and closing identity |

## Source and production

`captures/` retains the actual built-in-browser images and the exact JSON exported through the product. The film uses these images with restrained camera motion; it is not a continuous screen recording. Captures came from the current public deployment on 2 October 2026.

`symbol.blend` is editable. `../../scripts/showcase_symbol.py` constructs its two counterforms from the exact curves and transforms in `../brand/AquaShift-Mark.svg`.

`../Blender-Scene-Source/blender_video.py` is the exact retained generator for all three concept scenes (SHA-256 `90f604ab8133b6dfd34b86e9c988ca482952fe807c0db949c2cb6ade970414a3`). Editable scenes are in that folder. The film uses 192 overview frames and 168 storage frames, and frames 36–83 of the retained 720p/12 fps evening render. The evening shot is upscaled and frame-repeated; it is not native 1080p/24 fps footage.

`../../scripts/build_showcase.py` defines every cut, caption, crop and the original deterministic instrumental score. It composes the master with Pillow and FFmpeg. BridgeMind’s unmodified **BridgeClip RenderingService** then performs the final local export, keeping the full 16:9 timeline and normalizing its audio. See `BridgeClip/README.md` for the exact upstream revision, dependency pins, licences and export command. The BridgeClip desktop interface, transcription and cloud services were not used.

## Reproduce on the production Mac

Large source sequences remain on the mounted `/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02` volume. Frame-by-frame input identities are retained in `../../results/showcase-2026-10-02/input-frames.json`. The scripts intentionally require that volume and refuse to replace an existing master or final export.

Run from the repository root with Python 3.12, Pillow and NumPy, plus FFmpeg and the system Helvetica Neue font:

```sh
python3 scripts/build_showcase.py --preview
python3 scripts/build_showcase.py
python3 scripts/export_bridgeclip_showcase.py \
  --source /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip/AquaShift-Showcase-master.mp4 \
  --output /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip/AquaShift-Showcase.mp4 \
  --deps /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip/runtime/deps
python3 scripts/verify_showcase.py \
  /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip/AquaShift-Showcase.mp4 \
  results/showcase-2026-10-02/final
```

Regenerate the symbol with Blender 5.2.2:

```sh
"/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/tools/Blender.app/Contents/MacOS/Blender" \
  --background --python-exit-code 1 --python scripts/showcase_symbol.py -- \
  --svg delivery/brand/AquaShift-Mark.svg \
  --blend delivery/Showcase-Source/symbol.blend \
  --output /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/showcase-bridgeclip/symbol --frames all
```

For the concept scenes, run that generator with `--act overview` or `--act storage`, `--width 1920 --height 1080 --fps 24 --duration 9 --samples 64` and `--output /Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/render-native-24`. The evening generator and command are in the existing Blender source folder. Copy `captures/` to the production `showcase-bridgeclip/assets/` directory if recreating the build. The synthesizer creates `score.wav`; it has no narration or external music sample.

Verification covers a complete media decode, dimensions, duration, frame rate, stereo audio, encoded-picture comparisons at 14 points and measured loudness. The visual sheet supports inspection; it does not turn the illustrative examples into operational evidence. Original project files and prior videos are preserved.
