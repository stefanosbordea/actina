# AktinaBench 002

**No model promotion.** Validation selected the seven-feature residual model, alpha 1 and cutoff 620 W/m². On the complete test it reduces false surplus calls but misses too many positive hours. It fails the additional requirement to exceed Stefanos's original model in F1, precision and recall and match or exceed persistence in all three.

| Full test, 3,567 hours | Precision | Recall | F1 | False calls | Misses | MAE W/m² | RMSE W/m² |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed persistence | 98.010% | 97.525% | 97.767% | 20 | 25 | 12.259 | 40.107 |
| Original model | 97.573% | 95.545% | 96.548% | 24 | 45 | 14.266 | 42.660 |
| Absolute L1, selected cutoff 620 | 98.438% | 93.564% | 95.939% | 15 | 65 | 12.010 | 40.459 |
| Residual, 7 features, selected cutoff 620 | 98.233% | 93.564% | 95.842% | 17 | 65 | 11.360 | 40.396 |
| Residual, 25 features, selected cutoff 620 | 98.140% | 94.059% | 96.057% | 18 | 60 | 11.103 | 38.400 |

The added causal history/calendar bundle lowers MAE/RMSE against the matched seven-feature residual model, but not its validation F1. At the fixed 600 cutoff, test precision/recall/F1 are 97.537% / 98.020% / 97.778% for seven features and 97.157% / 98.119% / 97.635% for 25 features. Neither meets the promotion rule. These fixed-default results remain visible; the selected cutoff was not changed after test inspection.

`result-retry1/comparison.csv` contains every method, split and selected/default outcome. `report.json` includes every target month. Raw predictions, all 231 validation combinations, fitted trees and exact training memberships are retained beside it. `validation-selection.json` was written before fitting/scoring test models.

## Reproduce and check

From the repository root, using the installed environment with the versions in the report:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-002/run.py --output app/experiments/f1-002/result-new
python3 app/experiments/f1-002/check_audit.py
```

The run refuses to overwrite an output directory. The checker reads the retained `result-retry1`; it does not fit a model or write files unless given a new `--output` path. Its independent stdlib recomputation passed 35,665 prediction rows, 20 full scores, 110 monthly scores, 231 validation combinations, both training memberships and all 20 comparison rows. CSV parser representation differs from Python's float parser in 2,054 retained original-prediction values, by at most 1.14×10⁻¹³ W/m²; zero classification labels change. This residual is reported explicitly, with a 10⁻⁹ absolute numerical comparison tolerance.

The first attempt stopped before training: a cadence check compared microsecond-index integers with nanoseconds. `attempts/` retains that source and log. The successful run compares timedeltas directly; the frozen protocol, data, split membership and model settings were not changed. `run-retry1.log` records the completed execution.

Original inputs and experiment 001 remain untouched. Training purges 24 hours; all newly fitted methods use the same training rows, with no warmup exclusion and no evaluation-hour loss. Original timestamp labels are preserved, not converted into a guessed civil timezone. Historical availability of the archive observations remains unverified.

The test was already inspected before this experiment; these are exploratory results. Even a passing numerical comparison would require new independent evidence before release. Radiation classification establishes neither recovered curtailment nor useful plant scheduling.
