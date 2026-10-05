# Prospective evaluation 001

Prepared before reference retrieval. This evaluates the existing frozen capture and its two fixed analogue candidates. It does not fit, select, tune, promote or replace any model. No future reference is fetched during implementation or fixture tests.

## Frozen inputs and eligibility

Use only the primary and secondary target sets already frozen in `../capture-001/selected-targets.json` (SHA256 `7df57cce3cb4ab37b5700906aa507f1216aa186dfa7c1160ffb82f94f5843815`). Each contains 24 consecutive preceding-hour intervals. The three declared candidates are the captured raw forecast, `analogue_raw`, and `analogue_solar`. No persistence or original trained-model result is implied: their decision-time inputs were not independently captured.

The local UTC clock must be at least 48 hours after the last valid timestamp of the requested set:

| Set | Valid timestamps, inclusive, UTC | Earliest retrieval and scoring, UTC |
| --- | --- | --- |
| Primary | 2026-10-05 10:00 through 2026-10-06 09:00 | 2026-10-08 09:00 |
| Secondary | 2026-10-06 10:00 through 2026-10-07 09:00 | 2026-10-09 09:00 |

Evaluate one named set per invocation. An early invocation writes a refusal receipt and performs no network request or score. Production has no clock override. Unit fixtures may inject a clock into pure functions. Equality at the eligibility time is allowed. Eligibility does not establish provider availability or independent timestamp attestation.

Before retrieval, verify the capture receipt, selected-target identity, capture manifest, payload hashes and byte counts, raw response, full prediction CSV, and their mutual agreement. Verify the analogue protocol, input identities, output manifest and every declared output hash. Confirm its lock completed before the first selected interval began, its exact 48 keys, and the unchanged raw control. Do not trust claimed metrics or edited decision labels; derive event decisions from the frozen numbers.

After the adapter is complete, save a separate `input-lock.json` identifying these exact manifests and outputs, before any outcome retrieval. The evaluator checks that lock and all transitive manifest files; self-consistent edits to both a payload and its adjacent manifest must still fail against the lock. This local byte chain is not authenticated provenance. Keep frozen files unchanged. Read verified bytes once for evaluation rather than re-opening mutable prediction files after retrieval.

## Fixed reference request

The reference remains the one declared before forecast capture:

- Endpoint: `https://satellite-api.open-meteo.com/v1/archive`.
- Parameters: latitude `34.7744`, longitude `32.4229`, `models=eumetsat_sarah3`, `hourly=shortwave_radiation`, `timezone=GMT`, `timeformat=unixtime`.
- `start_date` and `end_date` are the UTC dates containing the requested set's first and last valid timestamps. Retain the full returned response; select no dates using values.
- Require UTC seconds and radiation units `W/m²`. Validate finite numeric values (excluding booleans), nonnegative radiation, integer whole-hour timestamps, equal array lengths, and unique timestamp keys. Preserve nulls as unknown. No interpolation, nearest-hour join, timezone shift, alternative model, automatic retry or fallback reference.

Match exact UTC valid timestamps, comparing the same preceding-hour means. SARAH3 is a satellite-derived reference, not station truth. Its spatial grid, satellite processing and hourly averaging differ from both live forecasts and the historical model/reanalysis training targets. Official [Satellite Radiation API documentation](https://open-meteo.com/en/docs/satellite-radiation-api) describes backward hourly means and a publication delay; the fixed waiting rule does not guarantee availability.

## Missingness and scoring

Always export all 24 expected rows, with their interval start/end, observed capture lead, each frozen candidate, reference value and status. Distinguish an absent reference timestamp from a present null. Preserve malformed or duplicate response bytes and fail the reference assessment rather than choosing one duplicate. Unknown forecasts remain unknown, never zero or false.

Report these independently:

1. **Complete-set assessment:** valid only when all 24 expected references and all three candidates' required fields are present and valid. Otherwise status is incomplete or invalid and no complete-set metrics are supplied.
2. **Common-hour diagnostic:** if the reference is structurally valid but contains absent/null values, use only the explicitly listed intersection of valid reference and all three candidates' required prediction fields. Report its exact keys, excluded keys/reasons, count and fraction of the original 24. It is a descriptive subset, never a completed original-set result. There are no candidate-specific subsets. An empty intersection yields null metrics with an explanation.

For the raw control, the required fields are point radiation and its derived 0/1 event probability; intervals are not applicable. For each analogue they are point radiation, probability and both interval bounds. Bounds must be nonnegative and ordered; probabilities lie in [0,1]. A null source radiation requires unknown candidate fields. Partial/inconsistent candidate nulls or missing/duplicated candidate rows are integrity failures, not opportunities to shrink the comparison.

The reference event is radiation **strictly greater than 600 W/m²**; the raw decision follows the same rule. Analogue decisions use probability **strictly greater than 0.5**. Exactly 600 and exactly 0.5 are negative. No decision is re-derived from an analogue's point median.

On each allowed scope, report all three candidates' MAE, RMSE and signed mean error in W/m²; TP, TN, FP, FN; precision, recall and F1; and Brier score. Precision with no predicted positives, recall with no positive references, and F1 with zero denominator are null with their denominator counts, not silently zero. Raw Brier uses its hard 0/1 prediction and is labelled accordingly. For analogues also report inclusive empirical 90% interval coverage and mean width in W/m²; raw intervals remain not applicable. Preserve units, sample counts, and every fixed candidate even if weaker. No ranking, best-method selection, significance claim, threshold search or model promotion occurs.

## Execution evidence and tests

Refuse an existing output directory. Keep the exact request, raw HTTP response (including error responses), response headers/status, local request start/end UTC, monotonic elapsed time, protocol/script/input hashes and a final receipt. Persist each failed or incomplete attempt. A subsequent explicitly requested attempt uses a new directory; it never overwrites or silently retries the first. No HTTP request is made if the time gate or input integrity checks fail.

Fixture tests use constructed local responses only. They cover early refusal with a network spy, the exact eligibility boundary, payload and manifest corruption, strict 600/0.5 boundaries, UTC joins, duplicate timestamps, missing timestamps, null reference and null forecast values, invalid units/numbers, complete versus common-hour counts, undefined classification ratios, and output non-overwrite. Expected confusion counts and scalar errors are hand-derived independently of the implementation.

Two 24-hour sets describe these captured forecasts only. They cannot establish seasonal robustness, broad model superiority, measured curtailment recovery, plant feasibility, field savings or competition success. Frozen forecasts and this evaluation remain research evidence, separate from operational decisions.
