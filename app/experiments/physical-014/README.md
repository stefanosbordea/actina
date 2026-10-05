# Event-to-water interface 014

The declared interface produces **no physical upgrade**. Both conditional arms reproduce the raw-point plan exactly in both periods. All four arms reproduce raw point on every test horizon. No model, product, tariff or plant assumption was changed.

## What ran

Each frozen 013 event vector was converted to the nearest binary64 irradiance vector consistent with its strict `>600` calls, then passed through the unchanged 011 solar-aware point optimizer. Consistent raw values stayed unchanged. Added events used the next binary64 value above 600. The [protocol](PROTOCOL.md) and [design proposal](../research-2026-10-04/forecast-water-link.md) were fixed before the run. All four arms and all six 012 controls were retained.

All 299 horizons and 2,990 plan records were saved and hashed before scoring references or masks were opened. These include 1,196 mapped candidate records. An unchanged input copies the archived raw plan exactly. All 299 raw-point reproductions are bitwise identical. The 56,160 numeric comparisons against archived control outcomes also match exactly.

Every plan uses the same 2,880 m³ water target and 9,792 kWh nominal desalination energy. Common physical scoring retains 139 validation and 144 test days under weather and satellite separately. Weather-only sensitivity retains 148 days in each period. All original-hour forecast diagnostics remain in the report.

## Results

| Arm | Validation mapping changes | Test mapping changes | Physical upgrade gate |
|---|---:|---:|---|
| Recency robust | 2 hours | 0 | Fail |
| Recency pooled | 2 hours | 0 | Fail |
| Conditional robust, primary | 0 | 0 | Fail |
| Conditional pooled | 0 | 0 | Fail |

The two recency policies change the same validation hours on 2 May 2026. Raw GHI values 594 and 592 W/m² become the next binary64 value above 600. Their maximum hourly production difference from raw is `4.3076473191548193e-13` m³. The largest common-day weather cost increase is `1.1368683772161603e-13` euros, and the largest grid increase is `9.094947017729282e-13` kWh. The satellite cost and grid values equal raw. These positive signs remain in the saved strict gates. They are below the declared numerical reporting thresholds and provide no usable benefit.

Both conditional interfaces equal raw, so they also lose the mean cost and grid advantages already observed for the stronger 012 controls. The following shows primary 014 minus each conditional 012 control on matched common days. Positive differences favor the 012 control.

| Period | 012 control | Weather mean cost Δ € | Satellite mean cost Δ € | Weather mean grid Δ kWh | Satellite mean grid Δ kWh |
|---|---|---:|---:|---:|---:|
| Validation | Conditional intact | +5.033 | +5.062 | +36.337 | +34.802 |
| Validation | Conditional shuffled | +5.763 | +6.344 | +45.377 | +48.996 |
| Test | Conditional intact | +7.389 | +9.439 | +47.317 | +56.385 |
| Test | Conditional shuffled | +10.745 | +14.604 | +76.313 | +94.688 |

The [full report](result/report.json) retains all five non-tariff controls, eight-axis aggregate gates, separate daily-regret gates, every candidate and both references. This does not retrospectively promote 012, whose original validation regret failures remain unchanged. Continuous MAE/RMSE and exact event metrics against raw NWP, original and persistence are separate diagnostics.

## Verification and reproduction

Twelve analytical fixtures pass. Independent preflight found an incorrect assumption about the source's missing-value flags before historical execution. The loader now strictly verifies `0`/`1`, both source feature clocks and the UTC interval. The [preflight findings](review/preflight-findings.md), initial and final test receipts are retained. No failed historical attempt was needed.

The frozen [input manifest](inputs.json) pins 69 files. The [actual run receipt](run-001-receipt.json), [stdout](run-001.log), [planning freeze](result/planning-freeze.json) and [execution receipt](result/execution-receipt.json) distinguish prepared code from executed work. The study returned actual exit 0, with 3.977 seconds internal wall time, 3.897 CPU seconds and 160,350,208 bytes peak RSS on the Mac. No energy measurement was made.

Run with the existing pinned Python environment from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python app/experiments/physical-014/test_link.py -v
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 python app/experiments/physical-014/run.py --execute-historical --out app/experiments/physical-014/reproduction-001
```

The runner refuses existing output directories and changed pinned sources. All water plans have numerical and exact rational replays. The largest exact constraint residue is `15/8796093022208` m³, about `1.71e-12` m³, below the frozen tolerance and retained explicitly. The [independent outcome audit](review/README.md) passes 499,433 checks over all 2,990 plans, masks, event mappings, physical metrics and gates.

The original interface proposal preceded the 013 results. The final 014 implementation and protocol were completed after the primary 013 raw-identity result was communicated, then frozen before any 014 outcome scoring. Thus the full implementation was not blind to 013. No arm, mapping or control changed from the earlier proposal.

## Interpretation

The result rejects this specific event-to-irradiance interface as an upgrade. Binary calls do not determine a calibrated radiation magnitude. The mapping was a declared reproducible choice, not a physical consequence of F1 improvement. No amplitude margin, policy or comparator was revised after scoring.

The primary papers cited in the proposal support evaluating induced decisions and keeping plant constraints explicit. No scientific novelty follows from this interface. These historical estimated references, illustrative PV conversion, unlimited grid backup and simplified plant do not establish actual curtailed-energy recovery, live availability or field savings.
