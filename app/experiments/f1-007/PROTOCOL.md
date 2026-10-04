# Joint-reference event target 007

This protocol fixes the label weighting and analysis before reading the historical satellite training join or fitting. The hypothesis follows the already-inspected 006 reference reversal. This is a bounded retrospective experiment, not an independent confirmation, novel learning algorithm, physical-curtailment detector or claim of universal superiority. The application, scheduler and competition pack remain unchanged.

## Fixed inputs and target

Use the exact 006 feature matrix, feature/target timestamps and its strict purged training memberships. Keep all 3,566 original validation hours and 3,567 original test hours. Pin those inputs, the original controls, 006 predictions, and the existing SARAH3 reference bytes before fitting. The satellite source already covers the earlier training period; no new reference product or target-period substitution is allowed. Use the existing fixed UTC+03 mapping to target UTC, with exact timestamp joins and duplicate rejection. Missing satellite values stay missing; missing timestamp membership is an error.

For each eligible training row, W = 1[weather radiation > 600 W/m²]. If SARAH3 radiation exists, S = 1[SARAH3 radiation > 600 W/m²] and y = (W + S) / 2. Otherwise y = W. Thus y belongs to {0, 0.5, 1}; the equal reference weights are fixed, not tuned. Each row has unit training weight regardless of source count. Save weather event, nullable satellite event, missingness, source count and soft label. This is a conditional reference-consensus target, not latent physical truth. Disagreement does not identify which reference is correct. The two sources are not assumed independent or equally accurate.

Training targets must be strictly earlier than the first evaluation origin for each split, exactly as in 006. The test refit may use earlier validation-period labels only when they meet that same time rule. No satellite value enters the feature matrix. Existing residual features remain weather-reference history strictly preceding each rolling origin; no source rewrite, imputation, scaling, future interpolation or feature addition is allowed. Availability by timestamp does not establish real-time publication availability.

## Fixed models

Use installed LightGBM with objective `cross_entropy` through its regression API, which accepts probability labels in [0,1]. Do not use a classification wrapper that discretizes the 0.5 targets. Six fits maximum: three configurations per split, with the same feature order and eligible rows as 006.

All configurations: seed 17, deterministic column-wise mode, two threads, learning rate 0.03, L2 penalty 2, unit row weights. No early stopping, class weighting, oversampling or calibration.

1. small: 200 trees, 5 leaves, maximum depth 3, minimum child samples 80.
2. medium: 300 trees, 9 leaves, maximum depth 4, minimum child samples 60.
3. larger: 300 trees, 15 leaves, maximum depth 4, minimum child samples 40.

These match 006 capacity. Apply the identical joint-reference validation gate and ranking below to the saved 006 validation probability vectors as well, then freeze their revised control cutoffs separately before new test scoring. This compares weather-only and mixed-target heads under the same selection policy without extra fits. Preserve the original 006 selection untouched, retain its prior cutoffs and common default 0.5 as separate diagnostics. The new heads use cross_entropy rather than the binary-only wrapper; do not claim numerical equivalence of separately fitted trees.

## Validation-only selection

For each joint-reference model, enumerate every unique validation probability plus 0 and 1. The event call is strictly probability > cutoff. A cutoff qualifies only if precision, recall and F1 each meet the raw day2 NWP values on BOTH weather-full validation and satellite-common validation (six comparisons). Undefined metrics never qualify. Satellite-common uses all and only original validation rows with available satellite reference.

Use exact confusion-count fractions for gates and ranking. Rank eligible thresholds by: minimum F1 across the two references; mean F1; minimum precision; minimum recall; closeness of cutoff to 0.5; then larger cutoff. If a model has no eligible cutoff, retain its best threshold under the same order for diagnostic reporting, marked unqualified. Among qualified models use the same first four metric criteria, then prefer the earlier/smaller configuration. If none qualifies, choose unchanged NWP. Apply this exact rule separately to the saved 006 weather-only family and the new joint-reference family; freeze each family's selected head or NWP fallback and cutoffs. Save every threshold, failed candidate, model configuration, input/code identities, selection and recommendation before any new test prediction or scoring.

## Fixed test and reporting

Evaluate all three new fits once using their frozen validation cutoffs; do not select on test. Compare original, persistence, raw day2 NWP, all three fixed 006 candidates under the new joint gate and all three joint-reference candidates. Retain default 0.5 and original 006-cutoff metrics separately. Score weather-full, weather-common and satellite-common for BOTH periods, preserving all missing-reference rows and denominators. Report TP/TN/FP/FN, precision, recall, F1 and Brier scores against each reference separately. NWP/original/persistence Brier scores use hard 0/1 outputs, not supplied calibrated probabilities. The new head estimates the mixed training target; its output is not established as a calibrated probability for either reference or actual curtailment. No W/m² point estimate or MAE is invented.

The selected joint-reference candidate passes the retrospective test gate only if all six P/R/F1 comparisons meet NWP on weather-full and satellite-common, with at least one strict gain. Always retain failed test candidates and all adverse reference results. A pass still gives no deployment or live-superiority recommendation: this test was already inspected and the hypothesis was chosen afterward. No tuning, further model family or favorable-reference selection after results.

Save the exact feature identity, training-label rows, fitted model text, all predictions, validation grid and selection, reference memberships, metrics, execution command/exit and input/output hashes. Refuse overwrite and verify inputs after the run. Use installed dependencies only. Independent review reconstructs labels, temporal membership, thresholds, counts and model prediction replay without refitting.

API basis: https://lightgbm.readthedocs.io/en/stable/Parameters.html#objective documents `cross_entropy` for labels in [0,1].
