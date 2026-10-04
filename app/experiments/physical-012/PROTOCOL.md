# Conditional forecast-path retrieval 012

Protocol frozen before the first historical 012 retrieval, solve or score, following analytical fixtures and independent review. This mechanism is proposed after inspecting 011 and its forecast-only coverage diagnostic. It is an exploratory next hypothesis, not independent confirmation, a calibrated forecasting model or a novelty claim.

## Hypothesis and one fixed descriptor

011 transferred errors from the latest 64 complete historical days without conditioning on the current forecast. Its forecast-only diagnostic found 44 of 150 validation horizons and 96 of 149 test horizons outside their bank's modeled total-supply range. This does not prove an error-law change or explain the outcome differences. Test one physical forecast-path descriptor, without feature, weight, neighbor-count or seed search.

For each raw archived ECMWFday2 forecast, compute hourly illustrative power exactly as in 011:

`P[h] = min(1700, 1.7 × max(GHI[h], 0))`, in kW.

Compute `F[h] = (P[0] + ... + P[h]) / 3.4`, in m³ across the declared one-hour intervals. This is cumulative potential PV-supported water, not feasible production, inventory, recovered curtailment or a clear-sky index. The vector reflects both supply magnitude and timing relevant to cumulative tank constraints. Constant SEC only rescales this distance. Subtracting the same cumulative demand from both vectors leaves their mathematical distance unchanged.

Use one distance: `d(history, target) = sum_h abs(F_history[h] − F_target[h]) / 24`. All computations are float64. Accumulate the 24 power values left to right in endpoint-hour order, divide each prefix by 3.4, then accumulate the 24 absolute differences left to right and divide by 24. Do not center, standardize, normalize total supply, learn weights or apply a near-tie tolerance. This geometry implicitly carries an early mismatch through later prefixes. Opposing hourly differences can cancel in a prefix. Those are declared limitations, not tuned away after scoring.

Select the 64 eligible historical days with smallest computed distance. Break exact computed-distance ties by earliest historical endpoint day. Save every eligible distance and rank. After selecting the set, order its 64 days chronologically before constructing residual trajectories or applying the frozen shuffle. The scalar supply/load ratio from the diagnostic is not an additional selection feature.

## Eligibility and issue information

Use all paired-complete historical endpoint days from the original source dataset, not just the old 64. Every source day needs 24 unique hourly endpoints, finite raw NWP and both historical reference values, with every endpoint strictly before the original 011 period cutoff. Validation cutoff remains 2025-12-04 00:00 fixed UTC+03. Test cutoff remains 2026-05-02 00:00 fixed UTC+03. Do not advance the cutoff during either evaluation period. Historical reference availability only establishes eligibility within this fixed past pool. Evaluation reference values, missingness, residuals or costs never select a day.

Target descriptor and historical descriptor both use their raw archived NWP, never realized weather, satellite values, corrected forecasts, candidate production or future information. Preserve original source target positions and all candidate-pool exclusions. The issue clock and nominal NWP times are identical to 011. Historical publication availability remains unverified. Do not call timestamp compliance proof of live availability.

All 299 endpoint-day horizons remain. Each horizon covers D−1 23:00 through D23:00, with endpoints D00–D23 and issue D−1 00:00 on fixed UTC+03. This is not a midnight-to-midnight physical day. Boundary padding is planned before masks.

## Fixed two-by-two comparison

Retain four candidate policies with no selection among them after outcomes:

| Historical set | Intact paths | Same-marginal shuffled paths |
|---|---|---|
| Original frozen recency64 | Reproduce 011 coherent | Reproduce 011 shuffled |
| New forecast-conditioned64 | Conditional coherent | Conditional shuffled |

Residual definitions remain reference minus corresponding historical raw NWP. Both references share the same selected source dates. Add each residual path to the target raw NWP, then apply the unchanged PV conversion. Selected dates are canonically chronological. Use exactly the original 011 per-stage 24×64 permutations, shared across the two reference families, and reuse them for every target horizon. Save selected IDs, canonical positions, residuals, unclipped scenarios and permutations.

Within each bank, intact and shuffled families must have exactly identical sorted hourly values. Every fixed schedule must have the same expected hourly-sum cost under either family within the existing numerical tolerance. Daily-regret tails can differ. Comparing historical sets measures the combined distribution change from conditioning. Comparing intact versus shuffled within the same set isolates temporal arrangement while preserving that set's marginals. Neither establishes calibration or field causality.

Before new outcome scoring, reconstruct the original recency banks and re-solve their two policies for every horizon using the pinned 011 optimizer and archived raw-point anchor. Require maximum hourly reproduction error at most the original 1e-6 m³ audit tolerance, and record exact equality and all maximum float differences. A larger mismatch stops new scoring and must be resolved or documented as an implementation failure, not absorbed into a candidate gain. Copy the unchanged archived raw solar-aware q0 and tariff-led app plan as controls and verify their source forecasts, target positions and water constraints. No new parameter or baseline objective.

## Unchanged physical and numerical model

Import the pinned 011 optimizer without modifying it. Demand 120 m³/h, production 0–500 m³/h, tank 4,000 m³, reserve 800 m³, initial/final 2,000 m³ and SEC 3.4 kWh/m³ remain fixed. All schedules target 2,880 m³ water and 9,792 kWh total plant energy. Unlimited grid backup, no export revenue, fixed endpoint-hour prices and omitted plant physics remain as documented in 011.

Each conditional policy minimizes the same maximum of the two reference-specific empirical daily grid-cost-regret CVaR90 values against the identical raw-point q0. Recompute q0's cost on each actual candidate scenario, including each shuffled trajectory. Free eta and worst-reference objective, nonnegative exceedance and grid variables, fractional tail weights, deterministic tie rules, €1e-5 action floor, primary/L1 caps and numerical audits are unchanged. No fitting, calibration, new metric, loss, coefficient, optimizer or scenario-count search.

## Fixed scoring and admission

Generate and hash all old-control and new conditional schedules before applying any evaluation outcome mask or calculating realized metrics. Primary scoring uses exactly the original 011 complete original-period horizons with all 24 satellite values. Preserve 139 validation and 144 test horizons and both references. Weather-only sensitivity retains 148 complete horizons per period. All exclusions and partial boundary plans remain explicit.

Report the same daily cost, grid energy, regret distributions, means, CVaR90, extrema, worse/equal/better counts, numerical water residuals and total plant energy as 011. Retain both same-path conditioning comparisons and both within-bank dependence comparisons. Apply the original risk-only gate and the distinct eight-axis aggregate gate relative to raw q0 in both periods. Also report the same gates relative to each candidate's matched 011 path-policy control. Improvement relative to a weaker control must not conceal regression against raw q0. An overall no-tradeoff recommendation would need the frozen primary regret-risk and eight-axis conditions in both periods, with identical water feasibility. Preserve negative, zero and mixed results. No candidate selection or product replacement follows automatically.

## Evidence and preflight

Before execution freeze this protocol, source inputs, descriptor/selection code and the exact existing optimizer hash. Retain prior 011 artifacts unchanged. Required fixtures include identical forecasts at zero distance, equal-energy early/late supply with nonzero distance, PV clipping, explicit cumulative order, exact distance ties, chronological reordering before shuffle, strictly-past paired-complete eligibility, fewer-than-64 rejection and unchanged marginal/expected-cost checks. Reproduce all source joins and source-time bounds. Save the 64th-neighbor distance, selected source ages and forecast support for every horizon, without excluding difficult target days. Serialize solves, use the existing dependencies and at most two CPU threads.

The unchanged optimizer SHA256 is `4931d0c86dcd296b0c43e88a8418766b8ba1491677ba89beb7e7301bdb0a78db`. The primary-paper note SHA256 is `302f27c70b4961d79396b91aed0e83d73b1161bad5f37758166ccf3d707f3ba5`. `inputs.json` pins the complete source set, original comparison artifacts, protocol, code and fixtures before execution. The actual commands, exits and resource use are recorded separately. No prepared command is counted as a completed run.

## Primary sources and limits

The accompanying [academic review](../research-2026-10-04/conditional-scenarios.md) records the full PDFs read and the adopted and excluded mechanisms.

- [Schefzik, A similarity-based implementation of the Schaake shuffle](https://arxiv.org/pdf/1507.02079), PDF pp. 3–7, Eqs. (1)–(3), Scheme 1 and §2.2, supports fixed forecast-similarity retrieval at the same prediction horizon and shared historical dates. Its full procedure calibrates margins before restoring dependence. This experiment transfers residual paths and is conditional residual sampling, not full SimSchaake or a calibration guarantee.
- [Zhou et al., Decision-Focused Scenario Generation and Selection for Efficient and Robust Grid Dispatch](https://arxiv.org/pdf/2607.05830), July 2026 preprint, PDF pp. 4–7, Eqs. (5)–(6) and (21)–(24), learns scenario generation and selection through downstream operating cost. Our fixed descriptor does not learn from cost and is not decision-focused learning. Its two-stage Wasserstein formulation differs from our fixed-plan, two-reference CVaR objective.
- [Hu and Konstantinou, Stochastic Power-Water Coordination](https://arxiv.org/pdf/2601.07295), PDF pp. 5–7, Eqs. (43)–(57), Algorithm 1 and §III-D, combines water constraints with copula scenarios and k-medoids reduction. Its salinity, pump, flushing, network and recourse treatment exceeds our model. It does not validate this descriptor or a transferable plant-savings claim.

No paper is claimed to validate the cumulative-water metric, its 64 neighbors or this site's results. Similar forecasts need not have similar errors. The descriptor ignores other weather variables, uncertainty magnitude and changing forecast versions. Archived weather and SARAH3 are estimated references, not independent ground sensors. Temporal dependence, analogue retrieval and CVaR are prior methods. This controlled adaptation does not establish novelty or general superiority.
