# Decision-preserving correction 005

The fixed correction retains **every archived NWP >600 W/m² event call** while using raw-analogue point corrections within the same decision class. On the retained weather test, it lowers NWP MAE from **8.806 to 6.918 W/m²**, with the same 15 false positives and 17 false negatives. Its satellite validation error is worse. This is standard constrained postprocessing designed after test inspection, not proof of a new forecasting breakthrough or live superiority.

## Reusable function

`correction.py` exports one pure function. With that file on Python's module path:

```python
from correction import constrain_correction

point = constrain_correction(nwp=602, corrected=590)
event = point > 600
# point == 600.0000000000001; event is True, matching the NWP call.
```

For positive NWP calls, the function floors the corrected point at the next binary64 value above 600. For negative calls, it caps the point at 600. It validates finite nonnegative numeric inputs and supports a threshold argument defaulting to 600. This experiment uses 600 only. Its CSV retains both round-trip decimal values and hexadecimal binary64 values; deriving decisions from a rounded display value would destroy the positive boundary.

This preserves event calls only. The supplied scheduler also ranks forecast magnitudes when repairing shortfalls. Corrected points can change that ranking, dispatch, costs and tank paths. For example, NWP `[650, 700]` and corrected points `[900, 610]` retain two positive calls but reverse their order. The correction has **not** been connected to the scheduler, product, competition deck or handoff pack.

## Full original weather test

Every row uses the same 3,567 test hours. MAE and RMSE are W/m²; event labels are radiation strictly above 600. Raw analogue decisions retain probability strictly above 0.5. Guarded decisions come from the constrained point, with no new probability or calibration claim.

| Method | MAE | RMSE | Precision | Recall | F1 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| Original | 14.266 | 42.660 | 0.975733 | 0.955446 | 0.965483 | 24 | 45 |
| Persistence | 12.259 | 40.107 | 0.980100 | 0.975248 | 0.977667 | 20 | 25 |
| Fixed archived NWP | 8.806 | 22.800 | 0.985119 | 0.983168 | 0.984143 | 15 | 17 |
| Raw analogue | 6.921 | 22.125 | 0.984143 | 0.983168 | 0.983655 | 16 | 17 |
| Guarded analogue | 6.918 | 22.124 | 0.985119 | 0.983168 | 0.984143 | 15 | 17 |

The large numeric-error difference comes from the existing raw analogue. The guard itself changes only three test points, improving weather-test MAE over raw analogues by 0.0035 W/m². It makes two downward projections and one upward projection, with maximum adjustment 7.5 W/m². Relative to raw probability decisions, it corrects two false positives and creates one false positive. The net FP count falls by one; those are three distinct hours, not a single repaired error.

## Both splits and reference bases

Weather-common and satellite-common use exactly the same available-reference hours. All original rows remain in the ledgers. The satellite reference is missing for 147 validation and 50 test hours. No missing values were filled.

| Split and reference | Hours | NWP MAE | Guarded MAE | NWP RMSE | Guarded RMSE |
|---|---:|---:|---:|---:|---:|
| Validation, weather full | 3,566 | 17.693 | 16.799 | 45.420 | 44.919 |
| Validation, weather common | 3,419 | 16.617 | 15.726 | 39.884 | 39.372 |
| Validation, satellite common | 3,419 | 33.818 | **33.853** | 73.109 | **74.072** |
| Test, weather full | 3,567 | 8.806 | 6.918 | 22.800 | 22.124 |
| Test, weather common | 3,517 | 8.866 | 6.984 | 22.943 | 22.276 |
| Test, satellite common | 3,517 | 19.325 | 18.228 | 44.948 | 44.943 |

**Satellite validation is a negative result.** Guarded MAE and RMSE both worsen against NWP. On satellite test, guarded MAE is also slightly worse than the unguarded raw analogue, 18.2280 versus 18.2273 W/m². All 30 method/split/reference records, signed bias, confusion counts and undefined-ratio denominators remain in `result/report.json` and `result/metrics.csv`.

Guarded precision, recall, F1 and confusion counts equal NWP on every basis by construction. It cannot improve NWP classification. On satellite test both have precision 0.957661, recall 0.974359, F1 0.965938, FP 42 and FN 25. Against the raw analogue it corrects one FP and one FN but creates another FN. On satellite validation it removes four raw-analogue false positives while adding seven misses, so it gives up the analogue's higher recall.

Twelve validation points project downward, maximum 16 W/m². On the full validation set, the guard leaves 13 points exactly at 600, including one already there. Test leaves two points at 600 and one at `nextafter(600,+∞)`. The ledgers retain every changed value and the report records full/common subset counts, threshold pileups and both median-rule and probability-rule disagreements.

## Reproduce and review

Python standard library only, no installation, fit or network request:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python3 app/experiments/f1-005/run.py --output app/experiments/f1-005/result-new
```

The runner refuses an existing output directory and verifies pinned bytes before and after computation. `PROTOCOL.md` and `inputs.json` were saved before running. `MEASUREMENT-NOTE.md` fixes extra boundary/serialization diagnostics before computation. The completed run exited 0 and checked all 7,133 original rows, 456,512 scenario values, projection identities and exact CSV round-trips. `run.log` and `run-receipt.json` retain execution evidence. Independent fixtures and reconstruction live in `review/`. The independent review passed 247,573 checks, including all 30 metric records and exact boundary serialization; `completion-receipt.json` links its evidence to the unchanged original run.

Original model/reanalysis and SARAH3 satellite values are reference estimates, not established local station truth. Historical forecast publication times remain unverified. This already-inspected test supports a bounded implementation result, not seasonal or general superiority, physical-surplus safety, recovered curtailment or customer savings. No model or competition artifact was changed.
