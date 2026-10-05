# 019: Logistic correction of Stefanos's v2 forecasts

Both fixed logistic heads achieved higher observed validation F1 with fewer false positives than 008. The expanded head scored 91.0624% F1 against 008's 90.6355%, with four fewer false positives and one additional missed event. Its recall is therefore slightly lower than 008. This is a small result on repeatedly inspected historical validation, not established superiority on new data.

Against supplied v2 at its original 600 W/m² cutoff, the expanded head found eight more true events and produced eight fewer false positives. Precision, recall and F1 all improved in this comparison. No original test set was read or scored. No product model was replaced.

## Matched validation results

All rows below use the same 3,566 original validation hours and the strict observed event `actual > 600 W/m²`.

| Method | TP | FP | FN | TN | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Supplied v2, cutoff 600 | 262 | 25 | 44 | 3,235 | 91.2892% | 85.6209% | 88.3642% |
| Supplied v2, validation-selected cutoff 562 | 287 | 51 | 19 | 3,209 | 84.9112% | 93.7908% | 89.1304% |
| Fixed 008 | 271 | 21 | 35 | 3,239 | 92.8082% | 88.5621% | 90.6355% |
| 019 core, 11 forecast features | 269 | 17 | 37 | 3,243 | 94.0559% | 87.9085% | 90.8784% |
| 019 expanded, plus four past-error features | 270 | 17 | 36 | 3,243 | 94.0767% | 88.2353% | 91.0624% |

Both arms pass the declared observed gate of F1 greater than 008 and no additional false positives. The expanded arm adds one true event with no additional false positives relative to the matched core arm. All controls, including raw day1/day2 forecasts, persistence, probability scores and unchanged radiation errors, are retained in [result/summary.json](result/summary.json).

The expanded head's Brier score is 0.0113040 and log loss is 0.0448005. Both are slightly worse than the core head's 0.0112553 and 0.0445930. Higher F1 at the selected operating point does not imply every quality measure improved.

## What changed

The radiation predictor remains the frozen, chronology-safe refit of Stefanos's v2 configuration from 016. Its radiation curve is unchanged here. It differs from the supplied model because 016 selected its tree count using a training-only stopping window. Its validation MAE remains 18.700675 W/m², compared with 18.697343 W/m² for the supplied v2 curve.

019 replaces only the small event head used in 017/018 with logistic regression. Both arms use the same fixed configuration as the logistic head in 016: C=1, L2 regularization, LBFGS, tolerance 1e-8 and at most 1,000 iterations. There is no fitted scaler, class weighting or parameter search. Existing radiation/error features stay divided by 100.

The core arm consumes v2's predicted radiation, supplied day1 radiation/cloud, pinned ECMWF day2 and GFS radiation, forecast disagreement and fixed solar/calendar features. The expanded arm adds four fixed trailing 14-day features: v2 bias, v2 mean absolute error, ECMWF bias and ECMWF mean absolute error. Each observation used by a context feature has target time strictly before the current forecast origin. The original forecast's origin is exactly 24 hours before its target.

The 15 expanded coefficients, their exact feature order, intercept, classes and solver settings are readable in [result/expanded-final.json](result/expanded-final.json). They define a weighted sum followed by a sigmoid. The event call is strictly `probability > 0.49`. Each of the eight forward-fold models is retained in the same format. This is a direct extension using v2's actual predictions, not an 008 prediction wrapper.

## Chronology and selection

Both arms use the same 10,675 common-source training OOF rows and all 3,566 validation rows. The 1,824 earlier OOF rows without complete retained NWP coverage remain excluded exactly as in 017. No future values fill those gaps.

Four expanding head folds use only earlier OOF examples whose targets are strictly before the held origin. Thresholds are selected from their pooled predictions, using 181 fixed ticks and an FP cap equal to the raw ECMWF control on those training hours. Both arms selected 0.49. Core training FP was 52 and expanded FP was 53 against the cap of 63. This training cap is not a guarantee about later false positives.

The source lock precedes all historical fits. Final coefficients and thresholds were frozen before loading the saved validation context, and predictions were frozen before full-reference scoring. The context itself contains strictly past validation observations, so this remains a sequential historical simulation rather than completely sealed-outcome validation. 018's independent audit verifies those windows and actual prefix invariance.

The predeclared paired comparison was one fixed linear learner with and without the same context. Previous 016–018 failures are retained. This experiment did not retune parameters, feature windows or cutoffs after validation scoring.

## Uncertainty and scope

The retained 2,000 paired target-day bootstrap draws use seed 17017 and 150 date blocks. Expanded-minus-008 F1 has a descriptive 95% interval of −1.6061 to +2.6215 percentage points. Expanded-minus-core spans −0.3445 to +0.7867 points. Both intervals include zero. The four context features have not established a reliable advantage.

Expanded-minus-supplied-v2-at-600 spans +0.6679 to +4.7335 points. These intervals do not correct for repeated validation inspection or experiment selection. The original supplied v2 also used validation for early stopping, while 008 and cutoff 562 were selected using validation. A fresh, agreed evaluation is needed before claiming general superiority.

The day1 and pinned day2 inputs have different source settings. Their nominal day labels do not prove practical issue-time availability. Historical forecast sources and a reconstructed OOF sequence do not establish a live deployment backtest. This experiment improves event calls, not the numeric irradiance forecast or a measured plant outcome.

## Reproduce and inspect

From the repository root, with the existing environment:

```sh
/Users/kixem/Documents/Loucas-Stefanos-Workspace-2026-09-19/AquaShift/.venv/bin/python -m unittest discover -s app/experiments/v2-019 -p test_run.py -v
/Users/kixem/Documents/Loucas-Stefanos-Workspace-2026-09-19/AquaShift/.venv/bin/python app/experiments/v2-019/run.py --out reproduction
```

The runner refuses an existing output directory and verifies 56 source/input pins before and after execution. Do not overwrite `result/`. A reproduction refits only the fixed event heads and does not train Stefanos's original model or read original test predictions.

The authorized run exited 0. Its recorded outer duration is 4.6891 seconds, including imports. The inner run took 0.8023 seconds, used 0.7174 CPU seconds and peaked at 217,333,760 bytes RSS. Fits were serial with at most two threads. Three synthetic preflight checks passed, covering fixed parameters, exact serialized-coefficient replay and the unchanged threshold FP cap.

The command, exit status and log hash are in [execution-001.json](execution-001.json). Model hashes, decision hashes, timing and all output identities are retained in the freeze/completion files. The frozen lock SHA-256 is `6980b53364ae337cb9926549f7081e9c829bb629f83272b39c07ed538c8d6330`.

The independent audit in [review/](review/) passed with exit 0. It replayed all ten coefficient sets to a maximum probability difference of 1.11e−16 and exactly reproduced event calls. It verified 56 source/input pins, all 362 threshold rows, the training FP cap, chronological memberships, convergence, confusion counts and bootstrap intervals.
