# Aktina research goal

Active direction reaffirmed by Loukas on 4 October 2026, for the 6 October competition. The objective is an original, useful contribution to forecasting and solar-to-water decisions. Reproducing a paper is a comparison method, not the objective itself.

## Concrete objective

Develop a correction mechanism that decides when a strong physical forecast should be changed despite conflicting reference estimates. Test whether separating the expected consequences under each reference succeeds where averaging their targets failed. Connect any accepted forecast change to desalination decisions under identical plant and water-service constraints.

The first hypothesis is **reference-specific correction regret**. Predict the effect of an action relative to the existing forecast separately for each reference, rather than treating their average as latent truth. Distinguish additions from removals. Disagreement should remain visible and affect whether the correction is permitted. The mechanism and its comparison must be fixed before the next experiment is scored.

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
- 010: common-issuance paired corrections with separate reference heads. Implementation and measurement are in progress. The prior-art review identifies the proposed application contribution and its limits.

Protect Stefanos's original `model/`, `data/` and `eval/`. Publish verified work on the authorized `stefanos-model` branch as Loukas Louka. Send Stefanos concise factual progress updates when authorized. Never report a failed comparison as an upgrade. No future-forecast automation or unattended-work claim substitutes for work running now.
