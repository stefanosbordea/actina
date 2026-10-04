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
- 013: exact variable-count daily event decisions completed and independently audited through 3,721,230 checks. The four frozen arms enumerate 72,459 actions under separate reference safeguards. Both conditional arms retain raw ECMWF exactly. Both recency arms add two validation false alarms and leave test unchanged. All improvement gates fail. The fixed primary arm has exactly zero paired uncertainty intervals against raw because its decisions are identical. Forecast-only diagnosis finds raw is the sole feasible conditional action on all 299 days. Precision safeguards reject all ten days with a possible strict robust-objective gain.
- 014: the fixed event-to-water interface completed and independently passed 499,433 checks across 2,990 plans. All 299 raw controls reproduce exactly. Primary conditional plans equal raw throughout. Recency changes produce only numerical residue. No physical upgrade gate passes.

## Immediate team priority

Stefanos supplied the new validation file on `nwp-features` at commit `85097a560769ad8a1459ce55f0b3a4c301202405` on 4 October. Its unchanged predictions have now been evaluated on all 3,566 shared validation hours. [Results and reproduction](../handoff/v2-validation-2026-10-04/README.md).

V2 precision / recall / F1 are 91.289% / 85.621% / 88.364%. It improves all three against the original model, yesterday and the raw forecast supplied in its own CSV. That raw forecast scores 85.329% F1. The earlier pinned ECMWF day2 archive is a different input and scores 90.084%. V2 does not clear that stronger comparison. The saved validation-selected 008 correction scores 90.635% F1, with its selection caveat retained. These raw sources must not be conflated. The results and distinction were sent to Stefanos at 15:22.

The immediate next modelling decision belongs to Stefanos: reconcile his unpinned day1 input with the earlier pinned day2 comparison before interpreting his approximately 0.90 gate. His final-model run and test file were conditional on validation. Do not execute his training or silently substitute a forecast source. Evaluate any new supplied file with explicit identity and then support the scheduler comparison. Separate forecasting experiments remain secondary. No new alternative-policy implementation is running. The pooled-event review below is a proposal only.

## Next open mechanism question

013 removes the fixed-count restriction from 010 but still produces no useful correction. Its exact saved-ledger diagnostic identifies daily expected precision as the main obstruction. A [primary-paper review](research-2026-10-04/pooled-event-policy-review.md) proposes cumulative expected TP gains and FP savings, with a matched daily-balance control. Two exact synthetic examples distinguish this from unsafe running-ratio guards. No historical policy has been fitted or scored for that proposal. Experiment 014 completes the declared interface test and finds no physical upgrade. Any next policy requires its own frozen protocol and should follow the immediate v2 evaluation. The already-inspected periods remain exploratory.

Protect Stefanos's original `model/`, `data/` and `eval/`. Publish verified work on the authorized `stefanos-model` branch as Loukas Louka. Send Stefanos concise factual progress updates when authorized. Never report a failed comparison as an upgrade. No future-forecast automation or unattended-work claim substitutes for work running now.
