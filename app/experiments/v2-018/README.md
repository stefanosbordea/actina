# 018 result

The four past-error features did not establish a useful improvement and did not beat 008. They added one true positive and one false positive relative to the matched control. The base radiation curve and product model were unchanged.

| Method | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frozen 008 | 271 | 21 | 35 | 3,239 | 92.81% | 88.56% | 90.64% |
| Four past-error features | 275 | 27 | 31 | 3,233 | 91.06% | 89.87% | 90.46% |
| Matched 017 control | 274 | 26 | 32 | 3,234 | 91.33% | 89.54% | 90.43% |
| Supplied v2 at 600 | 262 | 25 | 44 | 3,235 | 91.29% | 85.62% | 88.36% |
| Supplied v2 at 562 | 287 | 51 | 19 | 3,209 | 84.91% | 93.79% | 89.13% |

Both arms fail the requirement of strictly higher F1 than 008 without additional false positives. All 3,566 original validation hours are retained. This repeatedly inspected historical period is not a fresh holdout.

The new arm uses the average forecast error and average absolute error over the preceding 14 days for the v2 forecast and ECMWF forecast. Each feature uses observation targets in `[origin−336hours, origin)`. A forecast error cannot be used until its observed target is strictly earlier than the current prediction origin. The underlying v2 prediction history is the frozen 016 chronological OOF sequence followed by its fixed validation curve. No base model is retrained.

This experiment evaluates sequential use of observations. Head weights and thresholds were frozen first. The validation observation stream was then read to construct strictly past context for each origin. All resulting decisions were frozen before full validation scoring. It would be incorrect to describe this as keeping every validation observation sealed until all predictions were complete.

Training v2 history has 336 hours at every origin. Early ECMWF windows contain 45–336 hours, with 291 partial windows. Validation v2 history contains 312–336 hours, with 359 partial windows caused by the 24-hour gap between the retained OOF and validation forecast sequences. ECMWF validation windows are complete. There are no empty windows or dropped decision hours. Counts and latest included targets are retained as diagnostics, not model features.

The control reproduces 017's forward probabilities, selected threshold 0.530 and all validation probabilities/calls. The added-context head chose 0.525 from the training-only grid under the same 63-FP training constraint. Neither threshold was changed after validation scoring.

Evidence:

- [Protocol](PROTOCOL.md), [44-file source/input lock](lock.json) and [source capture](inputs/manifest.json).
- [Four passing causality checks](preflight-tests-001.log), including future-outcome mutation and exact window boundaries.
- [Execution receipt](execution-001.json) and [complete log](execution-001.log), exit 0 with 14.75 seconds external wall time.
- [Head freeze](result/head-freeze.json), [decision freeze](result/decision-freeze.json), all intermediate/final model files and [output hashes](result/completion.json).
- [Training contexts](result/training-context.csv), [validation contexts](result/validation-context.csv), and their separate coverage ledgers.
- [Exact metrics](result/summary.json), [all validation calls](result/validation-evaluation.csv) and [descriptive paired-day intervals](result/day-bootstrap.json).

The radiation MAE remains 18.7007 W/m² for the reused 016 refit curve. The supplied original v2 curve remains a separate 18.6973 W/m² reference. Event correction did not improve the radiation regression.

Reproduction from the repository root, using the saved dependency versions and an unused output directory:

```sh
python3 -m unittest discover -s app/experiments/v2-018 -p test_run.py -v
python3 app/experiments/v2-018/run.py --out replay-001
```

The reproduction command has not been rerun. No original test outcomes, demo defaults or team messages were changed.
