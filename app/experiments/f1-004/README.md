# AktinaBench 004

**No learned-method promotion.** Validation retained the fixed archived day2 forecast. Neither analogue qualified against its precision and recall. The research methods remain separate from the product and Stefanos’s model.

Conditional residual scenarios improve continuous error and probability scores on the retained test, but do not improve every required classification metric over the stronger forecast control. Solar scaling provides no classification win over that control and slightly worsens MAE relative to raw residual analogues.

| Full test, 3,567 hours | Precision | Recall | F1 | False calls | Misses | MAE W/m² | RMSE W/m² | Brier |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Persistence | 98.010% | 97.525% | 97.767% | 20 | 25 | 12.259 | 40.107 | 0.012616 |
| Original model | 97.573% | 95.545% | 96.548% | 24 | 45 | 14.266 | 42.660 | 0.019344 |
| Fixed archived day2 | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 | 0.008971 |
| Training median bias | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 | 0.008971 |
| Ridge correction | 98.998% | 97.822% | 98.406% | 10 | 22 | 9.433 | 22.712 | 0.008971 |
| Global residual scenarios | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 | 0.007663 |
| Raw residual analogues | 98.414% | 98.317% | 98.366% | 16 | 17 | 6.921 | 22.125 | 0.006772 |
| Solar-scaled analogues | 98.318% | 98.416% | 98.367% | 17 | 16 | 6.961 | 22.303 | 0.006770 |

All scenario methods are shown at their fixed .5 default because no searched alternative qualified for promotion beyond the fixed forecast. Global residual scenarios and the median-bias control retain the same point/classification result as the raw forecast; their uncertainty representation differs.

| Scenario method | Full-period 90% interval coverage | Mean width W/m² | Daytime coverage | Daytime width W/m² |
|---|---:|---:|---:|---:|
| Global residual scenarios | 94.28% | 48.72 | 89.14% | 60.75 |
| Raw residual analogues | 96.30% | 38.96 | 93.50% | 72.82 |
| Solar-scaled analogues | 96.55% | 42.25 | 93.77% | 79.16 |

Daytime is the preregistered geometrical scale >100; test includes 1,878 such hours. Nighttime zeros can make full-period interval coverage look stronger. These are empirical marginal intervals, not calibrated coverage guarantees or coherent daily scenarios. The 64 historical neighbours are not 64 independent observations.

## What was run

Eight fixed methods, all original evaluation hours, the same purged memberships and original model-derived target values. The raw and solar-scaled analogues share exactly the same K=64 neighbours; only residual scaling changes. Their source hours and distances are retained, along with every scenario. There is no synthetic truth, future-label access, night override or upper clear-sky cap.

The NOAA calculation averages six midpoints of the preceding hour under the fixed UTC+03 label convention. Its scale is geometric, not an atmospheric clear-sky model. Cloud median imputation, missing indicators, feature scaling and Ridge fitting use training only. The same 129 cloud gaps remain in validation and later pre-test training.

The frozen protocol was reviewed before execution. Validation selection was saved before fitting/scoring test. Both original controls and the stronger day2 control remain in every comparison. All nine cutoffs for each scenario method are retained, including failures; no test retuning occurred.

## Reproduce

From the repository root, using the existing local environment and the report’s versions:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-004/run.py --output app/experiments/f1-004/result-new
```

The runner refuses to overwrite an output directory. `result/comparison.csv` contains all selected/default full-period and daytime results; `report.json` includes every target month. `parameters/` retains training medians/scalers, Ridge coefficients and global representative source IDs. Compressed neighbour/scenario files and ordinary prediction CSVs permit independent reconstruction. The run completed with exit status 0; `run.log` and source/input hashes are retained.

Runtime disclosure: reusing experiment 001’s input/count helpers transitively imports the already installed LightGBM and joblib, beyond the libraries explicitly named in the protocol runtime paragraph. No LightGBM estimator is fitted in 004, no package was installed, and the frozen source/protocol were not rewritten to conceal this dependency. The run uses SciPy 1.18.1, joblib 1.6.0 and LightGBM 4.7.0 alongside the versions in `report.json`.

The historical forecast archive has no verified publication vintage; the original target is a weather-model/reanalysis reference, not an independent irradiance sensor. The already-inspected test remains exploratory. This experiment supplies no plant-control permission, recovered-curtailment claim or customer-saving estimate. A future, locked evaluation is a separate task.

## Independent checks

`review-check.py` reconstructed all 7,133 query neighbourhoods, shared neighbours, scenarios, point/probability/interval outputs, count metrics, membership and validation selection: PASS, exit 0. Its output and the actual run command/versions are pinned in `run-receipt.json`. Recheck with:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-004/review-check.py
```

The separately requested, post-result paired-day bootstrap is retained in `review-daily-bootstrap.json`. Its 20,000 replicates support lower retrospective MAE/RMSE for raw analogues versus raw day2; F1/precision intervals cross zero. Brier improvement against the global-residual control also has an interval crossing zero. It changes no selection or promotion decision.
