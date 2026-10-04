# Aktina research goal

Active direction reaffirmed by Loukas on 4 October 2026, for the 6 October competition. The objective is an original, useful contribution to forecasting and solar-to-water decisions. Reproducing a paper is a comparison method, not the objective itself.

## Concrete objective

Develop a correction mechanism that decides when a strong physical forecast should be changed despite conflicting reference estimates. Test whether separating the expected consequences under each reference succeeds where averaging their targets failed. Connect any accepted forecast change to desalination decisions under identical plant and water-service constraints.

The initial hypothesis was **reference-specific correction regret**, tested in 010 through paired event changes and then through physical schedules in 011–012. Estimate each reference's consequences separately rather than treating their average as latent truth. Disagreement remains visible and affects whether a correction is permitted. Any next mechanism and its comparison must be fixed before scoring.

Selective prediction, ensemble disagreement, noisy-label learning and safe policy improvement are established fields. A prior-art review must identify what the proposed mechanism changes. Until that review and experiments establish otherwise, call it an Aktina research hypothesis, not a new theorem or a scientific breakthrough.

## Evidence required

1. A reproducible implementation, exact inputs, saved models, per-hour outcomes and a retained record of every failed candidate.
2. Same-hour precision, recall and F1 comparisons against Stefanos's original model, persistence and the strongest archived-weather control, under both weather-full and satellite-common references. No regression in any of the six primary comparisons. Equality is identified separately.
3. A matched ablation separating new information, objective and decision rule. The already-inspected test remains exploratory. Any subsequent independent evaluation is labelled according to what actually occurred.
4. Independent reconstruction, model replay and appropriate uncertainty analysis. No sensor-truth, source-independence, calibrated-confidence or live-availability claim without the required evidence.
5. A downstream scheduling test with explicit physical assumptions, equal water service and no plant-constraint violations. A higher proxy F1 alone is not evidence of useful stored water or recovered curtailment.

## Current work

- 007: joint-reference soft targets. Recall/F1 gains, precision regressions. Rejected.
- 008: GFS plus separate correction thresholds. Five of six metrics improve, weather precision regresses. Rejected.
- 009: published Bernstein quantile network adaptation, independently audited. All six event point scores improve slightly against raw NWP. Numerical-error and 008 tradeoffs prevent an overall upgrade claim.
- 010: common-issuance paired corrections with separate reference heads. Completed and independently audited. Both arms retain the raw forecast, with no improvement. The fixed daily call count prevents this mechanism from repairing most validation misses.
- 011: daily solar-to-water scheduling completed and independently audited across 1,196 plans. Shuffled scenarios improve all eight aggregate cost and grid-energy measures in both periods. Both candidates fail the validation requirement for daily cost regret. Intact historical trajectories do not establish an advantage. Perfect-information lower bounds and exploratory uncertainty checks are retained separately. No operating savings or product replacement is claimed.
- 012: forecast-conditioned historical paths completed and independently audited. All 598 recency schedules reproduce exactly. Both conditional arms improve all eight aggregate cost/grid measures in both periods, while both fail validation daily-regret CVaR. Intact conditional paths reduce cost on all 144 primary test days under both references, with mean daily changes of −€7.389 and −€9.439. Validation regret tails remain +€0.408 and +€0.528, and some test days use more grid energy. No overall replacement or novelty claim. The audit verifies 714,332 assertions across 1,794 plans, 153,616 distances and 3,674,112 scenario values.

## Next open mechanism question

Can information available at issuance identify when a change to the raw plan is likely to increase cost, without losing the observed aggregate benefits? Conditioning the historical bank improves its forecast-regime match but does not solve the validation regret failures. A new rule must distinguish predicted risk from realized outcomes, retain both references and fixed water service, and use a declared comparison against raw-point and the existing conditional controls. No follow-up mechanism is implemented, running or scored. The next protocol must be frozen before its comparisons, and the already-inspected periods remain exploratory.

Protect Stefanos's original `model/`, `data/` and `eval/`. Publish verified work on the authorized `stefanos-model` branch as Loukas Louka. Send Stefanos concise factual progress updates when authorized. Never report a failed comparison as an upgrade. No future-forecast automation or unattended-work claim substitutes for work running now.
