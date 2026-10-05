# ActinaBench F1 experiment 001

The validation-selected direct classifier raises recall, but does not beat fixed persistence on test F1 or precision. **No candidate improves all three test metrics over persistence.** The neural candidate also underperforms persistence. These are retrospective results on an already-inspected test period.

The method selected before candidate test scoring was `direct_classifier`, with validation F1 **0.855882** and probability cutoff approximately **0.34** (the exact retained cutoff is in the report). Its validation precision also falls below persistence. **The roadmap prioritizes precision because false-surplus decisions cost money.** This F1-selected model should therefore not be promoted as an improvement under that priority. A future precision-constrained experiment would need its criterion fixed before evaluation.

All test results use the same **3,567 hours**, predicting actual radiation **strictly greater than 600 W/m²**. Target dates run from **3 May 2026 09:00 to 28 September 2026 23:00**. Classifier and calibrated-persistence cutoffs were selected on validation only, then frozen.

| Method | F1 | Precision | Recall | TP | FP | FN | TN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Persistence, fixed 600 | 0.977667 | 0.980100 | 0.975248 | 985 | 20 | 25 | 2537 |
| Persistence, CV cutoff 590 | 0.976859 | 0.971596 | 0.982178 | 992 | 29 | 18 | 2528 |
| Purged LightGBM regression | 0.968064 | 0.975855 | 0.960396 | 970 | 24 | 40 | 2533 |
| Direct LightGBM classifier | 0.974535 | 0.964147 | 0.985149 | 995 | 37 | 15 | 2520 |
| History LightGBM classifier | 0.972813 | 0.971372 | 0.974257 | 984 | 29 | 26 | 2528 |
| Neural classifier (64, 32, 16) | 0.957000 | 0.966667 | 0.947525 | 957 | 33 | 53 | 2524 |
| Original retained model | 0.965483 | 0.975733 | 0.955446 | 965 | 24 | 45 | 2533 |

The direct classifier misses 15 surplus hours versus persistence’s 25, while producing 37 false positives versus 20. Changing a classification cutoff trades precision against recall; it does not change the physical 600 W/m² target.

## Evidence

- [Frozen protocol](PROTOCOL.md), [runner](run.py), and [complete run](result-retry1/report.json).
- [Independent audit and original-model monthly scores](independent-audit.json): zero mismatches across 12 prediction files, all selected/default scores, 66 monthly scores and 304 threshold scores; original split membership, timestamps and retained source hashes verified. All seven methods’ overall test rows remain visible above.
- [Saved predictions](result-retry1/predictions/) and [experimental fitted models](result-retry1/models/). Original model, scheduler and data files were not overwritten.
- [Full result table](RESULTS.csv) includes all methods and both splits. Radiation MAE/RMSE use saved radiation scores; probability classifiers leave these fields blank. [Month and hour breakdowns](forecast-breakdown.csv) contain every group, including nighttime. The original validation and test model fits remain separate.
- [First failed invocation](attempts/01-path-error.txt): repository-root resolution used `parents[4]`; input loading failed before training. The successful retry uses `parents[3]`. The failure log is retained.

Training removes 24 rows at each evaluation boundary: 10,675 training rows before validation and 14,241 before test. The latest training target precedes the first evaluation origin. Historical feature timestamps are not proof of live data availability. Causal histories use only the current and preceding weather records; scaling uses training rows only.

The original validation period also informed model development. The test was inspected before this experiment was designed. Neither is a new independent holdout. Fresh later evidence is required before claiming generalization; these classification results establish no plant savings or recovered electricity.

## Reproduce

From the repository root, use Python **3.14.6**, NumPy **2.5.3**, pandas **3.0.6**, scikit-learn **1.9.1**, LightGBM **4.7.0**, and joblib in the active environment:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 app/experiments/f1-001/run.py --output app/experiments/f1-001/result-reproduction
```

The output directory must not already exist. This trains separate experimental models; it does not overwrite `result-retry1`. Package versions, source hashes, cutoffs, warnings and runtimes are retained in each report. Numerical results may vary across library builds or hardware.

Verify the retained run and independent audit without training or loading models, using Python's standard library:

```sh
python3 app/experiments/f1-001/check_audit.py
```

The checker recalculates every selected, default, monthly and threshold score from saved CSV rows, checks labels and original split coverage against source data, repeats cutoff/winner selection, verifies the 24-hour purge and checks retained file identities. It exits with an error on a mismatch. The completed check returned `PASS` with zero mismatches across 42,798 prediction rows.

## Figures

[All test classification results](test-classification.svg), [monthly forecast error](monthly-forecast-error.svg), and [hourly forecast error](hourly-forecast-error.svg) use every method or time group. The classification figure uses dots on a labelled 94–100% axis; the CSV retains unrounded scores.

Rebuild tables and figures without training, using Matplotlib **3.11.2**:

```sh
python3 app/experiments/f1-001/make_figures.py
```

The generator verifies retained input and prediction hashes before plotting. It does not change the completed experiment.
