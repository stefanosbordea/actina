# Models, ownership and current status

Status checked on 4 October 2026. Stefanos develops Aktina's radiation models and scheduler. Loukas Louka contributes evaluation, separate research models and the application. These directories preserve that distinction.

## Which model is which

| Model | What it does | Source and evidence |
|---|---|---|
| Stefanos v1 | LightGBM regression predicts next-day radiation in W/m² from existing weather features. `model.py` uses chronological train, validation and test splits with validation early stopping | [Training source](../model/model.py), [final-model source](../model/final_model.py), [retained predictions](../eval/) |
| Stefanos v2 | A new LightGBM radiation regressor adds numerical-weather inputs. Its supplied validation export contains actual, predicted, yesterday and raw-forecast values | [Merged upstream source](../model/train_modelv2.py), [read-only handoff copies](../app/handoff/v2-validation-2026-10-04/inputs/manifest.json) |
| Research 008, selected `consensus_two_source` | A separate event model scores whether radiation exceeds 600 W/m², then applies a saved correction policy to raw ECMWF event calls | [Implementation](../app/experiments/f1-008/run.py), [result and limitations](../app/experiments/f1-008/README.md), [saved selection](../app/experiments/f1-008/result/validation-selection.json) |

008 uses the same LightGBM family as Stefanos's regressors, but it is a separately fitted model. It loads neither his trained weights nor his predicted values as input features. Its inputs reuse the project's weather features and add archived ECMWF/GFS radiation, forecast differences and past-context features. The selected arm is an `LGBMRegressor` with `objective='cross_entropy'`, trained on weather and satellite event targets. Where both labels exist, their binary labels are averaged. Where satellite is missing, the weather label is used.

The selected 008 policy retains a raw ECMWF positive call only when its score is >0.50, and adds a raw negative call only when its score is >0.60. These are event scores, not radiation predictions or verified confidence estimates. The policy was selected on validation. 008 is prior research alongside the evaluation work, not v1 fine-tuning, v2, or a new learning algorithm.

The root [model/](../model/), [data/](../data/) and [eval/](../eval/) paths preserve Stefanos's original files and the seven additions merged from his `nwp-features` commit `85097a5`. The similarly named directories inside `app/` belong to the earlier reference prototype. They are not interchangeable.

## Extending Stefanos's work

The default historical forecast path is:

```text
Stefanos's v2 features and LightGBM configuration
    → chronology-safe refit retained in 016
    → small logistic event correction retained in 019
    → packaged radiation curve and event decisions in the forecast view
```

019 depends on actual predictions from the v2 refit. It does not load 008 predictions or weights. The original supplied v2 fit used validation for early stopping. The 016 refit chooses its tree count inside training, then freezes the curve. Their radiation MAEs are 18.697343 and 18.700675 W/m² respectively. The event correction improves classification, not the numerical radiation error.

The correction has 15 readable coefficients and one intercept. It combines the v2 forecast with numerical-weather inputs, solar/calendar features and four strictly past 14-day error summaries. Its fixed logistic configuration and train-only threshold selection are documented in [019](../app/experiments/v2-019/README.md). [Saved coefficients](../app/experiments/v2-019/result/expanded-final.json) and [independent replay](../app/experiments/v2-019/review/review.json) make the extension inspectable.

[016](../app/experiments/v2-016/README.md), [017](../app/experiments/v2-017/README.md) and [018](../app/experiments/v2-018/README.md) retain the earlier candidates that failed the comparison with 008. No failed result was removed. The forecast page retains supplied v2, cutoff 562 and 008 as explicit comparisons. The original supplied curve is shown only with the original v2 options.

## Current evaluation status

The published v2 comparison in [commit c3d1cde](https://github.com/stefanosbordea/actina/commit/c3d1cde) uses a fixed event definition and prediction threshold of **strictly >600 W/m²**. It matches all 3,566 validation target hours, actual values and persistence values against the retained original. Its input is pinned to Stefanos's `nwp-features` commit `85097a560769ad8a1459ce55f0b3a4c301202405`.

| Validation result | Precision | Recall | F1 |
|---|---:|---:|---:|
| Original v1 at >600 | 81.419% | 78.758% | 80.066% |
| Supplied v2 at >600 | 91.289% | 85.621% | 88.364% |
| Saved 008 event calls | 92.808% | 88.562% | 90.635% |
| V2 refit + correction 019 | 94.077% | 88.235% | 91.062% |

[The complete comparison](../app/handoff/v2-validation-2026-10-04/README.md) also includes persistence and both raw weather controls. The raw forecast supplied with v2 differs from the earlier pinned ECMWF day2 control. Their scores must not be described as two results for the same forecast. Origin labels shift +24 hours to target labels without a timezone conversion.

019's expanded correction has **270 true positives, 17 false positives, 36 false negatives and 3,243 true negatives**. Compared with supplied v2, it catches eight more events with eight fewer false alarms. Compared with 008, it has four fewer false alarms and one additional miss. Recall is slightly lower than 008.

The descriptive paired-day interval for the F1 difference against 008 is **−1.606 to +2.622 percentage points**, including zero. Validation has been inspected across several experiments, so the point gain is not proof of a reliable gain on unseen data. Past-error features use only observations resolved before each forecast origin, making this a sequential historical simulation. It is not a live deployment backtest.

The earlier validation-only cutoff of **562 W/m²** remains available. Its F1 is **89.130%**, precision **84.911%** and recall **93.791%**, with 51 false alarms. It changes event calls, not radiation predictions. [Selection evidence](../app/handoff/v2-calibration-2026-10-04/validation-selection.json).

No new v2 test predictions have been received or scored. The existing root `eval/test_predictions.csv` is the earlier model's file. Reused validation results do not establish unseen-test performance. ActinaBench's JSON format version 2 is also separate from Stefanos model v2.

## Site and research boundaries

The [static build](../app/build.mjs) copies the current [site](../app/site/) and earlier [review workspace](../app/web/) into `app/dist`. It does not train, evaluate or schedule. The site preserves the supplied historical schedule, whose values reproduce the persistence export. [Scheduler reproduction](../app/handoff/scheduler-reproduction/README.md) keeps the model-driven alternative separate.

[Research experiments](../app/experiments/README.md) retain their own models, source hashes, selections and results. 009 passes all six historical event metrics against raw NWP narrowly, but it has numerical-error tradeoffs and loses five event metrics to 008. No research result here proves live superiority, physical curtailment recovery or operating savings.

## Branches and handoff

- `main` is a separate repository branch.
- `stefanos-model` contains the evaluation/application work and the explicit merge of `nwp-features` at `85097a5` on 4 October.
- `nwp-features` remains Stefanos's development branch. The merge adds his v2 training script, NWP download/features scripts, input data and validation export without rewriting them.

The default historical view uses the audited 019 correction at the user's request. This does not replace the supplied scheduler or its costs, and does not alter Stefanos's upstream training code. [Integration receipt](../app/handoff/v2-integration-2026-10-04/) records file identities.

Use the [application guide](../app/README.md) for site build commands, packaging and delivery locations. Model scripts and experiment runners are not part of the static-site build.
