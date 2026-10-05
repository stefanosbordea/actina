# AktinaBench

Evaluate every retained prediction against the same actual values and the same definition: radiation **strictly above 600 W/m²** is a positive hour.

| Retained period | Method | MAE, W/m² | Precision | Recall | F1 | False alarms | Missed positive hours |
|---|---|---:|---:|---:|---:|---:|---:|
| Validation | LightGBM | 29.3375 | 0.8142 | 0.7876 | 0.8007 | 55 | 65 |
| Validation | Yesterday | 32.4694 | 0.7974 | 0.7974 | 0.7974 | 62 | 62 |
| Test | LightGBM | 14.2658 | 0.9757 | 0.9554 | 0.9655 | 24 | 45 |
| Test | Yesterday | 12.2593 | 0.9801 | 0.9752 | 0.9777 | 20 | 25 |

The current model loses all three classification measures on the test period. Validation was used for early stopping; its gain is not independent evidence that the model wins on unseen periods. The validation and test files evaluate different fitted models.

All 3,566 validation rows and 3,567 test rows are included. Target timestamps are file timestamps plus 24 hours. Validation covers 5 December 2025 19:00 through 3 May 2026 08:00; test starts the next hour and ends 28 September 2026 23:00. Partial boundary days stay in aggregate and monthly scores. Daily diagnostic rankings include only complete days and do not replace the full comparison.

[Full results](actinabench-v1.json) include every day, every month, original file hashes, MAE, RMSE, bias, precision, recall, F1 and confusion counts. Test days with the largest increase in model error include 8 May, 7 May and 18 May. These are investigation targets, not an alternative benchmark.

A timing review also found that the original adjacent training splits do not purge the 24-hour prediction horizon. This requires a purged retraining experiment. Removing boundary rows alone does not make the validation selection independent.

[Experiment 001](../experiments/f1-001/PROTOCOL.md) freezes a comparison of direct classification, causal weather history and a compact deep neural network. Original files are preserved. Its test results will be retrospective because this test period has already been examined.

Reproduce the retained-file benchmark from the repository root:

```sh
python3 app/tools/benchmark_predictions.py --output app/build/actinabench-new.json
python3 -m unittest discover -s app/tools -p 'test_*.py' -v
```

The command refuses to overwrite an existing report. F1 measures detection of the defined radiation threshold; it does not prove curtailment recovery or financial benefit.
