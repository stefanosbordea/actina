# Solar forecasts to water-production decisions

**The shuffled comparison improves all eight aggregate cost and grid-energy measures in both periods. Neither candidate passes the separate validation test for daily cost regret, so the research remains experimental.**

All 1,196 schedules were generated for 299 horizons before applying outcome masks. Each supplies 2,880 m³ under the same tank and production bounds, with 9,792 kWh of nominal total desalination energy. This is an illustrative retrospective PV/grid calculation, not observed plant savings or recovered curtailment.

The coherent candidate keeps 64 historical daily residual paths intact. The shuffled comparison has exactly the same hourly values, but rearranges their daily pairing. Both optimize the same worst-reference daily-cost-regret CVaR90 objective against a stronger solar-aware raw-forecast schedule. An existing tariff-led app schedule is retained as context.

## Measured outcome

Changes below are candidate minus raw solar-aware control. Negative is better. Each period uses identical complete horizons for both references: 139 validation and 144 test. Cost units are € per horizon and grid-energy units are kWh per horizon.

| Period | Reference | Candidate | Mean cost Δ | Cost CVaR90 Δ | Mean grid Δ | Grid CVaR90 Δ | Regret CVaR90 | Max regret | Worse horizons |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| validation | weather | coherent | -3.112 | -0.435 | -21.630 | -1.049 | +0.229 | +2.017 | 4 |
| validation | satellite | coherent | -3.228 | -0.436 | -21.968 | +0.489 | +0.146 | +0.986 | 3 |
| validation | weather | shuffled | -4.599 | -0.548 | -35.492 | -1.734 | +0.298 | +2.111 | 4 |
| validation | satellite | shuffled | -5.023 | -0.575 | -38.512 | -0.384 | +1.576 | +13.437 | 3 |
| test | weather | coherent | -3.698 | -5.327 | -24.812 | -42.178 | -1.046 | -0.091 | 0 |
| test | satellite | coherent | -3.983 | -5.088 | -23.698 | -34.028 | -1.171 | +0.076 | 1 |
| test | weather | shuffled | -8.657 | -12.046 | -64.775 | -98.406 | -2.895 | -0.770 | 0 |
| test | satellite | shuffled | -8.390 | -11.155 | -55.650 | -83.775 | -1.891 | +1.270 | 1 |

Coherent validation fails because satellite grid-energy CVaR increases by 0.489 kWh and both references' daily-regret CVaR values are positive. Shuffled passes the separate eight-axis mean/tail cost/energy gate in both periods, but it also has positive validation regret CVaR. Lower total-cost tails do not establish lower same-horizon regret tails. On test both candidates pass both gates, yet each still costs more on one satellite-reference horizon. No candidate is chosen after seeing these results.

Shuffled has lower mean cost than coherent in both periods under both references. Preserving the historical daily ordering therefore did not deliver the hypothesized benefit in this experiment. The [complete report](result/report.json) retains all signs, tails, extremes, comparisons and weather-only sensitivity on 148 complete horizons in each period.

Explicit solar/grid modeling matters more than this candidate change in the illustration. The tariff-led context's mean grid cost is €427.84/€452.13 on validation weather/satellite, versus €345.85/€400.28 for the raw solar-aware control. On test the corresponding figures are €129.38/€130.82 versus €20.41/€39.67. That context difference reflects an added physical modeling assumption and a different optimization objective. It is not evidence for coherent scenarios or a new forecasting model.

## Scope and controls

Production is 0–500 m³/h, demand 120 m³/h, tank 4,000 m³, reserve 800 m³ and initial/final stock 2,000 m³. The PV conversion is the declared assumption PV = min(1700, 1.7 × max(GHI, 0)) kW. Unlimited grid backup supplies production. No export revenue, spill benefit, plant ramp, startup, membrane, salinity or maintenance constraint is modeled. Lower grid purchases mean greater use of this assumed PV supply. Total desalination energy does not fall.

Endpoints D00–D23 describe preceding-hour intervals from D−1 23:00 through D23:00 on fixed UTC+03. They are not midnight-to-midnight physical days. All 24 endpoints share issue D−1 00:00. Historical publication times are unverified. The fixed prototype tariff is indexed by endpoint hour. Raw GHI and satellite estimates are references, not measured curtailed power.

Each period uses the latest 64 complete paired historical days before its earliest issue. Validation's bank spans 2025-10-01 through 2025-12-03. Test's 64 selected days span 2026-02-20 through 2026-05-01, excluding missing-reference days. Source ledgers preserve every inclusion and exclusion. Boundary and incomplete-satellite horizons were planned before being excluded from primary scoring.

The CVaR epigraph and fractional empirical tail calculation adopt Rockafellar and Uryasev. Joint-trajectory motivation follows Pinson et al. The more complete desalination constraints discussed by Hu and Konstantinou remain outside this model. The [protocol](PROTOCOL.md) identifies the primary papers and equations. Neither the optimization nor scenario construction is claimed as novel.

## How much room remains

A separate [perfect-information diagnostic](headroom/result/report.json) solves the cost and grid-energy minima using each realized reference trajectory. These unavailable future inputs provide lower bounds, not operating schedules. An independent formulation reproduced all 1,132 minima within 9.10e-13 and checked all 4,528 daily gaps.

On test, the raw schedule sits €16.97 and €27.82 per horizon above the weather and satellite cost bounds. Shuffled reduces those gaps to €8.31 and €19.43. On validation the corresponding raw gaps are €25.33 and €38.83, falling to €20.73 and €33.81. Cost and energy bounds are solved separately. The remaining gaps do not establish how much a feasible forecast improvement can recover.

An exploratory [calendar-block sensitivity analysis](uncertainty/result.json) keeps missing days in their original calendar positions and resamples both methods and references together. With seven-day blocks, shuffled test mean-cost changes have 95% percentile intervals of −€9.37 to −€7.98 for weather and −€9.53 to −€7.25 for satellite. All eight test intervals remain below zero. Both validation grid-energy tail intervals cross zero, and the positive validation regret tails remain. These post-result intervals do not correct repeated inspection or model selection. [Independent review](uncertainty/review/README.md) reproduces interval values within 2.76e-12 but finds the separate strict-sign resampling frequencies numerically unstable. Those frequencies remain in the original record and must not be interpreted as evidence of superiority.

## Execution and reproduction

Eight analytical preflight tests passed, including negative and fractional-tail CVaR, solar allocation, equal marginals, different daily tails, water conservation, infeasibility, strict source chronology and deterministic solves. Original preflight failures remain in attempts/preflight-001. Integer-tenths weights repaired a one-ULP constant-loss result. A declared €1e-5/day action floor prevents meaningless numerical plan changes. Anchor fallbacks report their optimum gaps separately and do not claim the tighter €1e-7 optimized-plan cap. Independent water checks use 1e-6 m³ numerical tolerance, not exact physical certification.

The actual run exited 0 after 190.454 seconds, using 131.674 seconds of process CPU time and a 177,537,024-byte process peak RSS on Darwin. The solver used one thread. No model training, network retrieval or new dependency was used. The [execution receipt](run-receipt.json) retains exact commands and hashes.

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/test_optimizer.py
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/run.py --out app/experiments/physical-011/reproduction
```

The reproduction directory must be new. Source/code hashes are checked before running. Per-period files retain every schedule, bank ID, unclipped scenario, shuffled permutation, source time, modeled cost/energy replay, realized daily outcome and exclusion. All plans were hashed in planning-freeze.json before scoring.

The original bank archives contain an object-typed timestamp member. They remain untouched. Use [portable copies](portable/receipt.json) to load every member with allow_pickle=False. The standalone export utility reconstructs Unicode timestamps from numeric source positions and the pinned target CSV without unpickling. Every numerical member is identical. Its separate execution receipt records this metadata-only export. The [independent audit](review/result.json) passed 197,353 checks, reconstructing 1,837,056 scenario values and all 1,196 water plans. The maximum exact binary64 water-constraint residual was about 1.71e-12 m³, retained separately from the 1e-6 m³ numerical tolerance. Portable copies passed independent numerical and timestamp identity checks without unpickling.
