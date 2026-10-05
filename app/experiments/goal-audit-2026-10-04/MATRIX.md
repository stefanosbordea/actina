# Research goal completion audit

**The goal is not complete.** Two scientific requirements remain: demonstrate the useful reference-specific correction mechanism, then carry that same accepted forecasting change through the water-service comparison.

This audit ran 42,777 checks and reconstructed the event metrics from hourly decisions, original labels and controls. It performed no training, new experiment or product edit. [Execution](execution-001.json) · [Evidence](evidence.json) · [Exact counts and fractions](event-metrics.csv) · [Full matrix](MATRIX.json)

| Requirement | Finding |
|---|---|
| Primary academic research | Met. Full-paper methods and equations are linked to the implemented BQN, residual scenarios and water optimization. Adopted methods and local hypotheses are distinguished. |
| Reproducible implementation | Met. Protocols, inputs, models, hourly decisions, outcomes and failed attempts remain available. |
| Same-hour precision, recall and F1 | Met against the predeclared controls. Frozen 009 improves all 36 point comparisons across both periods, both required references and original, persistence and ECMWF day-2 controls. |
| Useful distinct correction mechanism | Unmet. 009 is a published-method adaptation. The separate-reference mechanism in 010 selects no change. The physical regret mechanisms fail their validation regret gates. |
| Matched ablations | Met. Source, label/objective and decision-rule comparisons exist. The 012 two-by-two comparison exactly reproduces all 598 prior recency plans. Negative results remain. |
| Independent replay and uncertainty | Met with limits. The 009 precision and F1 difference intervals cross zero. The 011 strict all-axis bootstrap frequencies are numerically unstable and unsuitable for interpretation. Its interval reconstruction passes. |
| Equal-service downstream test | Partly met. All 1,794 plans satisfy the declared numerical water constraints. Those plans use raw NWP and residual scenarios, not the accepted 009 forecasts. The required single forecast-to-water chain remains untested. |
| Protected originals | Met. `model/`, `data/` and `eval/` are unchanged from original commit `2a093aba`. |
| Equal deck attribution | Met in the current local deck and pack. Actual slide XML uses identical formatting for all four names, and creator metadata lists all four. This does not cover historical LaTeX credit. |
| Published verified work | Research and product are published. Remote `stefanos-model` matches `cb71a520`, its CI passed, and 156 public responses match the current site. Corrected deck metadata and the refreshed pack await the parent commit at this snapshot. |

The 009 gain must be credited. Its test weather counts are TP 994, FP 15 and FN 16, versus archived ECMWF's 993, 15 and 17. Satellite-common counts are 951, 42 and 24, versus 950, 42 and 25. Every original hour remains. The test was already inspected during development.

ECMWF has the highest test F1 among the fixed archived controls in 008: ECMWF, GFS and their arithmetic mean. It does not dominate every forecast on every metric. GFS has higher recall with lower precision, and the raw arithmetic mean has higher satellite-validation F1. This audit names the predeclared comparator and does not invent a best-per-metric oracle gate. MAE tradeoffs and uncertain intervals are limitations, not newly imposed completion criteria.

The strongest next step is one frozen **variable-count correction rule** with separate reference consequences, removing 010's fixed-count restriction. Use a common issuance, a matched averaging control and a declared connection to the scheduler before execution. Binary event calls cannot silently substitute for PV energy. Evaluate that same correction in both the event and equal-water-service comparisons, retaining every regression and equality. The conditional joint-count route is under review and has not been implemented or scored by this audit.

[Current publication and delivery evidence](publication-followup.json) · [Actual deck XML evidence](deck-evidence.json)
