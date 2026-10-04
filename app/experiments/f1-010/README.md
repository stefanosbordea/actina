# Paired exchanges at one daily forecast time

**No improvement. Both fixed arms retain the unchanged archived-weather decision.**

This experiment forecasts all 24 hours of the following day at one common issue time. It trains separate weather-reference and satellite-reference event heads, then considers exchanging one selected hour for one unselected hour. The primary rule requires both heads to prefer the exchange. The matched ablation uses their mean preference. This applies established constrained-ranking and exchange ideas to this case. Novelty is not established.

All six frozen margins were retained. The primary rule made no exchanges in either period. The mean rule at margin zero made one validation exchange that left weather counts unchanged and worsened the satellite counts by one true positive. Every other mean margin made no exchanges. Validation therefore selected no-swap for both arms before test predictions. Neither arm is an upgrade.

| Margin | Min rule on validation | Mean rule on validation |
|---:|---|---|
| 0 | No exchanges. All six metrics equal control, so no strict gain | One exchange. Weather precision, recall and F1 equal control. Satellite precision, recall and F1 regress |
| 0.05 | No exchanges. All six equal, no strict gain | No exchanges. All six equal, no strict gain |
| 0.10 | No exchanges. All six equal, no strict gain | No exchanges. All six equal, no strict gain |
| 0.20 | No exchanges. All six equal, no strict gain | No exchanges. All six equal, no strict gain |
| 0.30 | No exchanges. All six equal, no strict gain | No exchanges. All six equal, no strict gain |
| 0.50 | No exchanges. All six equal, no strict gain | No exchanges. All six equal, no strict gain |

The fixed daily count severely limits this mechanism. Across all 150 complete validation days, only three days contain both a weather false alarm and a weather miss. Even perfect hindsight exchanges could raise weather TP only from 268 to 271. At least 35 misses remain because the daily call counts are too low on those days. Across the 141 complete days with every satellite value available, only five days have both error types. The corresponding TP ceiling is 233 from 228, with at least 57 unavoidable misses. Those satellite bounds use 3,384 complete-day rows, not the 3,419-hour satellite scoring mask. These are post-run, validation-only ceilings, not trained policies or achievable guarantees. `validation_budget.py` reproduces them from the frozen validation predictions.

| Selected policy | Reference | Test hours | TP | FP | FN | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Raw weather forecast and both selected arms | Weather | 3,567 | 993 | 15 | 17 | 98.5119% | 98.3168% | 98.4143% |
| Raw weather forecast and both selected arms | Satellite | 3,517 | 950 | 42 | 25 | 95.7661% | 97.4359% | 96.5938% |

## What changed

The shared issue time is the preceding day at 00:00 on the fixed UTC+03 clock. Endpoint leads are 24–47 hours and preceding-hour interval starts are 23–46 hours after issue. Weather state comes from issue−1h, radiation lag from issue−24h and residual history from targets strictly before issue. No later original rolling-origin state is retained. Target geometry and the two archived forecasts remain specific to each target hour.

All 17,832 original targets remain. Validation includes 3,600 complete-day forecast rows, then scores the original 3,566 rows. Test includes 3,576 rows, then scores the original 3,567 rows. Padding and satellite missingness are retained and never select a pair. Weather training has 10,656 and 14,232 rows. Satellite training has 10,656 and 14,085 rows, with 147 missing test-training labels explicitly excluded.

This is a retrospective, already-inspected test. Historical source publication times remain unverified. Earlier original, persistence and experiment008 forecasts use different issuance information and are labeled as context. Satellite and weather references are estimates, not measured plant surplus.

A complete-day exchange preserves the number of positive event calls. With the same complete truth set, an extra true positive necessarily removes a false positive and a false negative. This identity does not promise a correct exchange and need not survive missing-reference or partial-day masks. It says nothing about physical dispatch, water delivery, cost, schedule ordering or safety.

## Reproduce and inspect

Use the repository's pinned replay environment. No new dependency, network call or GPU is needed.

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-010/test_policy.py
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-010/run.py --out app/experiments/f1-010/reproduction
```

The output directory must be new. `inputs.json` pins all 22 source and implementation files. The runner checks them before fitting. `result/validation-selection.json` freezes both choices before the test stage. Full predictions contain every margin and selected decision. Pair ledgers retain source-specific differences, all margins, actions and both scoring masks. The four fitted models, issued features, source timestamps, training membership and output hashes are saved for independent replay.

Seven preflight tests pass. They cover source replacement, count preservation, the masked-subset exception, strict margins, deterministic ties, disagreement between the two rules and invalid inputs. The first preflight caught an assumption about pandas timestamp resolution. Its failed log and original source are preserved in `attempts/preflight-001`. The corrected check compares timedeltas directly. No fit or score had run at that point.

The completed run exited zero. It took 5.293 seconds of internal wall time and 4.532 seconds of process CPU time, with a 199.6 MB process peak RSS on the Apple M1 host. Two LightGBM threads were allowed. These are execution measurements, not comparative speed or energy claims.

The [independent audit](review/result.json) passed. It reconstructed all 17,832 source rows and 481,464 feature values, replayed 14,352 probabilities, checked 3,588 pair-margin records and recomputed 120 metric records. All 42 pinned inputs and outputs remained unchanged. It also confirmed the no-swap selections and the validation count-budget ceilings. The [execution receipt](review/execution-receipt.json) records the actual command and successful exit.
