# Joint-reference event target

**The new head fails the strict comparison against archived NWP.** It catches more events under both reference sources, but precision regresses under both. The stronger control remains in place. No application, scheduler or competition deliverable was changed.

The validation-selected joint-reference head uses the larger fixed configuration and cutoff **0.561345240141561**. On the test period it avoids seven weather-reference misses while adding two false alarms; against satellite it avoids six misses while adding three false alarms. These are tradeoffs, not an all-metric upgrade.

| Test reference | Method | Precision | Recall | F1 | False alarms | Misses |
|---|---|---:|---:|---:|---:|---:|
| Weather, 3,567 hours | Archived NWP | 0.985119 | 0.983168 | 0.984143 | 15 | 17 |
| Weather, 3,567 hours | Weather-only head, selected | 0.985134 | 0.984158 | 0.984646 | 15 | 16 |
| Weather, 3,567 hours | Joint-reference head, selected | 0.983284 | 0.990099 | 0.986680 | 17 | 10 |
| Satellite, 3,517 hours | Archived NWP | 0.957661 | 0.974359 | 0.965938 | 42 | 25 |
| Satellite, 3,517 hours | Weather-only head, selected | 0.955690 | 0.973333 | 0.964431 | 44 | 26 |
| Satellite, 3,517 hours | Joint-reference head, selected | 0.955045 | 0.980513 | 0.967611 | 45 | 19 |

The selected joint head improves four of the six test precision/recall/F1 comparisons and regresses on two. There are no equalities. Its frozen test gate fails, and the stronger requirement that every metric strictly improve also fails. The matched weather-only head improves three weather-reference metrics but regresses on all three satellite metrics. All negative candidates remain in the results.

## What changed

The feature matrix, eligible training rows and three capacity settings are exactly those of experiment 006. Only the training target changes: when weather and satellite estimates are both available, the target is the mean of their binary events above 600 W/m². Agreement gives 0 or 1; disagreement gives 0.5. If satellite is missing, the target uses weather alone. Every row has unit weight, so equal source weights apply to paired rows, not to the dataset globally. No rows were duplicated and no satellite feature was added.

LightGBM's `cross_entropy` objective accepts soft targets in [0,1]; its regression API preserves 0.5 labels. The output estimates a mixed reference target. It does not identify latent physical truth, establish a calibrated probability for either source, or measure physical surplus or curtailment. Weather and SARAH3 are reference estimates with different errors, not independent local ground sensors. [LightGBM objective documentation](https://lightgbm.readthedocs.io/en/stable/Parameters.html#objective).

Validation training contains 10,675 rows, all paired; 279 references disagree. Test refitting contains 14,241 past rows, including 147 missing satellite values; 375 available pairs disagree. Training-label ledgers retain the two events, source count, missingness and resulting soft label. No new data download or dependency was needed.

## Same selection rule for both families

The rule was fixed before reading the new training join or fitting. Each cutoff must meet NWP precision, recall and F1 on both weather-full and satellite-common validation. Exact count fractions determine admission and rank. The identical rule was applied to saved 006 weather-only validation probabilities, keeping the previous 006 selection untouched. This controls the selection-policy change without additional fits; old 006 cutoffs and default 0.5 are retained as separate diagnostics.

Only the larger joint-reference head qualifies. Its validation weather counts equal NWP (TP268, FP21, FN38); satellite counts improve to TP231, FP41, FN63 from NWP TP228, FP43, FN66. Small and medium joint heads do not qualify and their reported thresholds are diagnostic only. Both families select the larger head before any new test prediction or scoring. Neither passes the joint test gate. No parameter or cutoff was revised afterward.

The complete comparison retains nine methods, both periods, weather-full, weather-common and satellite-common bases, selected/default cutoffs and previous 006 cutoffs. Weather-common and satellite-common use identical rows. All original 3,566 validation and 3,567 test hours remain in the ledgers; 147 validation and 50 test satellite values remain missing and unscored for satellite metrics. Brier scores are retained separately for each reference; the fixed original, persistence and NWP controls supply hard 0/1 events. No irradiance point score is invented for an event head.

## Reproduce and limits

From the repository root, use the installed Python environment containing NumPy, pandas and LightGBM:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-007/run.py --output app/experiments/f1-007/NEW-RESULT
```

The runner refuses existing outputs. `PROTOCOL.md` fixes weights, configurations, gate and reporting; `inputs.json` pins 26 inputs. `result/validation-selection.json` freezes both families before the test pass. `run.log` and `run-receipt.json` retain the completed six-fit execution, exit 0 and identities. Independent audit files belong under `review/`.

This is retrospective rolling-origin evaluation on a test already inspected in earlier experiments. The hypothesis was motivated by an observed reference reversal. Past residual features use reference values preceding each origin, but historical publication availability is unverified. The satellite archive's publication delay also means target-before-origin alone is not an operational availability guarantee. Training data, derived consensus labels and these reference-sensitive scores do not establish live superiority, recovered curtailment, water service, costs or savings.
