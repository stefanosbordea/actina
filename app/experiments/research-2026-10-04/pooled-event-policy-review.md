# A causal policy for pooled event counts

Experiment 013 found no conditional correction satisfying its daily expected-score safeguards. Its full saved-ledger diagnosis identifies precision as the immediate obstruction. The next useful question is whether expected false-positive savings earned on earlier issued days can support a later correction while preserving cumulative confusion-count dominance under both references.

One bounded experiment is justified: compare a forecast-only cumulative confusion ledger with the same policy restricted to daily confusion-count dominance. Use the unchanged conditional 64-path bank. This is a proposal, not an implemented or selected upgrade. No historical candidate was fitted or scored for this review.

## What the primary PDFs establish

**Koyejo et al., NIPS 2014.** Read PDF pages 3–5, especially Eqs. (1)–(4), Theorem 2/Eq. (5), and Algorithm 1. They express F-measures and precision as ratios of population confusion quantities. The classifier enters through true-positive mass and positive-call mass. Their two-step method estimates probabilities and selects a threshold on separate labeled data. It assumes a fixed data distribution and consistent probability estimation. This supports the distinction between a pooled confusion-count ratio and the average of daily score ratios. It does not establish calibration, causal forecasting validity or the proposed two-reference ledger. [Primary PDF](https://papers.neurips.cc/paper/5454-consistent-binary-classification-with-generalized-performance-metrics.pdf)

**Lipton, Elkan and Naryanaswamy, 2014.** Read PDF pages 7–9, Theorem 1/Eq. (2), Corollary 1 and §4.2. For calibrated probabilities the unconstrained F1-optimal threshold is half the optimal F1. That optimum depends on the other examples in the evaluated batch. Section 4.1 treats expected F1 with label dependence separately. These results do not permit inserting all future validation/test forecasts into an issuance-time optimizer. They also do not justify treating our empirical residual-bank frequencies as calibrated probabilities or replacing the two-reference safeguards with a fixed threshold. [Primary PDF](https://arxiv.org/pdf/1402.1892)

**Narasimhan, Kar and Jain, ICML 2015.** Read PDF pages 5–6, §5.1, Definition 6, Lemma 7 and Algorithms 2–3. A target level of a fractional-linear performance measure can be checked through a linear valuation. AMP alternates a valuation optimization and a performance update. STAMP is its stochastic version. Algorithm 3 receives labeled samples in both its model and challenge-level updates. Theorem 8 concerns the stated exact-optimization setting, not arbitrary delayed solar labels or two-reference safeguards. We can adopt additive confusion accounting without claiming to implement STAMP or inherit its convergence guarantee. [Primary PDF](https://proceedings.mlr.press/v37/narasimhana15.pdf)

**Yan et al., 2016.** Read PDF pages 2–3 and 7, Definition 1, Algorithm 2 and Theorem 3. OCMO maintains a running confusion matrix while updating a probability estimator and threshold. Its update explicitly receives the current labeled pair. Its regret statement depends on a consistent probability estimator and the stated distributional conditions. Copying that update during day-ahead issuance would use unavailable outcomes. The useful lesson here is the need to distinguish online supervised learning from a causal forecast-only decision ledger. [Primary PDF](https://arxiv.org/pdf/1610.07116v1)

Selected equation and algorithm pages were rendered and visually checked. The source receipt retains URLs, PDF hashes, page numbers, local copies and implementation hashes.

## Why an ordinary running precision guard is insufficient

A tempting rule compares cumulative expected P/R/F1 with cumulative raw NWP and assumes that choosing raw today remains feasible. That assumption is false when past actions are irreversible.

Consider identical marginals under both references. On day one there are two potentially positive hours with probabilities 3/4 and 7/8. Raw calls only the first, giving expected TP 3/4 and one call. Calling both gives TP 13/8 and two calls. Precision rises from 3/4 to 13/16, recall rises from 6/13 to 1, and the ratio-of-expected-counts F1 rises from 4/7 to 26/29.

On day two, raw calls twenty certain positive hours. Appending those same calls gives the policy precision 173/176, below the all-raw precision 83/84. Calling any smaller subset of those twenty cannot repair the deficit, and calling a zero-probability hour makes it worse. Thus even a previous prefix that passed all three pooled ratios can leave the next prefix with no feasible action. Future raw precision has risen. A valid runner cannot silently call raw and claim that its cumulative guard still passed.

This is a synthetic exact-arithmetic counterexample, not an observed Aktina result.

## Proposed accounting and its narrow guarantee

At issue time d, let p[r,d,h] be the fraction of the retained 64 scenarios exceeding 600 W/m² for reference r and hour h. Keep the two references separate. The raw bit is b[d,h]. A candidate bit is x[d,h].

For each reference accumulate forecast-only quantities across already issued horizons, using the probabilities available at each horizon's own issue:

- T[r] = sum(p[r,d,h] * x[d,h]), expected true-positive count.
- U[r] = sum((1 - p[r,d,h]) * x[d,h]), expected false-positive count.
- M[r] = sum(p[r,d,h]), total expected positive count.
- K = T[r] + U[r] = sum(x[d,h]), the positive-call count.

Maintain the corresponding T0[r], U0[r] and K0 for the all-raw policy. Never recompute previous ledger entries using a later forecast. No joint independence assumption is needed for these additive expectations. They are estimated expected counts, not observations or certified probabilities.

Require at every issued prefix, separately for both references:

    T[r] - T0[r] >= 0
    U0[r] - U[r] >= 0

These are cumulative expected TP gains and FP savings. For a current candidate, update the balances using only:

    delta_T[r] = sum(p[r,d,h] * (x[d,h] - b[d,h]))
    delta_U[r] = sum((1 - p[r,d,h]) * (x[d,h] - b[d,h]))

Raw today contributes zero to both differences, so it always preserves a previously feasible balance. This avoids the running-ratio infeasibility above without anticipating future outcomes.

With the same M[r] for the candidate and raw policies, nonnegative TP gains and FP savings imply nonregression of the following ratios whenever the required denominators are defined:

    precision = T / (T + U)
    recall = T / M
    F1 = 2*T / (T + U + M)

Each increases with T and decreases with U where relevant. This is a deterministic algebraic property of the ledger. It is not a claim that expected F1 equals F1 of expected counts. It is not a probability or realized-score guarantee. The count conditions are sufficient and can be more restrictive than pooled ratio nonregression.

## A correction that daily precision rejects but these balances allow

For both references, suppose day A replaces one raw call of probability 1/4 with an uncalled hour of probability 3/4. It earns 1/2 expected TP and saves 1/2 expected FP. On day B, raw has one certain positive call. Adding another hour with probability 1/2 lowers day B precision from 1 to 3/4, so a daily precision guard rejects it.

The accumulated balances permit the addition. Across the two days, the candidate has expected TP 9/4 and FP 3/4, compared with raw TP 5/4 and FP 3/4. Its expected-count precision is 3/4 rather than 5/8, recall is 9/10 rather than 1/2, and F1 is 9/11 rather than 5/9. The accumulated TP gain is one and FP savings are zero.

This hand example proves that the proposed feasible sets differ. It does not show that the current solar banks contain an opportunity to earn or spend such savings. Starting with zero balances is essential. No invented credit or retrospective initialization is allowed.

## One bounded experiment

Freeze two fixed arms before reading any new candidate outcomes:

1. **Cumulative balances.** Retain nonnegative cumulative TP gains and FP savings under each reference.
2. **Daily balances control.** Require the current day's delta_T >= 0 and delta_U <= 0 under each reference, without spending earlier savings.

Both arms use the same unchanged conditional bank, raw calls, source cutoffs, issue clocks, event threshold, candidate enumeration and objective. Both retain their own forecast-only cumulative confusion state. Their sole experimental distinction is whether prior TP gains and FP savings can support the current action. Do not add recency, threshold, decay, window, tolerance or initial-credit variants to this first test.

For the objective, compute each arm's cumulative ratio-of-expected-counts F1 after appending a candidate. Compare it with the F1 from appending raw today to that arm's same immutable prior history. Maximize the minimum improvement across the two references. This continuation comparison always has a zero-valued raw candidate and avoids mixing different past histories inside the current objective. The cumulative count guards still compare against the separate all-raw ledger.

Retain raw on zero primary gain. Resolve positive-gain ties by fewer changed raw bits, then fewer current calls, then the earlier selected-hour tuple. Undefined ratios remain undefined and cannot count as a passing gain. On an unassessable objective, retain raw with an explicit reason.

Enumerate the saved uncertain-hour subsets with exact integer/Fraction arithmetic. Re-prove the unanimous-hour reduction for this new objective and guards before relying on it. Include all unanimously positive hours and exclude unanimously negative hours only if the proof and exhaustive small-case fixtures hold. A zero-current-call action can be valid when the accumulated call count remains positive. Do not reuse 013's current-day zero-call restriction blindly. Stop on an unresolved reduction or arithmetic defect instead of hiding it behind a raw fallback.

Serialize the original 150 validation and 149 test horizons in issuance order. Reset balances to zero independently at the start of each period. Read only the current day's frozen scenarios and previously retained ledger state when choosing an action. Mutating any later forecast must leave all earlier decisions and ledgers unchanged. Reference labels, missingness and frozen 008/009 prediction outcomes remain unopened until both periods' decisions and states are hashed.

As in 013, the ledger covers the complete issued 24-hour horizons. Later evaluation uses the exact original 3,566/3,567 rows and unchanged 3,419/3,517 satellite-common masks. Consequently the ledger's algebraic dominance is limited to its full planning domain. It does not automatically survive boundary padding removal or an unavailable future satellite observation. Report this scope explicitly and retain both full-horizon and original-mask descriptive tables. Do not inspect future satellite availability to improve planning decisions.

Use the same original, persistence, raw NWP and frozen 008/009 comparisons. Keep 013's unchanged whole-period six-score admission rule and require independent identity, chronology, exact-balance and score reconstruction. Report every correction and negative result. Allow at most 30 minutes and two threads, with no model fitting or new dependencies. If it does not beat the stronger saved comparators on the required metrics, do not promote it.

## Difference from work already implemented

| Existing implementation | Actual mechanism | Difference in this proposal |
|---|---|---|
| 007 `threshold()` and `joint_scores()` | A scalar probability cutoff selected on labeled validation outcomes. The consensus training target averages reference events when both exist. | Separate reference marginals and causal cumulative confusion state, with no validation threshold search. |
| 008 `decide()` and `select()` | Separate add/remove probability cutoffs on a fixed grid, selected using pooled validation metrics. | Actions depend on carried expected-count balances and the current day, rather than fixed selected cutoffs. |
| 010 `best_pair()` and `apply_pair()` | At most one addition and removal per day, with exactly preserved daily call count and validation-selected margin. | Variable current call count and multiple changes, with savings carried between days. |
| 013 `coefficient_scores()` and `solve()` | Exact per-day mean-of-ratios scores from scenario hour/count dependence and daily safeguards. | Ratios of cumulative expected confusion counts and additive prefix safeguards. This changes the surrogate and its time aggregation explicitly. |

The code inspection confirms that none of these implementations maintains such a forecast-only cumulative TP/FP balance. The proposed mechanism is nevertheless an engineering adaptation of established confusion-matrix optimization, not a novelty or breakthrough claim. It remains vulnerable to poor scenario probabilities, reference disagreement, unverified source publication availability, seasonal shift and the already reused historical test.

The first implementation work should be the two analytical fixtures above, prefix causality tests, and an independent proof/review of the finite-action reduction. No new historical policy should be executed until those pass and the protocol is frozen.
