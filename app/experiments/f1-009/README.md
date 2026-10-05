# Bernstein quantile network

**The selected joint BQN passes all six predeclared event metrics against raw NWP, but does not dominate the other candidates or every numerical metric.** It produces a net one fewer missed event with unchanged aggregate false alarms under each test reference. Weather-reference median MAE rises from 8.8057 to 8.9111 W/m². Against experiment 008's frozen selected policy, five of six event metrics regress. These are narrow retrospective results. The product remains unchanged.

The model is a genuine Bernstein quantile network with a tanh hidden layer, ordered softplus coefficient increments, lower censoring and mean pinball training. This is an adaptation of prior work, not a new algorithm: [Mayer et al., §3.2.3 and §4.1](https://arxiv.org/pdf/2508.15508), following Bremnes (2020). Their PV-power study motivates this test. Our irradiance inputs, two reference sources and small fixed CPU model differ from that study.

## Fixed event comparison

Validation selected the joint arm and froze the correction policy at lower 0.50 / upper 0.65 before the test pass. The weather-only arm admitted no qualifying correction and retained NWP decisions. The selected joint test policy has six strict improvements, no equalities and no regressions against raw NWP. Three test calls change: two additions and one removal. Each reference gains one true positive, removes one false alarm and adds another false alarm. The added hours disagree between the two references. The precision gains are very small. Not every individual correction is right.

| Reference | Method | Precision | Recall | F1 | False alarms | Misses |
|---|---|---:|---:|---:|---:|---:|
| Weather full (3,567) | Raw NWP | 0.985119 | 0.983168 | 0.984143 | 15 | 17 |
| Weather full (3,567) | Joint BQN | 0.985134 | 0.984158 | 0.984646 | 15 | 16 |
| Satellite common (3,517) | Raw NWP | 0.957661 | 0.974359 | 0.965938 | 42 | 25 |
| Satellite common (3,517) | Joint BQN | 0.957704 | 0.975385 | 0.966463 | 42 | 24 |

The comparison with the frozen 008 policy is also retained: only weather precision improves. Weather recall/F1 and satellite precision/recall/F1 regress. Passing the raw-NWP gate does not override that result. Original and persistence controls, both BQN arms and their default p>.5 decisions remain in `result/report.json`.

## Distribution scores

All errors and widths below are W/m². CRPS is the explicitly labelled approximation from twice the mean pinball loss over 51 levels k/52. It is not exact continuous-distribution CRPS. NWP is treated as a degenerate distribution for this comparison, not as a supplied probabilistic forecast. Its zero-width interval is not a 90% predictive interval, so the coverage numbers alone are not a calibration comparison.

| Period | Reference | Method | Approx. CRPS | Median MAE | Mean RMSE | Interval coverage | Width |
|---|---|---|---:|---:|---:|---:|---:|
| validation | Weather full | NWP point mass | 17.693 | 17.693 | 45.420 | 0.521 | 0.000 |
| validation | Weather full | Weather BQN | 13.506 | 16.523 | 44.374 | 0.895 | 47.573 |
| validation | Weather full | Joint BQN | 14.760 | 17.236 | 45.815 | 0.955 | 105.829 |
| validation | Satellite common | NWP point mass | 33.818 | 33.818 | 73.109 | 0.507 | 0.000 |
| validation | Satellite common | Weather BQN | 28.062 | 33.613 | 73.490 | 0.734 | 47.408 |
| validation | Satellite common | Joint BQN | 24.226 | 32.100 | 71.388 | 0.900 | 105.513 |
| test | Weather full | NWP point mass | 8.806 | 8.806 | 22.800 | 0.421 | 0.000 |
| test | Weather full | Weather BQN | 5.862 | 7.518 | 21.685 | 0.909 | 27.424 |
| test | Weather full | Joint BQN | 7.390 | 8.911 | 22.490 | 0.990 | 63.490 |
| test | Satellite common | NWP point mass | 19.325 | 19.325 | 44.948 | 0.404 | 0.000 |
| test | Satellite common | Weather BQN | 15.776 | 18.781 | 44.906 | 0.662 | 27.541 |
| test | Satellite common | Joint BQN | 12.247 | 15.660 | 43.527 | 0.950 | 63.725 |

The joint test interval covers 98.99% of weather-reference values and 95.00% of available satellite values despite nominal 90% endpoints. Do not claim calibrated 90% coverage. Both mean/median and probabilistic results, including weather-common rows, are retained. All original 3,566 validation and 3,567 test rows remain; 147 validation and 50 test satellite values are unscored rather than filled. No quantile crossings exceeding 1e-9 W/m² were found. The coefficients are ordered algebraically. Lower censoring preserves that order.

## Model and execution

One fixed architecture: 27 unchanged 008 inputs, tanh 16, degree 12 and 669 parameters. Each split fits imputation means and population scales using only its purged training rows. An ECMWF location skip initializes the median at raw NWP. Softplus increments define the ordered coefficients and are centered at their Bernstein median. Predictions retain all 13 coefficients, 51 quantiles, zero mass, median, analytically integrated censored mean, interval endpoints and P(Y>600) from 60-step monotone inversion. Coefficients use internal kW/m² units. Saved quantiles, mean, median and interval endpoints use W/m².

The weather arm trains on weather-reference pinball loss. The joint arm averages the two separate reference losses where both are present and uses weather alone otherwise. It never averages irradiance labels before applying the loss. These references are estimates. Mixture training does not identify physical truth or establish their independence.

All four fits completed the fixed 200-iteration budget. **None reported optimizer convergence.** The finite returned iterates, statuses, objective values, gradient norms and evaluation counts are retained. There was no restart, seed search, test-directed change or additional fit. Lower censoring can produce flat gradients. The architecture and budget are limitations of this measured run.

The four fits took 42.64 wall seconds and 24.77 process CPU seconds in total, with process peak resident memory 200,392,704 bytes on the 8 GiB Apple M1 development host. These observations include its current host conditions and are not a matched performance benchmark. Execution used existing NumPy/SciPy, CPU only, thread limits at most 2, and no installation. The reused 008 decision helpers import existing LightGBM/pandas transitively. No tree model was fitted here.

Four preflight tests passed before fitting: finite differences for all 669 parameters in both objectives. Hand pinball arithmetic that distinguishes separate-reference loss from an averaged target. Coefficient/quantile monotonicity, threshold/zero-atom inversion and censored mean against numerical integration. And training-only scaling/missing-reference fallback. Both the initial three-test and final four-test logs remain. Independent replay belongs under `review/`.

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python -m unittest discover -s app/experiments/f1-009 -p test_bqn.py -v
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/f1-009/run.py --output app/experiments/f1-009/NEW-RESULT
```

Use the existing environment with NumPy, SciPy, pandas and the prior experiments' installed dependencies. The runner refuses existing outputs and changed pinned inputs. Saved weights/scalers and distributions use NPZ without pickle. Protocol, 20 pinned inputs, validation selection, original rows, all fitted outputs and execution identities are retained.

## Independent review

The [independent audit](review/result.json) passed without fitting. It reconstructed all four networks from saved weights, checked 14,266 prediction rows and 727,566 quantiles, recomputed 242 validation policy pairs and verified all 1,338 gradient coordinates. Independent polynomial evaluation and inversion reproduced every frozen event decision. The largest probability difference was 1.07e-14 and the largest gradient difference was 8.08e-12. The [execution receipt](review/execution-receipt.json) records the command, exit status and file identities.

The audit confirms the narrow result above. It does not establish a meaningful gain beyond sampling variation, an independent holdout result, or superiority over experiment 008.

The [paired resampling sensitivity check](review/uncertainty-result.json) reinforces that limit. With seven-day blocks, the weather F1 difference is **+0.050 percentage points**, with a marginal 95% percentile interval of **−0.101 to +0.207**. The satellite F1 difference is **+0.053 points**, interval **−0.100 to +0.219**. Both precision intervals also cross zero. One-day blocks give the same qualitative result. These post-inspection intervals do not correct the repeated use of this historical test or establish future improvement. The [declared method](review/uncertainty-protocol.md), daily counts and [execution receipt](review/uncertainty-receipt.json) remain available.

This experiment was motivated by an already-inspected test. Historical data publication availability remains unverified. There is no live validation, guarantee of future gains, physical-surplus safety, measured curtailment recovery, water-service or savings claim. Stefanos's original model/data/evaluation roots and all competition deliverables remain unchanged.
