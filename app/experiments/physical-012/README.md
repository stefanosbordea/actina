# Conditional historical paths 012

Both conditional variants improve all eight aggregate cost and grid-energy measures in both periods. Neither passes the complete frozen gate because validation daily-regret CVaR90 remains positive. Keep the raw forecast control. No product replacement was made.

## What changed

For each forecast horizon, retrieve 64 historical days with the closest cumulative forecast PV path from all eligible past days. The distance uses raw archived weather forecasts only. Each reference supplies its own error path on the same selected dates. The existing water constraints, tariff, raw-point plan, empirical CVaR optimizer, numerical action floor and shuffle remain unchanged.

The comparison has two independent axes: recency versus forecast-conditioned history, and intact versus shuffled paths. Conditioning changes both marginal errors and dependence. Shuffling within either bank preserves its hourly values, so that comparison isolates temporal arrangement for that bank. This experiment is conditional residual sampling, not a new forecasting model or a calibration method.

## Observed results

Primary daily sets contain 139 validation and 144 test horizons, with complete weather and satellite values on identical original-period hours. Differences below are candidate minus the solar-aware raw-point control. Negative cost and grid differences are better. Cost CVaR and regret CVaR are different quantities.

| Period | Conditional paths | Reference | Mean cost Δ € | Cost CVaR90 Δ € | Mean grid Δ kWh | Grid CVaR90 Δ kWh | Regret CVaR90 € | Maximum regret € | Worse days |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| Validation | Intact | weather | -5.033 | -0.510 | -36.337 | -2.542 | +0.408 | +2.933 | 5 |
| Validation | Intact | satellite | -5.062 | -0.328 | -34.802 | -0.245 | +0.528 | +4.366 | 4 |
| Validation | Shuffled | weather | -5.763 | -0.395 | -45.377 | -1.935 | +0.125 | +1.199 | 3 |
| Validation | Shuffled | satellite | -6.344 | -0.173 | -48.996 | -0.050 | +0.768 | +9.654 | 4 |
| Test | Intact | weather | -7.389 | -8.182 | -47.317 | -57.980 | -3.346 | -1.091 | 0 |
| Test | Intact | satellite | -9.439 | -8.602 | -56.385 | -47.071 | -2.533 | -0.012 | 0 |
| Test | Shuffled | weather | -10.745 | -15.581 | -76.313 | -128.193 | -3.693 | -1.297 | 0 |
| Test | Shuffled | satellite | -14.604 | -21.972 | -94.688 | -167.055 | -2.378 | +1.277 | 2 |

The intact conditional plan reduces cost on every test horizon under both references. Its worst test-day savings are €1.091 for weather and €0.012 for satellite. It does not reduce grid energy on every day. Its largest test-day grid increases are 4.080 kWh under weather and 16.582 kWh under satellite. The cost result does not erase its validation failures. Shuffled conditional plans also improve test aggregate measures, while two satellite test days cost more than raw-point. Neither path family is selected after observing these results.

Relative to its matching recency policy, each conditional arm passes the eight-axis aggregate gate on test but fails it on validation. Neither passes the matched daily-regret gate in either period. The result supports further investigation of forecast conditioning. It does not establish that intact trajectories outperform the shuffled ablation.

The weather-only sensitivity retains 148 complete days in each period. Its full metrics, every candidate, daily ledger and all gate components remain in `result/report.json` and `result/{validation,test}/daily-outcomes.csv`. The eight-axis gate covers mean and CVaR90 of cost and grid energy under both references. The separate regret gate requires nonpositive daily cost-regret CVaR90 under both references and at least one strict gain. Both gates must pass in both periods for the declared overall recommendation. They do not.

## Reproduction and checks

All 598 recency schedules reproduce 011 exactly. All 299 horizons and 1,794 schedules were saved and hashed before outcome masks were applied. Planning includes boundary padding and missing-reference days. Every original scoring membership matches 011. The candidate pools contain 444 validation and 584 test days, using the original fixed cutoffs. All selected histories precede those cutoffs.

The candidate pool covers the target forecast total-supply range for all validation horizons. Eight test horizons remain beyond the full pool range. Similarity at a fixed forecast horizon does not imply similarity of forecast error. The 64th-neighbor distance, source ages, every pool distance and rank, selected IDs and exclusions are retained.

Run with the existing pinned Python environment from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-012/test_retrieval.py
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-012/run.py --out app/experiments/physical-012/reproduction-001
```

The runner refuses an existing output directory and changed pinned inputs. `inputs.json` identifies the exact source, optimizer, original comparison artifacts, protocol and code. Seven new fixture tests and all eight inherited physical fixtures passed. New checks cover analytical distance, summation order, clipping, exact ties, canonical date ordering, past paired completeness, insufficient history, invalid inputs, shuffle invariance and the matched-control gate. The original tests cover the physical LP, mass balance, CVaR tails and numerical fallback. Actual commands and exits are in `preflight-receipt.json` and `run-receipt.json`.

Source versions: Python 3.14.6, NumPy 2.5.3, SciPy 1.18.1, pandas 3.0.6. Solves use one thread and no fitting or new data download. The run used 148.343 seconds wall time, 140.640 seconds CPU time and 198,361,088 bytes peak resident memory on an Apple M1 Mac with 8 GiB RAM. No energy measurement was made.

## Limits and credit

The experiment follows already-inspected 011 outcomes, including test results. These are exploratory retrospective comparisons. Weather and SARAH3 are estimated references, not independent ground sensors. Historical source and reference publication latency remains unverified. No field savings, measured curtailed energy or live superiority is established.

The PV conversion and plant are illustrative. Unlimited grid backup, omitted operating-envelope physics and the endpoint-hour tariff convention remain unchanged. Total desalination water and nominal plant energy stay fixed at 2,880 m³ and 9,792 kWh per horizon. Reduced grid energy is a change in modeled energy sourcing, not reduced desalination energy. Tiny solver residuals and reporting resolution remain explicit.

The cumulative distance is physically motivated but fixed by hypothesis. Constant SEC only rescales it. It carries early differences into later prefixes and can cancel opposing hourly differences. No descriptor, neighbor count, weights, seed or optimizer was tuned after outcomes.

The [protocol](PROTOCOL.md) and [primary-paper review](../research-2026-10-04/conditional-scenarios.md) credit forecast-similarity retrieval, shared historical paths, power-water coordination and CVaR prior work. This adaptation is not full SimSchaake or decision-focused learning, and its novelty is not established.

## Independent audit

The [independent checker](review/check.py) passed with actual exit 0, recorded in [execution-002.json](review/execution-002.json). Its [result](review/result.json) verifies 714,332 assertions, all 153,616 distances and ranks, 3,674,112 scenario values, 1,794 water plans, all 598 exact recency matches and 54 unchanged files. Scenario-cost replay error is zero. Per-solve regret objectives were independently checked by sorted fractional tails. The audit replays saved solutions and is not a separate optimality certificate.

The initial checker used Python 3.14's compensated `sum` where the protocol declares explicit left-to-right addition. That checker-only mismatch is retained in [execution-001.json](review/execution-001.json), its log and original checker. The rerun changed only reviewer accumulation order. Candidate code, inputs and results were unchanged.

The largest exact water constraint residual is `15/8796093022208` m³, approximately `1.71e-12` m³. It is retained, lies within the frozen numerical tolerance and is not presented as an exact physical guarantee. Original 011 artifacts remain unchanged.
