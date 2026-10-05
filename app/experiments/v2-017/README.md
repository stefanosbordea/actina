# 017 result

Adding the two retained weather forecasts improved the matched correction, but **did not beat 008 or meet the no-additional-false-positive requirement**. No product model or threshold was changed.

| Method | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Frozen 008 | 271 | 21 | 35 | 3,239 | 92.81% | 88.56% | 90.64% |
| Expanded v2 correction | 274 | 26 | 32 | 3,234 | 91.33% | 89.54% | 90.43% |
| Matched core correction | 268 | 28 | 38 | 3,232 | 90.54% | 87.58% | 89.04% |
| Unchanged 016 v2 refit | 262 | 25 | 44 | 3,235 | 91.29% | 85.62% | 88.36% |
| Supplied v2 at 600 | 262 | 25 | 44 | 3,235 | 91.29% | 85.62% | 88.36% |
| Supplied v2 at 562 | 287 | 51 | 19 | 3,209 | 84.91% | 93.79% | 89.13% |

All rows use the same 3,566 previously inspected validation hours. The expanded arm gains six true positives and removes two false positives relative to its matched core. Against 008, it gains three true positives but adds five false positives, leaving F1 0.21 percentage points lower. Both arms fail the user's gate.

The expanded arm's F1 gain over supplied v2 at 600 is 2.06 percentage points. Its paired target-day bootstrap interval is +0.31 to +3.93 points. The matched expanded-minus-core interval is −0.07 to +2.88 points, and expanded-minus-008 is −2.47 to +2.15 points. These are descriptive intervals on reused historical validation and do not establish a fresh-test improvement or correct repeated model inspection.

## What the experiment changed

The underlying v2 configuration refit and its radiation predictions were reused from 016. Nothing was retrained in that base model. The original supplied v2 remains a separate reference. The common refit radiation MAE is 18.7007 W/m², compared with supplied v2's 18.6973 W/m². Event corrections do not change either curve or improve their regression errors.

The two heads use identical training rows and the same fixed, shallow LightGBM configuration. The core uses the v2 prediction, its original NWP context and deterministic solar/calendar features. The expanded head adds only ECMWF-minus-v2 radiation, GFS-minus-v2 radiation and their absolute disagreement. It never consumes 008 event bits or probabilities as an input.

This is a direct extension of the v2 prediction path. The trained expanded head uses `v2_margin` in 355 splits, ECMWF disagreement in 232, GFS disagreement in 83 and cross-forecast disagreement in 70. Full [feature importances](result/expanded-importance.csv) are retained. Split/gain importance is not a causal attribution. The matched arm comparison isolates the additional forecast features within this frozen configuration.

Training uses 10,675 common-coverage OOF hours. The 1,824 excluded early OOF origins are saved in [excluded-oof-origins.csv](inputs/excluded-oof-origins.csv). The two arms share exactly the same origins and purged forward-fold memberships. All validation hours remain included.

The pooled training-fold ECMWF control has 63 false positives. The core selected probability threshold 0.555, giving 62 training-fold false positives. Expanded selected 0.530, giving 61. Every threshold was selected from training-period forward predictions and saved before validation scoring. That training constraint did not guarantee the required validation false-positive count.

## Evidence and reproduction

- [Frozen protocol](PROTOCOL.md), [29-file source/input lock](lock.json), [input/source manifest](inputs/manifest.json) and [readable code guide](CODE-GUIDE.html).
- [Execution receipt](execution-001.json) and [complete log](execution-001.log). Exit 0, 3.52 seconds external wall time, 1.13 seconds measured inner wall time, 1.27 seconds CPU time, 211,550,208 bytes peak RSS. Fits were serial with a two-thread cap.
- [Four passing synthetic checks](preflight-tests.log) cover false-positive eligibility, no admissible policy, identical core features and strict chronology.
- [Policy freeze](result/policy-freeze.json) retains selected thresholds and hashes of all eight intermediate and two final head models before validation outcomes were parsed.
- [Exact metrics](result/summary.json), [all validation calls](result/validation-evaluation.csv), [paired daily-block intervals](result/day-bootstrap.json) and [output hashes](result/completion.json).

Each retained forecast value matches its raw archive at target = origin +24h, converted from the recovered fixed +03:00 labels to UTC epoch. The requests pin `ecmwf_ifs025` and `gfs_global`. All GFS cloud data are excluded. The original publication/issue timing of those archives remains unverified.

The existing astronomy function was replayed for each retained target. Its `solar_scale` floor is 100 W/m², including night. This is a fixed geometric feature, not a measured or calibrated clear-sky forecast.

To reproduce from the repository root, use the recorded dependency versions and a new output directory:

```sh
python3 -m unittest discover -s app/experiments/v2-017 -p test_run.py -v
python3 app/experiments/v2-017/run.py --out replay-001
```

The reproduction command is provided, not executed again. Existing results are never overwritten. No original test outcomes were scored, no post-result cutoff search occurred, and no claim or model update was sent to the team by this experiment.
