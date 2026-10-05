# Decision-preserving correction 005

Frozen before this computation. The mechanism is motivated by already inspected experiment 004: its raw residual analogue lowers continuous error but adds a false alarm against the stronger archived NWP control. This is standard constrained postprocessing, not a novel forecasting breakthrough or an independent prospective test. No fitting, tuning, selection, network request, new dependency or change to the competition pack occurs.

## One fixed rule

Let `q` be the saved archived day2 NWP point forecast and `a` the saved raw analogue point median, in W/m². For finite nonnegative inputs:

- If `q > 600`, the guarded point is `max(a, nextafter(600, +infinity))`.
- Otherwise, the guarded point is `min(a, 600)`.

Use Python binary64 `math.nextafter`. The positive floor is the next representable number above 600, not a fitted margin or arbitrary epsilon. Negative decisions include exactly 600. This projection is the closest feasible binary64 value to the saved analogue point in the NWP decision half-space.

The guarded event is its point **strictly greater than 600**. It must equal the NWP event for every original hour, independently of the reference. Consequently its confusion counts, precision, recall and F1 must equal NWP on any identical subset. It cannot improve those classification metrics against NWP by construction. Its possible value is a continuous-error improvement while retaining the stronger control's decisions. A wrong NWP decision remains wrong.

Raw analogue classification retains its saved scenario probability **strictly greater than 0.5**. Its median-threshold decision need not be identical when exactly 32 of 64 scenarios exceed 600. Count and retain both disagreements with NWP separately. Do not silently replace the raw analogue's decision rule. The guarded output is a point and binary decision, with no new probability forecast, interval-coverage or calibration claim. The 64 historical scenarios are not independent ground-truth observations.

## Fixed inputs and comparisons

Pin the unchanged experiment-004 report, original/persistence/NWP/raw-analogue prediction CSVs and raw-analogue scenario matrices for validation and test. Reconstruct the analogue median and probability from all 64 saved scenarios. Pin the existing SARAH3 full-reference CSV and reference-sensitivity membership files. Save input hashes before computation and verify them again afterward.

Preserve the exact ordered 3,566 validation and 3,567 test rows, feature times, target times and original weather-reference values. Verify all candidates have precisely these keys and targets. Convert target labels under the existing fixed UTC+03 convention to exact UTC valid timestamps. Join the retained satellite reference by those timestamps. Missing or null satellite values remain visible and unscored. No reference or forecast is imputed or selected away. Cross-check the prior sensitivity membership and retained forecast values.

Report all five methods: original, persistence, fixed NWP, raw analogue and guarded analogue. For each split, score (1) the full original weather reference, (2) the weather reference on the common available-satellite hours, and (3) the satellite reference on those identical common hours. Retain original denominator, missing-hour count, exact subset membership and all per-hour projected values.

Metrics are MAE and RMSE in W/m², signed mean error, TP/TN/FP/FN, precision, recall and F1. Undefined ratios remain null with denominator counts. Count every changed point, upward/downward projection, raw-median-versus-NWP event disagreement and raw-probability-versus-NWP disagreement, separately for full and common subsets. Report guarded-minus-NWP and guarded-minus-raw-analogue continuous-error differences, including zero or worse results. Report both counts and maximum absolute point adjustment.

No grid, threshold search, test-based revision, aggregate winner selection, significance or general-superiority claim. Results remain retrospective and conditioned on the known 600 W/m² rule. Archive publication vintage is unverified. Weather/model-derived and satellite references are different estimates, neither established local station truth. Radiation labels do not establish grid curtailment, feasible plant dispatch or measured savings.

## Execution and independent checks

Use Python standard library only. The runner refuses an existing output directory, retains an error receipt on failure and records actual command, input/code hashes, output hashes and exit status. No host measurement or training workload is started; process execution is single-threaded.

Before reporting success, verify the projection identity and idempotence for every hour, all guarded/NWP classification counts, every source membership and unchanged input hashes. Construct independent fixtures for values immediately below/at/above 600, exact probability 0.5 versus a positive scenario majority, projection in both directions, invalid/nonfinite inputs, duplicate/null reference handling and undefined metrics. An independent reviewer checks equations and retained results without fitting. Preserve any adverse error tradeoffs and the reason this experiment followed already observed results.
