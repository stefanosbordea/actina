# Event classifier with past residual context

The validation-selected classifier improves all three event metrics slightly on the original weather-reference test: **one fewer missed event, with the same 15 false alarms**. Against the satellite reference it loses one true positive and adds two false alarms. This is a reference-sensitive retrospective result, not a replacement recommendation.

Experiment 003 already included an NWP event classifier. This experiment adds solar geometry and strictly past residual context, tries three fixed complexity levels, and requires validation precision, recall and F1 to each meet raw NWP. It selected `larger`, cutoff **0.5411745121421931**, before predicting or scoring the test. The better test F1 of `medium` does not change that selection.

| Method | Validation precision | Recall | F1 | Test precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Original | 0.814189 | 0.787582 | 0.800664 | 0.975733 | 0.955446 | 0.965483 |
| Persistence | 0.797386 | 0.797386 | 0.797386 | 0.980100 | 0.975248 | 0.977667 |
| Raw day2 NWP | 0.927336 | 0.875817 | 0.900840 | 0.985119 | 0.983168 | 0.984143 |
| Small | 0.927336 | 0.875817 | 0.900840 | 0.988048 | 0.982178 | 0.985104 |
| Medium | 0.930796 | 0.879085 | 0.904202 | 0.986111 | 0.984158 | 0.985134 |
| Larger — selected | 0.931271 | 0.885621 | 0.907873 | 0.985134 | 0.984158 | 0.984646 |

These use all **3,566 validation and 3,567 test hours**, with strict actual radiation above 600 W/m². Validation false alarms/misses fall from NWP's 21/38 to selected 20/35. Test falls from 15/17 to 15/16. The selected classifier's original-reference test gate passes; that gate alone does not establish superiority under a different reference or in operation.

## Satellite check

Every method uses the same available-reference hours. Missing truth is retained as unscored: 147 of 3,566 validation hours and 50 of 3,567 test hours. No missing forecast or original evaluation hour is dropped.

| Satellite reference | Hours | Precision | Recall | F1 | False alarms | Misses |
|---|---:|---:|---:|---:|---:|---:|
| Validation NWP | 3,419 | 0.841328 | 0.775510 | 0.807080 | 43 | 66 |
| Validation selected | 3,419 | 0.842491 | 0.782313 | 0.811287 | 43 | 64 |
| Test NWP | 3,517 | 0.957661 | 0.974359 | 0.965938 | 42 | 25 |
| Test selected | 3,517 | 0.955690 | 0.973333 | 0.964431 | 44 | 26 |

On the same 3,517-hour subset using the original weather reference, NWP F1 is 0.983887 and selected F1 is 0.984399. The satellite reversal therefore follows the reference change, not merely removal of missing hours. All six methods, both periods and all three reference bases are retained in `result/comparison.csv`. Membership files and the report retain every missing timestamp.

The probabilities also have saved Brier scores, but the NWP control is a hard 0/1 event, not a supplied probabilistic forecast. No W/m² point prediction or MAE is invented for these classifiers.

## Timing and checks

Each origin uses residuals only from valid times strictly before that origin. The two rolling windows are 24 and 168 hours; the additional lag is 24 hours. Training targets precede the first evaluation origin, preserving the 24-hour purge. Missing early history and cloud remain explicit. Selection uses exact confusion-count fractions and validation probabilities only; every threshold and failed candidate is retained.

This is a rolling-origin retrospective evaluation: later origins can use earlier realized reference values within the evaluation period. Model weights are fitted once per split. The forecasts were not all issued at the period's first origin, and real-time availability of these reference values is not established.

The run completed with six fits, two threads, no new dependencies and no changes to the original model/data/evaluation files. The separate standard-library checker reconstructed all 89,160 history values, 42,798 saved prediction rows, 5,202 threshold rows and 36 comparison rows. Its first attempt stopped on a timestamp text-format mismatch (`T` versus a space); that script and log remain intact. The retry compares parsed timestamps and passes without modifying fitted results.

The test had already been inspected in earlier experiments. Historical NWP publication and operational availability of archived weather/residual inputs remain unverified. Weather and SARAH3 are estimates, not established local ground-sensor measurements. No new significance, curtailment recovery or savings claim follows. The competition pack and supplied scheduler remain unchanged.

Run, from the repository root, into a new output directory:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-006/run.py --output app/experiments/f1-006/NEW-RESULT
```

`PROTOCOL.md` and `inputs.json` were frozen before fitting. `result/validation-selection.json` records the choice before the test pass. `run-receipt.json` retains execution and audit identities; `check.py` reconstructs the retained `result/` without fitting.
