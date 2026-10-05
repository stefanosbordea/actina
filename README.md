# Aktina

Turn daytime solar availability into stored water through desalination scheduling.

Stefanos develops the radiation models and scheduler. Loukas Louka contributes evaluation, separate forecast research, the website and delivery materials.

Start with the [model map](docs/MODEL-MAP.md) for ownership, inputs and version differences. The [application guide](app/README.md) covers the demo and repository layout.

| Work | Location |
|---|---|
| Stefanos's original model, data and outputs | [model/](model/), [data/](data/), [eval/](eval/) |
| Stefanos's new v2 source | [Merged v2 source](model/train_modelv2.py) |
| Received v2 validation and comparison | [V2 handoff](app/handoff/v2-validation-2026-10-04/README.md) |
| V2 curve and event comparisons | [Forecast view](app/site/forecast.html) |
| Separate event-model research, including 008 | [Experiment index](app/experiments/README.md) |
| Current site and presentation materials | [app/site/](app/site/), [app/delivery/](app/delivery/) |

Build and open the retained demo without fitting any model:

```sh
node app/build.mjs
python3 -m http.server 8527 --bind 127.0.0.1 --directory app/dist
```

Open `http://127.0.0.1:8527/`. The build copies packaged site assets into `app/dist`. It does not run training, evaluation or scheduling.

As of 4 October 2026, the forecast page defaults to **V2 + event correction (019)**. On the same 3,566 validation hours, F1 is **91.062%**, versus **90.635%** for 008 and **88.364%** for supplied v2. Compared with 008 it has four fewer false alarms and one additional miss. This is a historical validation improvement, not proven superiority on new data. [Model lineage and evidence](docs/MODEL-MAP.md#current-evaluation-status).

Stefanos's `nwp-features` commit `85097a5` is merged into `stefanos-model`. Its seven added files are preserved byte-for-byte. `main` remains a separate branch. The small correction is kept under [app/experiments/v2-019/](app/experiments/v2-019/README.md), with the earlier failures and independent audits retained.

The demo uses historical files and illustrative plant, demand and price assumptions. It has no plant-control connection and establishes no measured operating savings.
