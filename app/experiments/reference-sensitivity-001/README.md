# Reference sensitivity 001

Completed under the reviewed protocol and narrow serialization amendment. **No fitting, threshold selection or model promotion.** All eight fixed 004 defaults were scored on both existing splits. Nine fixture tests pass; all 16 complete-weather records reproduce the existing 004 default confusion counts and metrics.

The same forecasts are measured against two references. SARAH3 is a satellite-derived estimate, not an independent local ground sensor. The original test was already examined during development. This substitution provides no significance or live-availability claim.

## Coverage

| Split | Original hours | Common scored hours | Missing reference | Coverage |
|---|---:|---:|---:|---:|
| validation | 3,566 | 3,419 | 147 | 95.878% |
| test | 3,567 | 3,517 | 50 | 98.598% |

All original rows and forecasts remain in the membership files. A satellite null is unscored; no reference was filled in and no missing forecast was intersected away. UTC missing endpoint spans, inclusive:

- validation: 2026-02-13T00:00:00+00:00 through 2026-02-14T00:00:00+00:00 (25 hours).
- validation: 2026-03-15T00:00:00+00:00 through 2026-03-19T00:00:00+00:00 (97 hours).
- validation: 2026-03-31T00:00:00+00:00 through 2026-04-01T00:00:00+00:00 (25 hours).
- test: 2026-07-01T00:00:00+00:00 through 2026-07-02T00:00:00+00:00 (25 hours).
- test: 2026-07-20T00:00:00+00:00 through 2026-07-21T00:00:00+00:00 (25 hours).

## Fixed comparisons

F1 columns distinguish the complete original weather reference, that weather reference on the common available-satellite subset, and the satellite reference on exactly that same subset. P/R means precision/recall; MAE/RMSE are W/m². Scenario point forecasts remain their saved medians; classification uses saved default probability >0.5, not selected decisions or thresholded medians.

### Validation

| Method | Weather full F1 | Weather common F1 | Satellite common F1 | Satellite P/R | Satellite MAE/RMSE |
|---|---:|---:|---:|---:|---:|
| original | 0.800664 | 0.814685 | 0.738676 | 0.757143/0.721088 | 45.167/95.072 |
| persistence | 0.797386 | 0.810997 | 0.746575 | 0.751724/0.741497 | 43.596/95.072 |
| nwp_day2 | 0.900840 | 0.905861 | 0.807080 | 0.841328/0.775510 | 33.818/73.109 |
| median_bias | 0.900840 | 0.905861 | 0.807080 | 0.841328/0.775510 | 33.818/73.109 |
| ridge_bias | 0.898990 | 0.903915 | 0.804965 | 0.840741/0.772109 | 35.481/73.395 |
| global_residual | 0.900840 | 0.905861 | 0.807080 | 0.841328/0.775510 | 33.818/73.109 |
| analogue_raw | 0.899506 | 0.902439 | 0.815972 | 0.833333/0.799320 | 33.852/74.112 |
| analogue_solar | 0.898026 | 0.900870 | 0.811092 | 0.826855/0.795918 | 33.884/74.236 |

### Test

| Method | Weather full F1 | Weather common F1 | Satellite common F1 | Satellite P/R | Satellite MAE/RMSE |
|---|---:|---:|---:|---:|---:|
| original | 0.965483 | 0.964921 | 0.944559 | 0.945529/0.943590 | 25.351/60.644 |
| persistence | 0.977667 | 0.977307 | 0.958248 | 0.951466/0.965128 | 22.094/55.027 |
| nwp_day2 | 0.984143 | 0.983887 | 0.965938 | 0.957661/0.974359 | 19.325/44.948 |
| median_bias | 0.984143 | 0.983887 | 0.965938 | 0.957661/0.974359 | 19.325/44.948 |
| ridge_bias | 0.984064 | 0.983806 | 0.964742 | 0.961303/0.968205 | 20.153/45.086 |
| global_residual | 0.984143 | 0.983887 | 0.965938 | 0.957661/0.974359 | 19.325/44.948 |
| analogue_raw | 0.983655 | 0.983392 | 0.965447 | 0.956697/0.974359 | 18.227/44.952 |
| analogue_solar | 0.983671 | 0.983409 | 0.965482 | 0.955779/0.975385 | 18.272/45.079 |

Every basis retains TP/FP/FN/TN, P/R/F1, MAE/RMSE and its denominator in `result-amended/metrics.csv` (48 records) and `report.json`. These tables do not choose a replacement method.

## What changed

- Coverage alone changes test raw-NWP F1 from 0.984143 to 0.983887. Substituting the reference on the same hours changes it to 0.965938. The latter is a reference effect, not a changed model.
- Raw NWP retains higher test precision, recall and F1 than original weather persistence on the satellite subset. Its precision is 0.957661 against satellite versus 0.984879 against weather on those same hours; the earlier near 99% figure is reference-sensitive.
- The raw analogue’s test MAE advantage over raw NWP narrows from **1.879 W/m²** on common weather reference to **1.098 W/m²** on satellite reference. Its extra false alarm remains: 16 versus 15 with weather labels, 43 versus 42 with satellite labels, with no additional true positives in either comparison.
- Validation source sensitivity is larger: raw-NWP F1 is 0.905861 on common weather reference and 0.807080 on satellite reference. Neither reference is established ground truth.

Weather/satellite event-label agreement on the common hours (`1` means strictly >600 W/m²):

| Split | Both0 | Weather0 / satellite1 | Weather1 / satellite0 | Both1 |
|---|---:|---:|---:|---:|
| validation | 3078 | 49 | 47 | 245 |
| test | 2500 | 23 | 42 | 952 |

## Integrity and reproduction

The initial attempt stopped before scoring on original-control decimal serialization differences. The original protocol, failed `result/`, exit 1 receipt and exact failed checker are retained. The approved `serialization-amendment.json` allows at most 4 ULP only for that control cross-check, with unchanged strict 600 decisions. Actual differences affect 1,309 validation and 745 test rows, maximum 1 and 3 ULP respectively; maximum absolute difference is 1.1368683772161603e-13 W/m², with zero event changes. All differences are recorded. Scoring uses unchanged frozen 004 values. Timestamps, labels, joins, missingness and persistence remain exact.

`inputs.json` binds 22 source files. The active results are in **`result-amended/`**. `run-amended-receipt.json` records the successful command, source/amendment hashes and exit 0; `test-amended-receipt.json` records the nine passing tests. No original benchmark artifact was modified.

```sh
python3 -B -m unittest discover -s app/experiments/reference-sensitivity-001 -p test_check.py -v
python3 -B app/experiments/reference-sensitivity-001/check.py --output app/experiments/reference-sensitivity-001/new-review
```

The checker refuses an existing output directory or changed frozen input bytes. It performs no network requests.
