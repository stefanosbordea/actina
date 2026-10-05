# AquaShift — editable Blender scenes

Three monochrome scenes explain Loucas Louka’s original concept: use otherwise curtailed solar electricity to produce water, store it, and supply it later. Stefanos (Στέφανος Μπορτέας) developed the competition roadmap. The imagery illustrates the mechanism; it is not footage of a plant, measured grid surplus, recovered curtailment or validated tank volumes.

The scenes contain geometry, materials, lighting, camera motion, directional flow markers and animated water levels. They need no external assets. `scene-check.json` records the actual packing and scene checks. `frame-check.json` records the rendered frame checks. The original render manifests retain the exact invocation and source hashes.

| Scene | Motion | Native output |
|---|---|---|
| `aquashift-overview.blend` | Solar electricity and water production; tank fills | 108 frames, 12 fps, 9 s |
| `aquashift-storage.blend` | Closer view of water production and storage | 108 frames, 12 fps, 9 s |
| `aquashift-evening.blend` | Production stops; stored water supplies homes | 108 frames, 12 fps, 9 s |

Tested with Blender 5.2.2 LTS, using Eevee at 1280 × 720. All materials, lights and the world use equal-channel gray values. The finished film composes these shots into a 1920 × 1080 canvas; its own production notes record the conversion to 24 fps.

To regenerate a scene, run from this folder with your Blender executable:

```sh
BLENDER="/absolute/path/to/Blender"
"$BLENDER" --background --python-exit-code 1 --python blender_video.py -- \
  --output ./render --act overview --width 1280 --height 720 --fps 12 --samples 32
```

Repeat with `--act storage` and `--act evening`. The generator saves a compressed `.blend`, its exact source snapshot, PNG sequence and a render manifest. Add `--frames 1,54,108` for three preview stills.

To render an edited scene directly:

```sh
"$BLENDER" --background aquashift-overview.blend \
  --render-output ./render/overview/frame- --render-format PNG --render-anim
```

Large native sequences are retained at `/Volumes/CARMIX-WORK/AquaShift-video-2026-10-02/render-monochrome/{overview,storage,evening}/frame-%04d.png`. The installed Blender binary is retained on the same verified mounted build volume. The packed scene files in this folder remain usable without that volume.
