# Stefanos v2 validation

**V2 improves on v1 and its supplied raw forecast. It does not reach the earlier ECMWF day2 benchmark.**

Received from `nwp-features`, commit `85097a560769ad8a1459ce55f0b3a4c301202405`. This is the new 4 October handoff, not the earlier CSV or the evaluator's format version. No model was trained, tuned or modified for this comparison.

All 3,566 supplied rows match the original validation origins, actual values and yesterday values exactly. Source labels are origin hours. Targets are origin plus 24 hours, from 5 December 2025 at 19:00 through 3 May 2026 at 08:00. Events are radiation **strictly greater than 600 W/m²**.

| Validation forecast | Precision | Recall | F1 | TP | FP | FN | MAE W/m² |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stefanos v2 | 91.289% | 85.621% | 88.364% | 262 | 25 | 44 | 18.697 |
| Raw forecast supplied with v2 | 88.153% | 82.680% | 85.329% | 253 | 34 | 53 | 21.558 |
| Yesterday | 79.739% | 79.739% | 79.739% | 244 | 62 | 62 | 32.469 |
| Original supplied model | 81.419% | 78.758% | 80.066% | 241 | 55 | 65 | 29.337 |
| Earlier pinned ECMWF day2 | 92.734% | 87.582% | 90.084% | 268 | 21 | 38 | 17.693 |
| Saved 008 event correction | 92.808% | 88.562% | 90.635% | 271 | 21 | 35 | — |

Against the raw forecast in its own file, v2 catches nine more events and makes nine fewer false calls. Against v1, it catches 21 more events and makes 30 fewer false calls. Against the earlier day2 control, it misses six additional events and makes four additional false calls. These are validation differences, not a statistical significance claim or a forecast of test performance.

## Why the two raw results differ

The incoming `forecast` column differs from the retained day2 control in 1,721 hours, including 70 different event calls. Stefanos's downloader requests `shortwave_radiation_previous_day1`, with no model specified and `timezone=auto`. The retained archive explicitly requests `ecmwf_ifs025` day2, stores UTC epochs and joins using the previously recovered fixed UTC+03 source clock. Both feature sets are joined at origin +24 hours. They are distinct weather inputs, not two scores of the same forecast.

V2 therefore passes a comparison against **its supplied raw forecast**. It does not meet the **earlier approximately 0.90 control**. Reconcile the intended forecast source with Stefanos before calling that gate passed. This report does not choose or train his next model.

[Exact ECMWF request and field availability](weather-source/ecmwf-source.md) identifies `models=ecmwf_ifs025`, the original URL and timestamp convention. The retained day1 radiation and cloud fields cover every original train, validation and test target. Day2 cloud has 129 missing validation hours. The source check does not score a new model or imply that swapping weather inputs will preserve the same gain.

The 008 row is the previously selected `consensus_two_source` event correction, with fixed retain probability >0.50 and add probability >0.60. That policy was selected on this validation set. It is shown because the handoff requested the saved classifier, not as an untouched validation estimate. V2 also uses validation for early stopping. Weather-model radiation is a proxy reference, not a field sensor or observed curtailment. Archive files do not establish live issuance availability.

## Evidence and reproduction

`inputs/manifest.json` identifies exact incoming bytes and source files from Stefanos's commit. The retained source files are inspection copies only. `comparison-reviewed.json` contains all matched metrics, input hashes and differing raw-hour identities. `comparison.json` is the first run before an additional classifier-policy integrity guard was added. Both runs have identical matched results. `tests.log` and `tests-receipt.json` record 13 passing checks against the final evaluator.

From the repository root, write to a new output filename:

```sh
PYTHONDONTWRITEBYTECODE=1 python app/tools/compare_prediction_versions.py \
  --incoming app/handoff/v2-validation-2026-10-04/inputs/cv_predictions_v2.csv \
  --reference eval/cv_predictions.csv \
  --model-id 'Stefanos nwp-features v2 85097a5 validation' \
  --incoming-time-basis feature --reference-time-basis feature \
  --raw-control app/experiments/f1-004/result/predictions/validation-nwp_day2.csv \
  --classifier app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv \
  --classifier-policy app/experiments/f1-008/result/validation-selection.json \
  --output app/handoff/v2-validation-2026-10-04/comparison-new.json
```

The independent check computes counts without the shared evaluator. Its source and retained result are `independent-check.py` and `independent-check.json`. No final-model or test run is included. Original `model/`, `data/` and `eval/` remain unchanged on the evaluation branch.

Recheck the retained independent result without changing files:

```sh
PYTHONDONTWRITEBYTECODE=1 python app/handoff/v2-validation-2026-10-04/independent-check.py --check
```
