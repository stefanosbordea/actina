# Aktina

Turn daytime solar availability into stored water through desalination scheduling.

Stefanos develops the radiation models and scheduler. Loukas Louka contributes evaluation, separate forecast research, the website and delivery materials.

Start with the [model map](docs/MODEL-MAP.md) for ownership, inputs and version differences. The [application guide](app/README.md) covers the demo and repository layout.

| Work | Location |
|---|---|
| Stefanos's original model, data and outputs | [model/](model/), [data/](data/), [eval/](eval/) |
| Stefanos's new v2 source | [nwp-features at 85097a5](https://github.com/stefanosbordea/actina/tree/85097a560769ad8a1459ce55f0b3a4c301202405) |
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

As of 4 October 2026, the published v2 comparison uses the fixed **>600 W/m²** event threshold. No new v2 test predictions have been received. The later validation-only threshold scan is retained separately. Work on direct extensions of Stefanos's v2 has resumed at the user's request, with no automatic model replacement. [Current version status](docs/MODEL-MAP.md#current-evaluation-status).

`main`, `stefanos-model` and `nwp-features` are separate branches. The v2 source link above pins the handoff commit. Reading or evaluating that handoff does not merge it into another branch.

The demo uses historical files and illustrative plant, demand and price assumptions. It has no plant-control connection and establishes no measured operating savings.
