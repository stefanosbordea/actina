# Experiment 013: variable-count reference-specific event decisions

Status: implementation and independent analytical preflight are complete. The input manifest freezes this protocol and executable sources before the forecast-only complexity receipt and the authorized historical run. No historical decision or outcome scoring has run at this freeze. The original proposal remains unchanged in the research directory. This hypothesis follows already-inspected 006–012 outcomes and is exploratory.

## One hypothesis and four fixed arms

Use retained daily scenarios to optimize event calls across all 24 hours, allowing the number of calls to change. All four arms use exactly the same reference-specific expected precision, recall and F1 safeguards relative to raw ECMWF. They differ only in bank and objective:

| Bank | Worst-reference F1 uplift | Mean-reference F1 uplift |
|---|---|---|
| 012 conditional 64 | Primary: conditional robust GFM | Conditional pooled GFM |
| Original recency 64 | Recency robust GFM | Recency pooled GFM |

“Pooled” describes the arithmetic mean of two expected F1 uplifts. It never averages radiation, binary reference labels or their denominators. Equal safeguards make the objective comparison interpretable. An unconstrained pooled arm would change both the objective and safeguards and is excluded from this bounded test. No arm is selected after observing new outcomes. Raw ECMWF remains a candidate within every arm and the primary external control.

## Immutable issue inputs and scenarios

Read the already hashed 012 pre-scoring artifacts, without rerunning retrieval or changing scenario values. For each period use `result/{period}/scenario-replay.npz`, member `unclipped_ghi`, with axes horizon, bank, family, reference, scenario, hour. Banks are recency then conditional. Use only family zero, the intact paths. References are weather then satellite, with 64 scenarios and 24 endpoint hours. Use `plans.npz` for raw forecast, target positions and horizon identity, `bank.npz` for source IDs, and retained metadata for source clocks.

Require each consumed file to match 012's planning freeze and output hashes. Pin those manifests, 012 protocol and inputs, exact source files needed for joins, existing reference membership and the frozen 008/009 controls. Reject missing members, nonfinite values, duplicate target identities or inconsistent dimensions. Load numeric/Unicode arrays with pickle disabled. Verify the raw forecast, selected source IDs and target endpoints against their pinned records.

An event is exactly `unclipped_ghi > 600` W/m². Do not use the clipped PV arrays, round values, average references or create an artificial clear-sky bound. Preserve negative scenario values as supplied. They simply do not exceed the positive event threshold.

Retain all 299 horizons, 150 validation and 149 test, before outcome masks. The common issue remains D−1 00:00 fixed UTC+03, for endpoints D00–D23, leads 24–47 hours. These represent intervals from D−1 23:00 to D23:00. Source pools stay frozen at the original earliest issue cutoffs, 2025-12-04 for validation and 2026-05-02 for test. Do not update the bank with within-period outcomes. Historical publication availability remains unverified.

## Exact empirical quantities

For one horizon let `b[i] = raw_forecast[i] > 600`, `K0 = sum(b)` and `y[r,s,i] = scenario[r,s,i] > 600`. Let `S[r,s] = sum_i y[r,s,i]`. Each scenario has weight 1/64 within its own reference. Define the following as exact rational numbers from integer counts:

- `p[r,i] = sum_s y[r,s,i] / 64`.
- For candidate count K > 0, `a[r,i,K] = sum_s 2*y[r,s,i]/(S[r,s]+K) / 64`.
- If `nplus[r] = count_s(S[r,s] > 0)` is positive, `c[r,i] = sum_{s:S>0} y[r,s,i]/S[r,s] / nplus[r]`.

For a 24-bit action x with K selected hours, expected precision is `sum_i p[r,i]*x[i] / K`, expected F1 is `sum_i a[r,i,K]*x[i]`, and expected recall is `sum_i c[r,i]*x[i]`. Recall here is conditional on a nonempty scenario truth set. Preserve `nplus` and the empty-scenario fraction explicitly. Do not replace this mean of ratios with a ratio of expected counts.

Compute the raw action's expected scores using the same bank, reference and conventions. Precision is undefined when K0=0, so omit that reference's precision constraint only in that case. If no scenario has positive truth, recall is undefined and its constraint is omitted. Undefined quantities remain null in outputs, never zero, one or a passing observed score.

Empty action and empty truth have F1=1, matching the cited GFM definition. Thus the K=0 action's expected F1 equals the reference's empty-scenario probability. K=0 is admissible only if raw K0=0. When K0>0, do not compare a zero-call candidate with raw precision. This restriction is explicit and limits complete removal of raw calls. For K0=0 the zero vector is the raw candidate, and positive-count candidates remain possible if they satisfy the applicable recall and F1 constraints.

## Exact enumeration and the dominance reduction

Read-only inspection of saved scenario event labels, without consulting realized evaluation outcomes or scoring candidate actions, found at most 7 uncertain hours for validation recency, 8 for validation conditional, 9 for test recency and 8 for test conditional. Enumerating their subsets requires 72,459 subsets across all 299 horizons and two banks. Both objectives reuse the same feasible subset scores, so four arms do not double this subset count. Report any extra noncanonical raw candidates separately. These are forecast-scenario complexity diagnostics, not results or a new scenario selection rule. Retain the reproducing diagnostic and its source hashes before execution.

An hour is unanimously positive only if every scenario under both references is positive. It is unanimously negative only if every scenario under both references is negative. Every other hour is uncertain, including disagreement that is certain within each reference. Canonical candidates include all unanimously positive hours, exclude all unanimously negative hours and enumerate every subset of uncertain hours. Also retain the unmodified raw action as a candidate even when it is not canonical. Do not use a probability cutoff to narrow the uncertain set.

The reduction preserves an optimum for each primary objective under the expected-score safeguards. Adding an omitted unanimous positive increases TP, K and every scenario's recall. It increases F1 and does not reduce defined precision. Such a positive hour also rules out an empty truth set. Removing a selected unanimous negative leaves TP and recall unchanged and weakly improves precision and F1 whenever the remaining count is positive. When K=0 is permitted, that final removal gives empty-action F1 equal to one on empty truth and zero otherwise, again no lower than a zero-TP positive action.

There is one count-restriction exception. If raw K0>0, deleting the last unanimous-negative call cannot leave the prohibited zero action. Such a candidate previously had no possible TP, hence zero F1, precision and defined recall under both references. If a unanimous-positive or uncertain hour exists, selecting that potentially positive hour gives an admissible positive-count action that weakly dominates it. Further unanimous positives can then be added. If no potentially positive hour exists, all allowed positive-count actions have F1 zero, and the retained raw action is optimal. Test this case explicitly. Never justify the reduction by silently allowing K=0 when K0>0.

All coefficient construction, score comparisons, safeguards and objective comparisons use exact integer arithmetic and `Fraction`. Floats may be emitted only as display values alongside exact numerator/denominator pairs. For every enumerated action with admissible K, recompute expected P/R/F1 for each reference and require every applicable quantity to be at least its raw counterpart. No numerical tolerance is permitted. Preserve infeasible candidates and their exact failed constraints in the ledger.

For robust arms maximize the minimum of the two expected F1 uplifts against raw. For pooled arms maximize their arithmetic mean with exactly the same safeguards. Rank feasible canonical candidates plus raw by the arm's exact objective, then fewer changed raw bits, then smaller K, then lexicographically smaller selected-hour tuple. There is no secondary mean or minimum objective ahead of the change-count tie. Apply an action only when its primary objective has a strict exact gain over raw. Otherwise raw wins its zero-change tie. Report that conservative choice explicitly.

This reduction also preserves the stated full lexicographic optimum. If robust uplift is strictly positive, each reference has positive expected TP. Removing a unanimous-negative call then strictly improves both expected F1 values and their minimum uplift. For strictly positive pooled uplift, at least one reference has positive expected TP, so removing that call strictly improves the mean. Adding a unanimous-positive hour strictly improves either objective. A strict-gain optimum therefore contains every unanimous positive and no unanimous negative. When maximum uplift is zero, the feasible raw vector wins the zero-change tie, including the sole-negative and all-empty exceptions. The saved scenarios remain estimated inputs, so an exact empirical optimum is not a population Bayes-optimality or observed-score guarantee.

A second direct scenario-score calculation must verify the selected vector and each applicable safeguard using exact fractions, independent of the coefficient path used to rank candidates. A disagreement, malformed scenario, inadmissible count or hash change stops the run as a defect. There is no optimizer tolerance, MILP gap or approximate feasibility fallback. Raw remains the explicit no-gain fallback, not a way to conceal an incomplete calculation.

Serialize horizons. Use only installed standard-library Python and NumPy for the saved arrays, with at most two process threads and no fitting. Predeclare a 30-minute total runtime budget. If it is exhausted, save a nonzero incomplete receipt and every completed ledger, without scoring an incomplete candidate set or calling it an experiment result. Do not expand the budget based on scores. Expected runtime is seconds to several minutes for 72,459 small subset records, but this is an estimate. Save actual elapsed time, CPU time, macOS peak RSS in bytes and the executed exit status.

## Freeze decisions before outcomes

Generate all four arms for both periods and hash complete 24-hour call vectors, exact metric fractions, source IDs, coefficients and subset ledgers before loading scoring references or their availability masks. Plans depend only on the frozen scenarios and raw forecasts. Copy all padded decisions into the retained output even when the hour is not in the original period.

The planning manifest must not rely on regenerated scenarios or corrected reference values. There is no validation threshold selection and no validation-to-test policy choice. All four policies are fixed here. Report validation and test separately and keep every negative arm.

## Same-hour evaluation and admission

Score the original 3,566 validation and 3,567 test hours. Use the unchanged weather-full mask and the unchanged satellite-common masks, 3,419 validation and 3,517 test hours. Weather-common is an additional matched-mask sensitivity. Do not substitute the complete-day water-study masks. Join every method by exact target identity, verify the expected row set, and retain missing satellite values rather than manufacturing labels.

Report TP, FP, FN, TN, positive-call counts, exact precision/recall/F1, additions/removals, changed daily counts and missing rows. Preserve all per-hour decisions and daily realized metric distributions. Undefined observed scores remain null and make the corresponding admission comparison unassessable. No new Brier or calibration claim is appropriate for the final optimized bits. The empirical scenario marginals, if displayed, are identified as such and are not action probabilities.

The primary conditional robust arm passes the retrospective raw-control gate only if all six pooled P/R/F1 values are no worse than raw ECMWF on both references in each period, with at least one strict improvement in each period, and a complete verified enumeration. Report six strict gains separately from mixed gains and equalities. Apply the same gate descriptively to the three fixed controls, without selecting a replacement winner.

Also report the exact frozen selected 008 consensus-two-source and 009 joint-BQN decisions on identical rows, plus original and persistence. Keep their selected thresholds untouched. Those methods use the original later rolling-origin information and are context benchmarks, not matched common-issue controls. A raw-control pass does not establish all-axis superiority if any of these stronger saved comparators wins a required metric. List every such regression rather than renaming it a tradeoff-free upgrade.

Within each bank, robust versus pooled compares the objective under identical safeguards. Within each objective, conditional versus recency compares the retained bank. The intact paths are fixed here, so this experiment does not newly isolate temporal dependence. No automatic product, scheduler, water-plan or competition-pack replacement follows.

## Required analytical tests and independent audit

Before historical solves, test:

1. Strict 600 equality and the next binary64 value above it. No threshold rounding.
2. Exact expected P/R/F1 against direct enumeration, including zero-call, all-empty and mixed-empty scenario sets. Recall conditioning and null precision must be distinguishable.
3. Full 2^m exhaustive actions on small analytical cases against the unanimous-hour reduction for both objectives. Include changed optimal count, reference conflict, sole-negative removal with K0>0 and no possible positives.
4. Identical per-hour marginals with different hour/count dependence, confirming that F1 coefficients can change.
5. An infinitesimal rational safeguard violation rejected without a float tolerance, plus malformed inputs, runtime interruption and a known feasible raw candidate.
6. Exact tie ranking, repeated identical enumeration, strict-primary-gain/raw fallback and invariance to a shared permutation of complete scenario IDs.
7. The deterministic two-day aggregation counterexample in the companion review. Daily nonregression must not be mislabeled pooled nonregression.
8. Full source hash refusal, duplicate/missing target refusal, exact original mask membership, boundary padding retention and source cutoff compliance.

An independent checker must reconstruct binary scenarios and all exact selected expected scores without importing production enumeration or coefficient helpers, recalculate all observed counts from pinned references, check all join/mask identities and verify immutable source hashes. On tractable synthetic cases it must exhaust all actions. Preserve failures and actual executed commands. Exact rational safeguard checks establish only what was true of these empirical scenarios, not statistical or physical guarantees.

## Prior art and limits

This is a constrained two-reference adaptation of [Waegeman et al., JMLR 2014, Theorem 8 and Algorithm 1](https://www.jmlr.org/papers/volume15/waegeman14a/waegeman14a.pdf) and [Dembczyński et al., ICML 2013, §§3–5](https://proceedings.mlr.press/v28/dembczynski13.pdf). The accompanying [review](../research-2026-10-04/variable-count-event-review.md) distinguishes the adopted equations from our engineering choices and from a four-state classifier alternative.

The 64 paths are an empirical conditional distribution with unverified calibration. Optimizing its daily expected F1 does not guarantee period-level F1, precision or recall on realized references. Reference disagreement remains visible. Repeated use of this historical test prevents a fresh-holdout claim. Event decisions alone establish no curtailment recovery, plant safety, water service, dispatch, cost or energy improvement. Novelty and general superiority remain unestablished.
