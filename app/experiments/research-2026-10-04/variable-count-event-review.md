# A variable event count from retained forecast paths

Proposed next experiment 013. No new candidate has been fitted, optimized or scored for this review. The recommendation follows inspection of the actual 006–010 results and 012 scenario artifacts. The historical test has already informed this direction, so it remains exploratory.

## Recommendation

Use the existing 64 intact daily scenario paths to choose all 24 event calls jointly, allowing their count to change. Retain weather and satellite as separate reference distributions. Compare a worst-reference F1 objective with an equally safeguarded mean-reference objective, under both the conditional and recency banks. No additional statistical model is needed.

The useful change is the decision objective and variable count. It is not another version of the same classifier or another threshold grid. General F-measure maximization is established prior work. The proposed reference-specific constraints and use of these existing solar scenarios are an application hypothesis, not a verified invention.

## What the completed work actually leaves open

| Completed experiment | Relevant result or limitation |
|---|---|
| 006 | The selected weather classifier gains one weather-reference test TP but loses satellite-reference accuracy. A better weather fit does not resolve reference disagreement. |
| 007 | Averaging the two binary labels permits values 0, 0.5 and 1, but merges weather-only and satellite-only events. Its selected families fail the six-score test gate. |
| 008 | Two separate correction thresholds already allow independent additions and removals. The selected two-source classifier improves several counts but has weather-test precision 98.4174%, below raw NWP's 98.5119%. Merely allowing a variable count is therefore not sufficient or new to this project. |
| 009 | The selected joint BQN gains one test TP under each reference with unchanged FP against raw NWP. It does not dominate frozen 008 on every event metric, and weather point MAE regresses. All four optimizers reached the iteration limit. |
| 010 | The fixed-count exchange cannot add calls on underpredicted days without removing one elsewhere that day. Every primary margin produced no validation changes. Only three of 150 full validation days permit even a hindsight weather TP gain by exchanging one FP and one FN. The weather ceiling is 271 TP from 268, with at least 35 misses left. These are full-day diagnostic bounds, not the satellite scoring mask. |

These findings come from the retained protocols, runners, reports, selections and the 010 validation-budget analysis. File identities are listed in `variable-count-event-sources.json`. The proposed comparison keeps the exact 008 and 009 selected predictions rather than refitting or choosing a more convenient variant.

## Full primary papers and the adopted mechanism

**Waegeman et al., JMLR 2014, On the Bayes-Optimality of F-Measure Maximizers.** Read PDF pp. 2–4 and 12–17, especially printed pp. 3527–3528, Theorems 8–9, Eq. (16), Algorithm 1 and Eqs. (17)–(19). For a fixed number of calls K, expected F1 is linear in the selected bits, with coefficients that depend on each hour's event and the scenario's total event count. Enumerating K avoids an independence assumption. The paper sets empty/empty F1 to one. Its simple top-K solution does not include our six safeguards, so its quadratic complexity and exact Bayes-optimality result do not transfer to the proposed constrained search. It also distinguishes instance-wise and pooled F1 and warns that estimated probabilities can make exact optimization worse in practice. [Full PDF](https://www.jmlr.org/papers/volume15/waegeman14a/waegeman14a.pdf)

**Dembczyński et al., ICML 2013, Optimizing the F-Measure in Multi-Label Classification.** Read PDF pp. 2–4, §§3–5 and Eqs. (3)–(8). The plug-in approach separates distribution estimation from the decision that maximizes expected F1. Its fixed-count inner problem and outer count search provide the implementable structure. We reuse already generated empirical paths instead of fitting its conditional probability estimators. The two-reference constraints are additional engineering choices. Neither that paper's consistency results nor its empirical advantage establishes that our 64 historical residual paths are calibrated. [Full PDF](https://proceedings.mlr.press/v28/dembczynski13.pdf)

**Dembczyński, Cheng and Hüllermeier, ICML 2010, Bayes Optimal Multilabel Classification via Probabilistic Classifier Chains.** Read PDF pp. 2–5, §§2–4 and Eqs. (2)–(12). Conditional dependence matters through the chosen loss. Marginal event probabilities suffice for a sum of per-label error risks, whereas joint prediction losses can need more information. This makes a four-state weather/satellite head plausible, but does not show it is useful for this task. Four states at one hour are different from the hour-versus-daily-count information used by GFM. [Full PDF](https://icml.cc/Conferences/2010/papers/589.pdf)

The proposed optimizer needs each reference's empirical hour/count probabilities. It does not require an independent-hours model or a full 2^24 probability table. Pairing source days keeps the original scenario provenance, but the worst-reference objective compares two distributions rather than estimating an unobserved physical truth between them.

## Why not fit a four-state head first

A multiclass head for neither, weather-only, satellite-only and both would preserve disagreement direction lost by 007. However, a robust sum of separate reference error risks uses only its two marginals, which 010 already modeled with separate heads. A four-state learner would add a sparse conflict-class estimation problem and require a policy for missing satellite labels. It would not by itself specify which additions and removals improve P/R/F1. A fair test would also need paired-only and missing-label controls. Changing the decision rule using retained paths is the more direct test of the exposed limitation.

GFM is materially different from 008/009 thresholding because each hour's utility depends on the number of positives in the same scenario and on the proposed total calls. It is materially different from 010 because K can rise or fall and more than one bit can change. It is not a claim that those extra freedoms improve held-out scores.

## The decisive failure risk

Daily safeguards do not imply a pooled score safeguard. Consider two deterministic 24-hour days. On day A, raw TP/FP/FN is 1/0/1 and a candidate gives 2/0/0. On day B, raw is 1/1/9 and the candidate gives 10/10/0. Daily precision, recall and F1 each stay equal or improve. Pooled precision nevertheless falls from 2/3 to 12/22 because the candidate places more calls on the less precise day. This hand example must be a fixture, not a claimed experiment result.

There is also estimation error before that aggregation problem. The scenarios are transferred historical residuals, not 64 independent new measurements or a certified conditional distribution. Archived weather and SARAH3 can disagree and share upstream information. Fixed historical cutoffs establish timestamp order, not verified publication availability. A strict 600 W/m² event is not a measurement of physical curtailment, plant availability or safe dispatch.

The [proposed protocol](variable-count-event-protocol.md) therefore retains an exact whole-period six-score gate, all rejected controls, every padded horizon and the current reference masks. It reports comparisons with frozen 008/009 separately because those forecasts use later rolling issuance information. No event gain implies a water, energy or cost gain.

## Cost and scope

Root's read-only scenario-label complexity diagnostic found at most nine uncertain hours under either reference, with 72,459 subsets across the 299 horizons and two banks. Unanimous positives can be included and unanimous negatives excluded by a dominance argument, with the prohibited empty-action exception handled explicitly. The protocol enumerates those subsets exactly using rational scores. Both objectives share the same subset calculations. Raw remains an explicit candidate. This is simpler and stronger than the initially considered 28,704 floating-point MILPs.

Only the existing Python standard library and NumPy array reader are needed. No fitting, GPU, network, new package or solver is required. One horizon at a time should remain below 1 GiB working memory. Seconds to several minutes on the 8 GiB M1 is a planning estimate, not a completed timing. A fixed 30-minute total budget retains partial evidence and stops without scoring an incomplete candidate set. Actual wall time, CPU time, completeness and peak RSS must be recorded if the experiment runs.
