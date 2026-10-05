# Reference sensitivity 001

Freeze this protocol and input identities before scoring. This is a reference-sensitivity audit of existing predictions, with no fitting, threshold search, method selection, forecast change or benchmark replacement. The original validation/test results have already been examined during development; this is not an untouched holdout. The satellite intake's coverage and five missing spans are already known.

## Fixed inputs

Use all saved **default** predictions from experiment 004 for `original`, `persistence`, `nwp_day2`, `median_bias`, `ridge_bias`, `global_residual`, `analogue_raw` and `analogue_solar`, separately for validation and test. Their owner confirmed these result files are final. Preserve the original 3,566 validation and 3,567 test origins, order, target times and weather-reference actuals. Record SHA256 values and sizes of every consumed input before scoring.

Use the pinned `satellite-reference-001/result/response.json`: requested `eumetsat_sarah3`, 34.7744°N/32.4229°E; returned grid 34.75°N/32.4°E; UTC hourly shortwave radiation over 13 September 2024–1 October 2026. Raw SHA256 `207b57c01a0a5cb6b8b71307b905e116d25c5f9ca845940898ae6628f516666c`. This is a satellite-derived reference, not ground-station truth. Do not download another reference or replace these bytes.

## Timestamp and prediction integrity

Join on 004's `target_epoch_utc` in `joined-inputs.csv`. Independently verify each saved target equals origin +24 hours, and that converting the saved naive target label with the empirically established **fixed UTC+03** offset yields that epoch. Do not infer seasonal DST using a timezone database. Both radiation sources represent the preceding-hour mean ending at that UTC timestamp.

Require every method to have exactly the original split's origins/targets in the same order. Cross-check origins, actuals and original/persistence values against the supplied `eval/cv_predictions.csv` and `eval/test_predictions.csv`. Reject duplicate/missing origins, missing target joins, absent satellite timestamps, changed actuals, nonfinite forecasts or invalid default decisions, even on hours where the satellite value is null. Never intersect away a missing forecast. Preserve negative original predictions; apply no new clipping.

Use the saved `point_w_m2` for MAE/RMSE, including scenario methods' existing median forecasts. Use saved `default_positive` for classification. Verify deterministic methods use point forecast strictly >600 W/m²; scenario defaults use saved probability strictly >0.5. Do not replace scenario event decisions with a threshold on their median or use `predicted_positive` selected thresholds. All reference event labels use actual radiation **strictly >600 W/m²**; equality is negative.

## Coverage and scoring

For each split, define one common available-reference subset solely by non-null satellite radiation. Every method uses exactly this same subset. Null satellite values remain unscored, never imputed. Report original total hours, available/scored hours and fraction, unscored count/fraction, and exact UTC spans of unscored target endpoints. Save membership and both reference values for every original hour, including nulls.

For every method, retain three explicitly separate bases:

1. Original weather reference on the complete original split, for continuity with 004.
2. Original weather reference on the common available-satellite subset.
3. Satellite reference on that **same** subset.

Each basis reports hours, TP/FP/FN/TN, precision, recall, F1, MAE and RMSE. A zero denominator produces null rather than an invented score. Compute confusion counts directly, and MAE/RMSE from the saved point predictions. Also report the 2×2 weather-versus-satellite event-label counts on the common subset to expose reference disagreement. This cross-tabulation is not a forecast-accuracy claim. Compare basis 2 with basis 3 when discussing a changed reference; basis 1 versus 2 isolates excluded-reference coverage. No winner, promotion gate, statistical significance or confidence interval is chosen in this audit.

## Interpretation and retention

Keep original weather-target outputs untouched. A precision change caused by different labels is not model improvement. Satellite retrieval, provider transformations, spatial support and possible shared inputs limit independence; neither reference is an independent local ground sensor. Archived feature issuance/publication availability remains unverified. Do not add satellite persistence: availability of target−24 satellite observations at decision time has not been established.

Use standard-library calculations; no network, model loading or training. Save the protocol/input hashes, checker identity, executed command and exit status, every split's original-hour membership, all metric bases and coverage. Refuse existing result directories and changed frozen input bytes. Test strict boundaries, default-versus-selected decisions, null preservation, source-change attribution and missing-prediction rejection on small fixtures. Parent review of this protocol precedes actual scoring.
