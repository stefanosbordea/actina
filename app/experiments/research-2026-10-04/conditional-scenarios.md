# Conditional historical solar scenarios

One justified next experiment is to select 64 historical error paths using similarity of cumulative forecast PV supply. Keep the existing physical optimizer and compare intact versus shuffled paths within each bank. This tests a plausible weakness in 011. It does not establish that this weakness caused its failure, or that the replacement will pass.

The [forecast-only diagnostic](../physical-011/review/forecast-regime-diagnostic.md) finds 44 of 150 validation horizons and 96 of 149 test horizons outside their frozen bank's range of forecast PV energy divided by 9,792 kWh load. All 61 June/July test horizons exceed the test-bank maximum. These are forecast comparisons across all planned horizons, not the smaller outcome-scoring subsets. No realized error or cost entered that diagnostic. The scalar ratio diagnoses coverage only and is not a second candidate to optimize.

**Primary methods actually read**

- [Schefzik, *A similarity-based implementation of the Schaake shuffle*](https://arxiv.org/pdf/1507.02079), PDF pp. 3–7, Eqs. (1)–(3), Scheme 1 and §2.2. The method chooses historical dates by a fixed forecast-similarity criterion at the same prediction horizon, then shares those dates across margins. Eq. (3) compares ensemble means and spreads. Scheme 1 first calibrates marginal distributions and then restores historical ranks. Our proposed transfer of whole residual paths adopts the conditional retrieval principle, not that full calibrated procedure. It is not a SimSchaake implementation or a calibration guarantee.
- [Zhou et al., *Decision-Focused Scenario Generation and Selection for Efficient and Robust Grid Dispatch*](https://arxiv.org/pdf/2607.05830), July 2026 preprint, PDF pp. 4–7, Eqs. (5)–(6) and (21)–(24). It differentiates downstream operating cost through scenario generation and selection. Eq. (22) defines selection probabilities, Eqs. (23) use a Gumbel–Softmax surrogate, and Eq. (24) mixes scenarios during training. Evaluation returns discrete samples. Our fixed physical distance does not learn from operating cost, so call it physically motivated conditioning, not decision-focused learning. The paper's two-stage Wasserstein formulation is also different from 011's fixed-plan, two-reference empirical CVaR objective.
- [Hu and Konstantinou, *Stochastic Power-Water Coordination*](https://arxiv.org/pdf/2601.07295), PDF pp. 5–7, Eqs. (43)–(57), Algorithm 1 and §III-D. Their uncertainty construction uses a copula and k-medoids reduction. Shared desalination commitment precedes scenario-specific operation. Their pump, salinity, flushing, network and import/export treatment exceeds 011's assumptions. This supports explicit power/water constraints and uncertainty-aware scheduling, not our particular retrieval distance or a transferable savings claim. No full plant-control claim follows from this experiment.

**One candidate to freeze before scoring**

For the existing 24 endpoint-indexed forecast hours, define

`P[d,h] = min(1700, 1.7 × max(NWP[d,h], 0))` kW

`F[d,h] = sum(P[d,0:h+1] × 1 hour) / 3.4` m³

`distance(k,d) = mean_h(abs(F[k,h] − F[d,h]))` m³.

The final component measures total potential PV-supported water. Earlier components distinguish equal-energy morning and afternoon patterns. Constant specific energy only rescales the distance, so the water unit adds interpretation rather than a new mathematical mechanism. This is not feasible production or inventory. It excludes demand, grid supply and tank/rate restrictions, which remain in the optimizer. Subtracting the same fixed cumulative demand from both curves would leave their distance unchanged.

1. Freeze all eligible historical days before each original 011 period's earliest issue, using its exact clock and paired-complete reference rule. No evaluation outcomes extend the pool. Use all eligible past days, not merely the existing 64. Otherwise choosing 64 would change nothing.
2. Rank by the single computed distance, with earliest source day breaking exact ties. Select 64 distinct days with equal weights. Stop if fewer than 64 exist. No learned weights, seasonal filter, near-tie tolerance or alternative descriptor search. Preserve candidate IDs, distances, exclusions and ranks.
3. Sort selected IDs chronologically before applying the unchanged 011 permutations. Use the same IDs for both reference families. Add each historical residual vector to the target raw forecast. Save unclipped radiation. Apply clipping only in the frozen PV conversion.
4. Keep four controls: existing recency/intact, recency/shuffled, conditional/intact and conditional/shuffled. Reproduce recency controls to detect implementation drift. Within each bank verify exact hourly marginals and equal expected hourly-sum cost for an identical fixed plan. Between banks, both residual marginals and dependence can change. That comparison cannot isolate dependence alone.
5. Keep 011's raw-point baseline, water service, tariff, solver, numerical action floor, CVaR90 objective and both period-specific gates unchanged. Freeze all 299 plans and bank selections before applying outcome masks. Retain the same 139 validation and 144 test common-reference daily scores, plus its weather sensitivity. Keep failed arms and all outcomes. Do not select a replacement from test results or revise the candidate after validation failure.

**Interpretation limits**

Cumulative L1 distance carries an early supply mismatch into later components. Opposite hourly differences can partly cancel after accumulation. This is a deliberate fixed hypothesis, not a demonstrated optimum. It ignores other weather variables, uncertainty magnitude and changing forecast-model versions. Similar forecasts need not have similar errors, especially when distant historical days supply the nearest matches. Report the 64th-neighbor distance, source ages and support limits without excluding difficult target days.

Historical forecasts must retain the same pinned model, variable, nominal lead and endpoint alignment. Publication and reference-availability times remain unverified. Strict past timestamps establish retrospective chronology, not deployable availability. Archived weather and SARAH3 remain two estimated references, not independent ground sensors.

The proposal follows already-inspected validation and test results. It is a mechanism-repair experiment, not independent confirmation. Analog retrieval, shared historical paths, cumulative physical descriptors and CVaR are prior methods. The narrow contribution would be a controlled comparison under the declared water-service constraints. Neither novelty nor general superiority is established by these papers or by preparing this protocol.
