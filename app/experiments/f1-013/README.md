# 013: exact daily event decisions

**No forecast improvement.** Both conditional arms retain every raw ECMWF call. Both recency arms add two false alarms in validation and leave test unchanged. None passes the frozen improvement gate. Stefanos's original model and the public product remain unchanged.

The mechanism adapts published generalized F-measure maximization to two separate empirical reference distributions. It allows the daily number of sunny-hour calls to increase or decrease, while guarding expected precision, recall and F1 under both references. All comparisons use exact rational arithmetic. It is an exact solution for the retained scenarios, not a calibrated or population-optimal forecast.

## What ran

The protocol and inputs were frozen before the run. All four arms and both periods were planned and hashed before scoring references opened. The run evaluated 72,459 candidate actions over 299 daily horizons in 11.47 seconds, using 118 MB peak memory. It completed with exit 0. The four arms isolate conditional versus recency scenarios and minimum versus mean expected F1 uplift under identical safeguards.

The primary conditional robust arm equals raw ECMWF on every retained hour, including boundary padding. Its test scores are:

| Reference | Precision | Recall | F1 | False alarms | Misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weather, 3,567 hours | 98.512% | 98.317% | 98.414% | 15 | 17 |
| Satellite, 3,517 common hours | 95.766% | 97.436% | 96.594% | 42 | 25 |

These are the unchanged raw-forecast scores. Experiment 009 still catches one additional event under each test reference without another false alarm. Experiment 008 retains different precision/recall tradeoffs. Neither control was reselected. Original, persistence, 008 and 009 use later rolling information and are same-hour context comparisons, not matched daily-issue controls.

Validation remains harder. Conditional robust equals raw at weather F1 90.084% and satellite F1 80.708%. Recency adds two false alarms under each reference, lowering F1 to 89.782% and 80.423%. Retaining raw satisfies nonregression but fails the required strict improvement.

## Evidence

- [Frozen protocol](PROTOCOL.md) and [source hashes](inputs.json).
- [Forecast-only complexity diagnostic](complexity-001/complexity.json).
- [Decision freeze](result/planning-freeze.json), [complete metrics](result/report.json) and [actual execution receipt](result/execution-receipt.json).
- [Independent analytical review](review/actual-core.md): 407,109 assertions against full-action exhaustive synthetic optima. Runner and core fixtures pass 23 tests. The initial checker coverage gap and initial fixture errors are preserved.
- [Independent historical audit](review/runner-and-result.md): 3,721,230 checks reconstruct every retained candidate, coefficient, safeguard, ranking, mask and comparator metric.
- [Paired calendar-block sensitivity](uncertainty/PROTOCOL.md) and [120 marginal intervals](uncertainty/result/report.json), using 20,000 shared draws across both periods and block lengths 1 and 7. Independent reconstruction matches every draw, daily confusion count and percentile endpoint exactly. No undefined draws occurred. Every interval against raw is exactly zero because predictions are identical. This analysis adds no new admission gate.

The [forecast-only diagnostic](diagnostic/result/summary.json) identifies the obstruction. Raw is the sole feasible retained action on all 299 conditional-bank days. Before safeguards, the robust objective offers strict gains on seven validation days and three test days. The precision safeguard alone rejects all ten opportunities. This describes the retained empirical scenarios and does not justify relaxing precision on observed outcomes.

The separate [014 water scheduling interface](../physical-014/README.md) has completed with identical plant assumptions and service. Its primary plans exactly equal raw, so it adds no physical benefit. No event metric is presented as recovered electricity or additional water.

## Reproduce

Use the pinned Python 3.14.6 and NumPy 2.5.3 environment. Keep all four numerical-library thread limits at two or below. The runner refuses to replace outputs and enforces its declared 30-minute limit.

```sh
python -m unittest discover -s app/experiments/f1-013 -p 'test_*.py' -v
python app/experiments/f1-013/run.py --out app/experiments/f1-013/reproduction
```

The saved primary run is never overwritten. References are weather and satellite estimates, not local sensor truth. These periods were already examined in earlier experiments. Historical publication availability, prospective reliability and a new scientific contribution remain unestablished.
