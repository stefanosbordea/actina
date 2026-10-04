# Aktina application

The site presents Stefanos's retained forecasts and schedule. Evaluation, separate research, review tools and delivery materials are kept alongside it. See the [model map](../docs/MODEL-MAP.md) before comparing v1, v2 or experiment 008.

## Open the demo

From the repository root:

```sh
node app/build.mjs
python3 -m http.server 8527 --bind 127.0.0.1 --directory app/dist
```

Open `http://127.0.0.1:8527/`, or the [published demo](https://aktina-pafos-2026.vercel.app/). The build copies `site/` to `dist/` and the earlier review workspace to `dist/workspace/`. Fonts, charts and data are bundled locally. No training, model dependencies or external API calls are required. [Vercel configuration](vercel.json) uses this same build.

Open `/forecast.html` for the [v2 forecast view](site/forecast.html). It displays Stefanos's retained radiation curve, actual values and the two distinct weather controls. Event calls default to >600, with the retained validation-selected 562 threshold and 008 calls available for comparison. Changing the event view leaves the radiation curve and supplied schedule unchanged. [The packager](tools/prepare_forecast_demo.py) verifies source identities and matched hours before writing `site/forecast-data.js`. It does not train or select a model.

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

`/benchmark.html` presents the original supplied forecast comparison and retained early experiments. It is not a live v2 model service. The [new v2 validation report](handoff/v2-validation-2026-10-04/README.md) records the separately received 4 October handoff at the fixed >600 W/m² threshold. [Version and calibration status](../docs/MODEL-MAP.md#current-evaluation-status) distinguishes that published result from the later threshold scan and newly resumed extension work.

[008](experiments/f1-008/README.md) is a separate event model trained from scratch. It improves five of six historical test event metrics against the archived ECMWF control, with a weather-precision regression. [009](experiments/f1-009/README.md) narrowly improves all six against raw NWP, but weather median MAE worsens and five event metrics regress against 008. Neither result establishes a general replacement or live superiority. [All research and retained failures](experiments/README.md) remain available.

## Delivery and earlier workspace

The retained [competition pack](delivery/Aktina-Competition-Pack.zip) predates the latest v2 forecast view and needs repackaging to include it. The [PowerPoint](delivery/Aktina-Pafos-2026.pptx) and [silent final video](delivery/Aktina-Backup-Final.mp4) remain available with their sources. Use the [delivery status](handoff/DELIVERY-STATUS.md) and [packaging guide](tools/PACKAGING.md) to identify reviewed versions. Older AquaShift files remain historical evidence.

To open the earlier review workspace directly without opening a browser automatically:

```sh
python3 app/scripts/serve_workspace.py --no-browser
```

It contains plan, prediction and water-accounting reviews. Imported files stay in the browser unless exported. The application uses historical data and illustrative assumptions. It has no plant-control connection or measured-savings claim.
