# Models, ownership and current status

Status checked on 4 October 2026. Stefanos develops Aktina's radiation models and scheduler. Loukas Louka contributes evaluation, separate research models and the application. These directories preserve that distinction.

## Which model is which

| Model | What it does | Source and evidence |
|---|---|---|
| Stefanos v1 | LightGBM regression predicts next-day radiation in W/m² from existing weather features. `model.py` uses chronological train, validation and test splits with validation early stopping | [Training source](../model/model.py), [final-model source](../model/final_model.py), [retained predictions](../eval/) |
| Stefanos v2 | A new LightGBM radiation regressor adds numerical-weather inputs. Its supplied validation export contains actual, predicted, yesterday and raw-forecast values | [Stefanos's source at 85097a5](https://github.com/stefanosbordea/actina/blob/85097a560769ad8a1459ce55f0b3a4c301202405/model/train_modelv2.py), [read-only handoff copies](../app/handoff/v2-validation-2026-10-04/inputs/manifest.json) |
| Research 008, selected `consensus_two_source` | A separate event model scores whether radiation exceeds 600 W/m², then applies a saved correction policy to raw ECMWF event calls | [Implementation](../app/experiments/f1-008/run.py), [result and limitations](../app/experiments/f1-008/README.md), [saved selection](../app/experiments/f1-008/result/validation-selection.json) |

008 uses the same LightGBM family as Stefanos's regressors, but it is a separately fitted model. It loads neither his trained weights nor his predicted values as input features. Its inputs reuse the project's weather features and add archived ECMWF/GFS radiation, forecast differences and past-context features. The selected arm is an `LGBMRegressor` with `objective='cross_entropy'`, trained on weather and satellite event targets. Where both labels exist, their binary labels are averaged. Where satellite is missing, the weather label is used.

The selected 008 policy retains a raw ECMWF positive call only when its score is >0.50, and adds a raw negative call only when its score is >0.60. These are event scores, not radiation predictions or verified confidence estimates. The policy was selected on validation. 008 is prior research alongside the evaluation work, not v1 fine-tuning, v2, or a new learning algorithm.

The root [model/](../model/), [data/](../data/) and [eval/](../eval/) paths remain Stefanos's original files on this evaluation branch. The similarly named directories inside `app/` belong to the earlier reference prototype. They are not interchangeable.

## Extending Stefanos's work

The direct integration path is:

```text
Stefanos's nwp-features model
    → supplied cv_predictions_v2.csv
    → matched-hour evaluation
    → unchanged radiation curve and explicit event threshold in the forecast view
```

[The retained v2 CSV](../app/handoff/v2-validation-2026-10-04/inputs/cv_predictions_v2.csv) contains his model's predictions. [The comparator](../app/tools/compare_prediction_versions.py) checks those outputs against the original validation and saves the metrics. [The forecast packager](../app/tools/prepare_forecast_demo.py) prepares verified rows for [the forecast view](../app/site/forecast.html). The supplied radiation curve remains his. An optional validation-selected event threshold changes which hours are called positive, not the predicted radiation values or model weights.

008 belongs alongside this path as a research comparison. It supplies neither Stefanos's curve nor a replacement for his model. A higher validation F1 alone does not select the team's demo or authorize a model change.

[Experiment 016](../app/experiments/v2-016/README.md) implements a direct extension: a chronological refit of Stefanos's v2 configuration feeds a small event-correction model. This differs from his original validation-stopped fit. Its logistic correction reaches 89.33% validation F1 with 26 false calls and does not beat 008. The independent audit replays the saved base and final correction models. The website therefore continues to use his supplied v2 curve.

## Current evaluation status

The published v2 comparison in [commit c3d1cde](https://github.com/stefanosbordea/actina/commit/c3d1cde) uses a fixed event definition and prediction threshold of **strictly >600 W/m²**. It matches all 3,566 validation target hours, actual values and persistence values against the retained original. Its input is pinned to Stefanos's `nwp-features` commit `85097a560769ad8a1459ce55f0b3a4c301202405`.

| Validation result | Precision | Recall | F1 |
|---|---:|---:|---:|
| Original v1 at >600 | 81.419% | 78.758% | 80.066% |
| Supplied v2 at >600 | 91.289% | 85.621% | 88.364% |
| Saved 008 event calls | 92.808% | 88.562% | 90.635% |

[The complete comparison](../app/handoff/v2-validation-2026-10-04/README.md) also includes persistence and both raw weather controls. The raw forecast supplied with v2 differs from the earlier pinned ECMWF day2 control. Their scores must not be described as two results for the same forecast. Origin labels shift +24 hours to target labels without a timezone conversion.

A later validation-only scan selected a predicted-value threshold of **562 W/m²**, with truth still >600. Its F1 is **89.130%**, precision **84.911%** and recall **93.791%**. It trades precision for recall and remains below 008's validation F1 of **90.635%**. Radiation predictions and MAE are unchanged. [Selection evidence](../app/handoff/v2-calibration-2026-10-04/validation-selection.json) and [draft status](../app/handoff/v2-calibration-2026-10-04/DRAFT.md) preserve that run. At the user's request, work on direct extensions of Stefanos's v2 has resumed. The earlier 562 scan remains a validation-selected comparison, with no automatic change to the default model.

No new v2 test predictions have been received or scored. The existing root `eval/test_predictions.csv` is the earlier model's file. Reused validation results do not establish unseen-test performance. ActinaBench's JSON format version 2 is also separate from Stefanos model v2.

## Site and research boundaries

The [static build](../app/build.mjs) copies the current [site](../app/site/) and earlier [review workspace](../app/web/) into `app/dist`. It does not train, evaluate or schedule. The site preserves the supplied historical schedule, whose values reproduce the persistence export. [Scheduler reproduction](../app/handoff/scheduler-reproduction/README.md) keeps the model-driven alternative separate.

[Research experiments](../app/experiments/README.md) retain their own models, source hashes, selections and results. 009 passes all six historical event metrics against raw NWP narrowly, but it has numerical-error tradeoffs and loses five event metrics to 008. No research result here proves live superiority, physical curtailment recovery or operating savings.

## Branches and handoff

- `main` is a separate repository branch.
- `stefanos-model` contains the original model handoff and the evaluation/application work documented here.
- `nwp-features` contains Stefanos's new v2 work. The received source above is pinned to commit `85097a5`, rather than whatever the branch may contain later.

Branches are not merged automatically. Reading the retained v2 source copies or evaluating its CSV does not replace files in `model/`, `data/` or `eval/`. Source changes, model replacement and demo changes require an explicit integration decision.

Use the [application guide](../app/README.md) for site build commands, packaging and delivery locations. Model scripts and experiment runners are not part of the static-site build.
