# Aktina application

The site presents Stefanos's retained forecasts and schedule. Evaluation, separate research, review tools and delivery materials are kept alongside it. See the [model map](../docs/MODEL-MAP.md) before comparing v1, v2 or experiment 008.

## Open the demo

From the repository root:

```sh
node app/build.mjs
python3 -m http.server 8527 --bind 127.0.0.1 --directory app/dist
```

Open `http://127.0.0.1:8527/`, or the [published demo](https://aktina-pafos-2026.vercel.app/). The build copies `site/` to `dist/` and the earlier review workspace to `dist/workspace/`. Fonts, charts and data are bundled locally. No training, model dependencies or external API calls are required. [Vercel configuration](vercel.json) uses this same build.

Open `/forecast.html` for the [forecast view](site/forecast.html), also linked from the workspace home. The default **Current forecast** uses the audited 019 event decisions and the chronology-safe v2 refit curve it actually consumes. Supplied v2, its retained 562 event cutoff and 008 event calls remain selectable. The original v2 options display the supplied curve. 008 supplies event calls only.

[The packager](tools/prepare_forecast_demo.py) verifies pinned inputs, audit evidence and all 3,566 matched validation hours, including partial boundary days. It does not train or choose a model. Historical event F1 is 91.062%, with 17 false alarms and 36 misses. Relative to 008 this is four fewer false alarms and one additional miss. [Full result and uncertainty](experiments/v2-019/README.md). Neither this event correction nor the animated solar-to-water illustration changes the retained schedule or costs.

The supplied schedule matches a persistence-driven scheduler export. A separate run of the unchanged model-driven scheduler changes 469 production hours. The site preserves the supplied schedule and shows the model forecast separately. [Reproduction and both outputs](handoff/scheduler-reproduction/README.md) explain the difference.

## Where work belongs

| Path | Purpose |
|---|---|
| [site/](site/) | Current demo, AktinaBench and packaged assets |
| [build.mjs](build.mjs), `dist/` | Static build and generated output |
| [tools/](tools/) | Data packaging, hour-membership checks, forecast comparison and delivery packaging |
| [experiments/](experiments/README.md) | Separate research models, frozen protocols, retained results and independent reviews |
| [handoff/](handoff/) | Received files, comparisons, provenance, execution receipts and draft status |
| [delivery/](delivery/) | Presentation, silent video and editable sources, including older versions |
| [web/](web/) | Earlier review workspace, retained at `/workspace/` in the build |
| [scripts/](scripts/) | Workspace, document and video utilities. Individual scripts may write outputs |
| [model/](model/), [data/](data/), [eval/](eval/), [results/](results/) | Earlier reference prototype and its evidence, separate from Stefanos's root directories |

[prepare_demo.py](tools/prepare_demo.py) checks target-hour joins, complete days and water balance before packaging the original CSVs. [package_benchmark.py](tools/package_benchmark.py) checks retained evaluation membership before copying benchmark results. Both write site assets, so rebuilding the existing site does not require running them. [compare_prediction_versions.py](tools/compare_prediction_versions.py) scores supplied files without fitting and refuses changed truth on shared hours.

## Evaluation and research

`/benchmark.html` presents the original supplied forecast comparison and retained early experiments. It is not a live v2 model service. The [new v2 validation report](handoff/v2-validation-2026-10-04/README.md) records the separately received 4 October handoff at the fixed >600 W/m² threshold. [Version and calibration status](../docs/MODEL-MAP.md#current-evaluation-status) distinguishes that handoff from the later threshold scan and completed event correction.

[008](experiments/f1-008/README.md) is a separate event model trained from scratch. It improves five of six historical test event metrics against the archived ECMWF control, with a weather-precision regression. [009](experiments/f1-009/README.md) narrowly improves all six against raw NWP, but weather median MAE worsens and five event metrics regress against 008. Neither result establishes a general replacement or live superiority. [All research and retained failures](experiments/README.md) remain available.

## Delivery and earlier workspace

The refreshed [competition pack](delivery/Aktina-Competition-Pack.zip) includes all 82 current offline site assets, the corrected 12-slide [PowerPoint](delivery/Aktina-Pafos-2026.pptx) and notes, the [technical-summary LaTeX source](delivery/Aktina-Technical-Summary.tex), four forecast QR assets and the verified silent backup. Its [manifest](delivery/Aktina-Competition-Pack.manifest.json) records all 98 entries and the archive hash. No standalone PDF was generated. Shotter will handle the final presentation.

The offline home animation now remembers explicit Play/Pause across reloads. Its [pack update receipt](results/competition-pack-home-motion.json) verifies that only the animation controller and SVG changed. All other packaged files are unchanged. The previous pack is preserved under ignored `build/competition-pack-before-home-motion/`.

The [44-second video](delivery/Aktina-Backup-Final.mp4) is historical screenshot footage that predates the current forecast page. It is a fallback for the earlier schedule demonstration, not a showcase of the new correction. Earlier proposal sources are included as review drafts and need reconciliation with the current technical summary. No private messages or team-setting captures are included. Use the [delivery status](handoff/DELIVERY-STATUS.md) and [packaging guide](tools/PACKAGING.md) for the exact contents and limits. The prior pack is preserved under ignored `build/competition-pack-before-019-handoff/`.

To open the earlier review workspace directly without opening a browser automatically:

```sh
python3 app/scripts/serve_workspace.py --no-browser
```

It contains plan, prediction and water-accounting reviews. Imported files stay in the browser unless exported. The application uses historical data and illustrative assumptions. It has no plant-control connection or measured-savings claim.
