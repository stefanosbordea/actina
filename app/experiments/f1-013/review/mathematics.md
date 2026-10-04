# Exact enumeration review

No blocking mathematical issue with the reviewed draft. The conclusion requires the stated six guards, explicit raw candidate, count restriction and tie order. This is an algebraic verification of the proposed adaptation, not a novelty or forecast-quality claim.

Let K be the selected count, S the scenario truth count and T their intersection size. Within each reference, average over all 64 scenarios. For K>0:

- Expected precision is E[T]/K.
- Expected recall is E[T/S | S>0]. It is null when every S is zero.
- Expected F1 is E[2T/(K+S)].

The coefficient sums in the draft reproduce these expectations exactly. Recall is conditional on nonempty truth, not a ratio of expected counts. At K=0, precision is null, recall is zero whenever defined, and expected F1 is Pr(S=0). Only a raw-empty horizon permits an empty candidate. Each reference retains its own denominators and guards.

## Why the reduction preserves the full ranked optimum

An omitted hour positive in all 128 paths can be added. For each scenario this changes (T,K) to (T+1,K+1). Defined precision cannot decrease, recall increases and F1 strictly increases. All scenarios have S>0. Both primary objectives therefore strictly improve while retaining feasibility.

Removing a universally negative selected hour preserves T and recall. If the remaining K is positive, precision and F1 cannot decrease. Expected F1 strictly increases in a reference exactly when that reference has positive expected T.

For a strictly positive minimum-uplift optimum, both references have positive expected T. Otherwise one candidate F1 is zero, its guard forces raw F1 to zero, and minimum uplift cannot be positive. Removing any universally negative hour thus strictly improves both F1 values and the minimum objective. A strictly positive mean-uplift optimum has positive expected T in at least one reference, so removal strictly improves its mean objective.

The only last-call exception consists entirely of universally negative calls. If K0>0, removing its last call would be inadmissible. But its expected F1 is zero under both references. Feasibility forces both raw F1 values to zero, so it cannot have positive uplift. When the optimum uplift is zero, raw is feasible and uniquely wins the zero-change tie. This also covers all-empty truth distributions. When K0=0, final removal is permitted and cannot reduce expected F1.

Therefore every positive-uplift optimum is canonical. Otherwise raw wins. Enumerating all ambiguous subsets plus raw preserves the full optimum under exact objective, fewer changes, smaller K, then selected-hour tuple. It does not assert an optimum at every separately fixed K. Count canonical subsets and any additional noncanonical raw vectors separately.

## Independent checks and limits

`math-check.py` imports no production helper and reads no historical input. It exhausts all 256 two-hour, two-reference, two-scenario distributions and all four raw actions. It also checks 128 seeded four-hour distributions with every raw action. Both objectives and the complete tie order agree with full action enumeration. Coefficient and direct-ratio calculations agree, including all-empty, sole-negative, count-changing, reference-conflict and exact rational boundary fixtures.

The recorded run exited 0 with 89,193 checks. Two- and four-pattern distributions can be repeated to 64 equally weighted paths without changing any expected metric. See `math-result.json` and `math-execution-001.json`.

Identical hourly marginals do not determine expected F1. For action {0}, paths {00,11} give F1=1/3 while paths {10,01} give F1=1/2. Both give precision=1/2 and conditional recall=1/2.

Daily guards alone do not imply pooled improvement. Within 24-hour days, keep day1 at TP9/FP1/FN0. Change day2 from TP1/FP9/FN1 to TP2/FP13/FN0. Every daily P/R/F1 is nondecreasing, while pooled precision falls from10/20 to11/25 and pooled F1 falls from20/31 to22/36. This is a counterexample to the aggregation inference, not a claim that the proposed optimizer selects that action under perfect scenario truth.

The scenario probabilities remain empirical and uncalibrated. Exact optimization establishes only the optimum for those supplied distributions. Pooled observed scores, source availability, uncertainty and any downstream water consequences still require their separate retained checks.
