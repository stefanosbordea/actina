# Stefanos model v2 validation

Evaluate the supplied `cv_predictions_v2.csv` first. No test CSV or model execution is needed. MAE does not determine precision, recall or F1.

The supplied schema is `time,actual,predicted,baseline,forecast`. An unnamed first index column is accepted. `forecast` is the supplied raw forecast and `baseline` is yesterday's observation. A four-column file without `forecast` is also accepted.

Stefanos's labels identify the feature hour. The evaluated target is exactly 24 hours later. Preserve the naive source clock without a timezone conversion. If a future export already labels the target hour, declare `--incoming-time-basis target`. Incorrectly declared clocks can produce zero overlap or mismatched observations. Never shift a file to improve its score.

From the repository root, replace `/absolute/path/cv_predictions_v2.csv` with the retained incoming file. Use a new output filename for every run.

```sh
python app/tools/compare_prediction_versions.py \
  --incoming /absolute/path/cv_predictions_v2.csv \
  --reference eval/cv_predictions.csv \
  --model-id 'Stefanos nwp-features model v2 validation' \
  --incoming-time-basis feature \
  --reference-time-basis feature \
  --raw-control app/experiments/f1-004/result/predictions/validation-nwp_day2.csv \
  --classifier app/experiments/f1-008/result/predictions/validation-consensus_two_source.csv \
  --classifier-policy app/experiments/f1-008/result/validation-selection.json \
  --output app/handoff/stefanos-v2-validation-001.json
```

The retained original is `eval/cv_predictions.csv`. The classifier comparator is the previously selected **f1-008 consensus_two_source** event correction. Its saved policy retains raw positives above probability 0.50 and adds raw negatives above 0.60. Both comparisons are strict. This policy was selected using validation, so its validation score is not an untouched estimate. No other arm is selected after seeing v2.

The report contains:

- Original input byte hashes and explicit model identity
- Every incoming hour scored against supplied actual values
- Incoming, original, persistence, supplied raw, retained raw and saved classifier scored on exactly the same shared target hours
- Missing and extra target identities, plus any supplied raw values that differ from the retained raw control
- Precision, recall and F1, with confusion counts and `null` for undefined denominators
- MAE, RMSE and bias for radiation forecasts. Saved classifier bits have event scores only

An event is radiation **strictly greater than 600 W/m²**. Exactly 600 is negative. The existing benchmark parser and metric calculation are reused unchanged. The wrapper additionally rejects surplus CSV fields, conflicting actual or persistence values on shared targets, invalid saved classifier calls and changed retained control truth. Input files must contain consecutive, unique hourly rows with finite nonnegative values. Shorter or shifted periods are allowed, but missing and extra hours remain visible.

Compare models through the `matched` section. Partial overlap cannot establish superiority over the full original period. The `incoming_full_period` section is separate because values outside retained shared hours have not been independently verified. If overlap is zero, matched scores are `null` and no comparison is assessable.

The tool does not fit, tune, select a new classifier or alter model, data or evaluation files. Output creation is exclusive. Prediction CSVs cannot establish training cutoffs, forecast issuance or absence of leakage. Keep those facts with the model handoff. Reused validation is not fresh holdout evidence. Radiation events are not observed curtailment or water savings.

**ActinaBench format version 2 is unrelated to Stefanos model v2.** The explicit model identifier and incoming file hash identify this handoff.

Run the focused checks with:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s app/tools -p test_compare_prediction_versions.py -v
```
