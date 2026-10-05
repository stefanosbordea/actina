# AktinaBench 003

**The validation-selected model is not promoted.** Its test F1 and recall improve, but precision falls below both the original model and persistence. The choice is unchanged after test inspection.

The useful result is the predeclared archived day2 forecast at the fixed 600 W/m² threshold: it improves all three classification metrics over both references on this period. That is evidence for additional weather information, not proof that a new trained model or live deployment is better. The archive has no verified historical publication timestamps; this is an already-inspected test.

| Full test, 3,567 hours | Precision | Recall | F1 | False calls | Misses | MAE W/m² | RMSE W/m² |
|---|---:|---:|---:|---:|---:|---:|---:|
| Fixed persistence | 98.010% | 97.525% | 97.767% | 20 | 25 | 12.259 | 40.107 |
| Original model | 97.573% | 95.545% | 96.548% | 24 | 45 | 14.266 | 42.660 |
| Archived day2, fixed 600 | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 |
| Archived day2, calibrated | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 |
| Classifier, original 7 inputs | 96.835% | 96.931% | 96.883% | 32 | 31 | — | — |
| Classifier, archived inputs | 97.473% | 99.307% | 98.382% | 26 | 7 | — | — |
| Residual over archived forecast | 98.512% | 98.317% | 98.414% | 15 | 17 | 8.806 | 22.800 |

Validation chose `classifier_nwp`, probability cutoff **0.19**. Its test has 26 false calls and 7 misses, versus persistence’s 20 and 25. The direct forecast has 15 and 17. The calibrated archive selected 600; the residual method selected alpha 0, so those two rows are the same direct forecast, not independent wins. The unqualified seven-feature classifier is shown at its fixed 0.5 default.

Fixed defaults remain in the full comparison: the augmented classifier at 0.5 has test precision/recall/F1 of 98.320% / 98.515% / 98.417%; the residual at alpha 1/cutoff 600 has 98.419% / 98.614% / 98.516%. These were not the validation-selected settings. They are reported without replacing the frozen choice.

## Inputs and checks

The raw ECMWF IFS 0.25° archive is retained in `../nwp-archive-001/`. It is joined at origin +24 hours using the empirically checked fixed UTC+03 label convention. Only archived day2 radiation/cloud are added; day1 is not used. The 129 missing cloud values in validation are preserved as native NaN with a missing indicator. Test has no cloud gaps; its training includes those 129 missing values. No original evaluation hour or eligible training row was excluded.

The seven-input and augmented models share the same 24-hour-purged training memberships: 10,675 rows for validation and 14,241 for test. Trees use the protocol settings plus fixed deterministic/column-wise execution flags; the exact code and saved model files retain those settings. Both validation selection and all 368 grid combinations are saved before test fitting/scoring.

The stdlib audit passed 17,832 joined feature rows, 49,931 prediction rows, 28 full scores, 154 monthly scores, all 368 grid combinations, both training memberships and all 28 comparison rows. It checks original labels, UTC joins, missingness, strict thresholds, probabilities versus radiation units, selection and the promotion rule. Original-CSV parser differences are retained explicitly: at most 1.14e-13 W/m², with zero changed classification labels.

## Reproduce

From the repository root, with the already installed environment and report versions:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-003/run.py --output app/experiments/f1-003/result-new
python3 app/experiments/f1-003/check_audit.py
```

The runner refuses to overwrite an output directory. The checker validates retained `result/` without fitting or writing files; `--output` may save a new audit. `result/comparison.csv` includes all methods, splits and selected/default scores; `report.json` includes every target month. Source hashes, exact joined inputs, prediction CSVs, fitted models and `validation-selection.json` are retained. `run.log` records the completed execution.

The original protocol and the timestamped missing-cloud amendment are both preserved. The amendment preceded all 003 training/scoring and changes no grid or promotion criterion. Original model/data/evaluation files, experiment 001 and the public interface remain unchanged. No model or result has been sent to Stefanos from this experiment.

No candidate is a release recommendation without new independent evidence. Radiation is a weather proxy; these results establish no recovered curtailment, plant permission or customer savings.
