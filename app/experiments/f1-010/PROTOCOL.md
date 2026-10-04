# Common-issuance paired exchange 010

Freeze before fitting or scoring. Hypothesis: exchange at most one positive/negative hour per target day, retaining the raw forecast's daily positive count, and require both independently trained reference heads to favor that exchange. Compare the worst-reference rule with an arithmetic-mean rule using the same heads. Constrained ranking and pair exchanges are prior-art mechanisms; this application hypothesis has no established novelty or guaranteed gain. The prior test has already been inspected.

## Issuance and features

Keep the exact 17,832 original targets, fixed UTC+03 clock and source 008 feature rows. Every target calendar day is forecast at 00:00 on the preceding day. Thus endpoint leads are 24–47 hours; preceding-hour radiation intervals start 23–46 hours after issue. All 743 complete source target days must have exactly 24 unique hourly targets.

Overwrite the four contemporaneous weather fields using the raw weather row at issue−1h, renamed issue_temperature_2m, issue_shortwave_radiation, issue_relative_humidity_2m, issue_cloud_cover. Replace radiation_yesterday with issue_radiation_lag24 from raw weather at issue−24h. Replace hour with lead_hours and month with issue_month. Replace all five residual/history columns with the saved008 values at feature_time=issue, renamed with issue_ prefix. Those values use target observations strictly before issue; independently reconstruct their provenance and retain the latest contributing target or null when none exists. Do not retain target−24h state for hours 1–23.

Target geometry, target calendar and ECMWF/GFS day2 inputs remain per target, including cloud missingness. Their nominal reference time is target−48h, hence at most issue−1h. Save original origin, target, issue, each source family's timestamp and maximum source time. These inequalities are timestamp evidence only; historical forecast publication and observation availability are unverified. Raw weather and satellite are retrospective reference estimates, not established live observations.

Use exactly 27 clearly named features. No fit-time scaling, extra feature, data selection or interpolation. Preserve missing history/cloud. For each evaluation period, train only on targets strictly before its earliest common issue, not before its later first original rolling origin. Satellite-head training additionally excludes missing satellite labels; keep those excluded rows in the label ledger with their reason.

## Four fixed fits

Use LightGBM binary cross-entropy, larger configuration from006/008: 300 trees, 15 leaves, depth4, minimum child samples40, learning rate0.03, L2=2, seed17, deterministic column-wise mode, two threads. Fit a weather-event head and a satellite-event head independently for each period, four fits total. Reference event is strictly radiation>600 W/m². No mixed target, extra weighting, early stopping, calibration or parameter search. No changes after test results.

## Full-day pair policy

For every full 24-hour target day, let raw ECMWF define the positive calls. Every candidate pair removes one raw positive hour r and adds one raw negative hour a. The primary score is min(pW[a]−pW[r], pS[a]−pS[r]); the matched ablation score is their arithmetic mean. Rank pairs by greatest score, then earliest added target, then earliest removed target. Each margin m in the fixed grid {0,.05,.10,.20,.30,.50} acts only when the best score is strictly greater than m. At most one pair acts; no available pair means no swap. Explicit no-swap is always an option.

Generate the entire24-hour predictions/policies before applying the original validation/test or satellite score masks. Evaluation spans all target days touching the original period, with padding outside the original period preserved. Missing satellite outcomes never select hours or pairs. Save every best pair, both score components, margin, action and original/satellite mask membership afterward, including cross-mask swaps.

Select validation margins separately for the primary min and ablation mean arms. Admission requires no regression of precision/recall/F1 on both weather-full and satellite-common original validation hours, with at least one strict gain. Undefined metrics cannot qualify. Use exact count fractions: maximize minimum F1 across references, mean F1, minimum precision, minimum recall, then fewer full-day swaps (including padding), then larger margin. If no margin qualifies with a strict gain, retain no-swap. Freeze both chosen margins before new test prediction/scoring. Never choose between arms after test.

## Evaluation and interpretation

Compare original, persistence and raw ECMWF on the same original 3,566 validation and3,567 test hours. Their original supplied rolling predictions have different issuance/horizons; disclose this, do not present them as identical-information controls. Raw ECMWF day2 fields have the declared nominal timing but unverified publication time. Retain frozen008 selected policy as context only, also with different issuance. Score weather-full and weather/satellite common subsets on identical available-reference rows. Preserve all padding, missing outcomes and denominator changes.

On a full matched day, a swap preserves the number of positive calls K. For a fixed truth set with P positive outcomes, ΔFP=−ΔTP and ΔFN=−ΔTP, so P/R/F1 move together when defined. This is a structural identity, not a promise that ΔTP is positive. It need not hold after partial-day or missing-reference masks. Explicitly check and retain full-day counts and masked-subset counts; do not infer the identity for masked comparisons.

Save both heads' raw Brier scores against both references; a swap policy has no invented calibrated probability. Retain all margins, failures, changes and metrics. Each arm's test gate is all six P/R/F1 nonregressing with at least one strict gain; report all six strictly improved separately. No physical plant, water-volume, dispatch-cost, realized-surplus or live superiority claim follows from event-hour count preservation.

Before fits, test count preservation, strict margin, deterministic pair ties, min-versus-mean conflict and chronology/source replacement. Freeze hashes of code, sources and protocol. Preserve all executions, stdout/exits, fitted models, issued features, training membership, all full-day predictions/pair ledgers and selection before test. No original model/data/eval files or product/delivery edits, no new dependency/network fetch, no GPU. Independent replay and reconstruction must precede conclusions.
