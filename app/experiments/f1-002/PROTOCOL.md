# AktinaBench feature and precision experiment 002

Frozen before fitting. This is a bounded retrospective follow-up to experiment 001, whose original test results have already been inspected. It cannot establish independent future generalization. It changes no original model, data, evaluation file, schedule or current UI result.

## Data and timing

Reuse experiment 001's input loader, classification metric function and original membership from `eval/cv_predictions.csv` and `eval/test_predictions.csv`. An input row at origin t predicts radiation at t+24 hours; truth is strictly actual >600 W/m². No evaluation rows or negative/night hours are dropped. Report every target calendar month.

Input identities: `data/features.csv`, `data/paphos_weather_data.csv`, both original prediction CSVs, and experiment 001's `run.py`. Check unique, increasing hourly indices; original actual/baseline alignment; and finite features. Actual archive availability timestamps are absent. Using values timestamped at or before the origin is a retrospective availability convention, not proof they were available then.

For validation, fit only origins before its first origin whose target is strictly earlier than that origin. For test, refit on all eligible pre-test origins under the same 24-hour purge. All three new fits use the same complete-feature training indices at each stage and the same earliest eligible origin. A lag warmup may remove training origins only; any missing evaluation feature fails the experiment rather than moving membership. Record all training boundaries and row counts.

## Fixed candidates and feature contribution

Controls: unchanged persistence (current-origin radiation) at cutoff 600, and retained original-model predictions at cutoff 600. The retained original model has a different historical training procedure and is not the matched retraining control.

New matched models, all LightGBM L1 regression with 300 trees, learning rate .05, 15 leaves, minimum 40 samples per leaf, seed 17, two worker threads, no early stopping, sampling or automatic reweighting:

1. `absolute_l1`: predict target radiation from the existing seven input columns.
2. `residual_base`: predict target minus current-origin radiation from those same seven columns.
3. `residual_history`: the same residual with 18 additional features: radiation and cloud-cover lags 1, 3, 6, 12 hours (8); trailing 6- and 24-hour means of those two fields, including the origin (4); current minus 24-hour-prior radiation and cloud cover (2); sine/cosine of target hour/24 and (target day-of-year−1)/365.25 (4). Thus the fitted input counts are 7, 7 and 25. No target weather or realised future cloud cover is used.

Absolute forecasts are max(0, raw prediction). Residual forecasts are max(0, origin radiation + alpha × predicted residual). Alpha is selected from exactly [0, .25, .5, .75, 1]. Alpha zero deliberately exposes when a selected improvement is only persistence threshold calibration, not learned feature value. No additional candidate, parameter or feature search is permitted after scoring.

## Validation selection, frozen before test scoring

For all new methods search cutoff [500,510,…,700] W/m² with strict score > cutoff. Search all five alphas for each residual method; the absolute model has alpha 1 only. Retain every combination, including failures. Also report each model's fixed-default alpha 1/cutoff 600 outcome, MAE and RMSE, so threshold selection cannot obscure the feature ablation.

A combination qualifies only when validation precision ≥ fixed-persistence validation precision AND validation recall ≥ retained-original validation recall. Undefined precision/recall cannot qualify. Compare rational count products for the gate to avoid floating-point boundary decisions. Within each model choose the qualifying combination with greatest F1, then precision, then recall, then cutoff nearest 600, then smaller alpha, then smaller cutoff. If that model has no qualifier, report its fixed-default configuration explicitly as unqualified; it is not recommended.

The global recommendation compares all qualifying new-model choices and fixed persistence if it meets the same gate. Rank by F1, precision, recall; remaining ties prefer persistence, then absolute_l1, residual_base, residual_history. If nothing qualifies, use unchanged persistence at 600 as the explicit fallback, even if it misses the recall gate. Save the recommendation and every per-model selected/default configuration before fitting or predicting test data. Neither test scores nor test months may change this choice.

## Outputs and independent checks

Save raw predictions and selected/default scores for all five methods on both complete splits, validation grids, full/monthly classification counts and precision/recall/F1, and full/monthly MAE/RMSE. Retain fixed-default outcomes as well as selected outcomes. The matched residual_base versus residual_history results measure this fixed feature bundle's contribution, not the importance of each feature in isolation.

Save fitted models, input/protocol/code hashes, package/runtime versions, training membership identities, the frozen validation decision, execution log and comparison CSV. Preserve failures instead of overwriting them. A separate stdlib checker must recompute counts, regression errors, monthly coverage, timestamp/label/baseline equality, strict thresholds, validation gates/ranking, train purges and all expected hours from saved CSVs. Recheck original input hashes at completion. No model fitting in that checker.

This is forecast evaluation only. Radiation is not measured curtailment; classification gains do not establish useful schedule changes, recovered solar energy, plant permission, customer savings or an all-metric improvement. Report every loss and all months. Future chronological evidence is still needed after development.
