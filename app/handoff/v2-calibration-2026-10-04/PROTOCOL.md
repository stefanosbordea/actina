# V2 event-threshold calibration

Prepared on 2026-10-04. Code and inputs are fixed before the validation threshold scan. Execution awaits root release. No scan has run at this freeze. This is validation tuning of supplied predictions, not a blinded validation experiment. The initial v2 validation metrics were already reviewed.

Use only the retained incoming validation CSV from Stefanos's nwp-features model v2. Feature-hour labels shift exactly 24 hours to the target. Require complete identical target sets and unchanged actual and persistence values against retained original validation. Verify the saved f1-008 classifier truth and bits on the same targets. Do not read or score any test file.

The truth event stays actual > 600 W/m². Candidate calls use v2 predicted radiation > threshold. Evaluate every integer threshold from 500 through 650 W/m², inclusive, in steps of 1. Rank by exact rational F1 from integer confusion counts. Resolve exact F1 ties by the smallest distance from 600, then by the higher threshold. Fail if every F1 is undefined. Undefined precision or recall remains null.

Save all 151 thresholds, TP, FP, FN, TN, precision, recall, F1, exact F1 and unchanged MAE in validation-table.csv. Save the selected threshold and original 600 threshold in validation-selection.json. Preserve source hashes, the protocol hash, exact executed command and run times. Refuse existing outputs and fail if any frozen input or source hash changes.

Compare the selected validation F1 against the already selected f1-008 consensus_two_source saved event calls. Reproduce its exact validation F1 of 542/598, approximately 0.9063545150501672. This is prior research with a validation-selected policy, not a classifier retrained for the new v2 model. Report the difference without selecting a different 008 arm.

The applied event threshold is validation-selected. No model is trained. Radiation predictions and their MAE, RMSE and bias stay unchanged. This procedure does not change the demo or make a final team selection. The selection rule in Stefanos's deleted message is not applied. Test-file access requires a separate root release after the selection is reviewed.

Synthetic checks cover the strict 600 boundary, all 151 grid endpoints, exact F1 ranking, nearest-600 and higher-threshold tie conventions, and undefined or unpaired input. They do not load the validation CSV.

Frozen files:

```json
{
  "app/handoff/v2-calibration-2026-10-04/threshold.py": "f3191bfbee54fc903c7650140b9fde8670de5b512ddff39b9b06e62e0b95c42c",
  "app/handoff/v2-calibration-2026-10-04/test_threshold.py": "0ea74657173afc4c7f29b7266be0ad2c7082eb028bd7253fbf4d816cdeecf7f2",
  "app/tools/benchmark_predictions.py": "2c9a0069582233d9fa8b1a9ea800bc0ad02b5839a041aca6ff76faeef0bf0bfd",
  "app/tools/compare_prediction_versions.py": "68e2d4114c8cb542deb4521d382416090ccbee582dc56f94b5768db653351139",
  "app/handoff/v2-validation-2026-10-04/inputs/cv_predictions_v2.csv": "71de995691fd6cc4feda1eb5ee9da9002551c8144cbc04a7376a5e8790809982",
  "eval/cv_predictions.csv": "1b4d9a3b95169c52be39551fcbd1d37df6db0a40beb9986462d87b1644d75d69",
  "app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv": "7a7394433f707371ce6ce7f8ae7b0db1d8119b2805a4d9676386aaf7e2804b66",
  "app/experiments/f1-008/result/validation-selection.json": "2e09ea387909cf3c26b145e61089b6142351cda4c1a8ffa7a0f01ff021525c6c"
}
```
