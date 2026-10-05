# 016 result

Neither fixed correction beat 008. The logistic head improved the v2 refit's validation F1 by 0.97 percentage points, with six additional true positives and one additional false positive. That remains below 008, and the paired daily-block interval for the gain includes zero. The result does not justify replacing the team model or claiming a breakthrough.

All results below use the same 3,566 original validation hours. The period has been inspected before. Both new head thresholds were selected only from training-period forward predictions and frozen before this scoring pass.

| Method | TP | FP | FN | TN | Precision | Recall | F1 | Radiation MAE, W/m² |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Frozen 008 | 271 | 21 | 35 | 3,239 | 92.81% | 88.56% | 90.64% | — |
| Logistic correction | 268 | 26 | 38 | 3,234 | 91.16% | 87.58% | 89.33% | Base curve retained |
| Boosted correction | 270 | 33 | 36 | 3,227 | 89.11% | 88.24% | 88.67% | Base curve retained |
| Chronological v2 refit | 262 | 25 | 44 | 3,235 | 91.29% | 85.62% | 88.36% | 18.7007 |
| Supplied v2, threshold 600 | 262 | 25 | 44 | 3,235 | 91.29% | 85.62% | 88.36% | 18.6973 |
| Supplied v2, threshold 562 | 287 | 51 | 19 | 3,209 | 84.91% | 93.79% | 89.13% | 18.6973 |
| Supplied raw NWP day1 | 253 | 34 | 53 | 3,226 | 88.15% | 82.68% | 85.33% | 21.5580 |
| Retained raw ECMWF day2 | 268 | 21 | 38 | 3,239 | 92.73% | 87.58% | 90.08% | 17.6929 |
| Persistence | 244 | 62 | 62 | 3,198 | 79.74% | 79.74% | 79.74% | 32.4694 |

The later user criterion requires higher F1 than 008 with no additional false positives. Both heads fail. That criterion is recorded separately in [post-run-criterion.json](post-run-criterion.json), without changing the frozen selection policy.

## What was added to Stefanos's code

Stefanos's nine regression features and LightGBM configuration remain the base. His supplied implementation uses validation early stopping. This experiment instead chooses tree count using a purged stopping window inside training and refits on the permitted training rows. It selected 159 trees. This produces a distinct radiation curve, even though its >600 event counts match the supplied model.

Six forward base folds produce 12,499 predictions for hours that their base model did not train on. A small event head receives each base prediction, its disagreement with Stefanos's raw NWP radiation, his NWP cloud value, and cyclical hour/month features. It learns whether the target exceeds 600 W/m². The logistic head has eight coefficients and one intercept. The alternative boosted head has 150 shallow trees. These are fixed alternatives with no parameter sweep.

The important code flow in [run.py](run.py) is:

```python
# Each held fold's training labels resolve before its first origin.
eligible = train.loc[permitted(train.index, held.index[0])]
model, info = fit_base(eligible, label, out)
prediction = np.maximum(model.predict(held[BASE_FEATURES]), 0)

# The event learner consumes these held-out base predictions.
meta_x = head_features(oof["base_prediction"].to_numpy(), oof)
final_heads[arm] = fit_head(arm, meta_x, meta_y)
```

Four forward head folds provide the training-period scores used to select strict probability thresholds 0.425 and 0.385. The full 181-tick tables are retained for both heads. No validation threshold was chosen or changed after the result.

The logistic coefficients are in [logistic-model.json](result/logistic-model.json). The trained boosted head's largest gain importance is its base-prediction margin, with the other features listed in [boosted-head-importance.csv](result/boosted-head-importance.csv). This establishes an explicit dependence on the v2 refit. Feature importance is not a causal attribution, and there was no no-v2 ablation in this frozen run.

## Evidence

- [Protocol](PROTOCOL.md), [source/input lock](lock.json) and [upstream timestamp audit](inputs/source-audit.json).
- [Execution receipt](execution-001.json) and [complete stdout/stderr](execution-001.log). Exit 0, external wall time 14.11 seconds, measured inner wall time 9.12 seconds, CPU time 6.15 seconds, peak RSS 177,668,096 bytes. Two-thread limits, serial fitting.
- [Preflight receipt](preflight-receipt.json). Eight synthetic checks passed. The earlier mixed-format fixture failure is retained in its original log.
- [Policy freeze](result/policy-freeze.json), saved before validation outcomes were parsed, includes final model and decision hashes.
- [All validation predictions and calls](result/validation-evaluation.csv), [exact metrics](result/summary.json), [paired daily-block intervals](result/day-bootstrap.json) and [completion/output hashes](result/completion.json).
- [Primary-paper review](RESEARCH.md). Stacked post-processing and probability models are established methods. This experiment does not claim a new algorithm.

Every saved training and validation row was checked against the actual upstream weather/NWP row shifts. Both raw indices and their union contain 24,048 regular hourly entries. No shifted target differs from origin +24h and no training exclusions were required. The source contains both `nwp_radiation` and `nwp_cloud`.

The raw day1 and retained ECMWF day2 controls have different provenance and values. They are not interchangeable forecasts. Their original operational issue and publication timing remain unverified.

Reproduce the frozen experiment from the repository root with the saved inputs and recorded dependency versions, using a new output directory:

```sh
python3 -m unittest discover -s app/experiments/v2-016 -p test_run.py -v
python3 app/experiments/v2-016/run.py --out replay-001
```

The original `result/` is never overwritten. The script refuses modified locked sources, fits serially and enforces a 30-minute limit. This reproduction command has been provided, not executed again. No original test outcomes, training sources, product defaults or team messages were changed by this experiment.
