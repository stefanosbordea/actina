# Historical satellite reference

The existing SARAH3 archive already covered the full training period. **No additional data request was made.** The retained raw response reconstructs the original reference CSV byte for byte; existing validation/test reference files remain unchanged.

| Exact 006 membership | Total hours | Satellite available | Missing |
|---|---:|---:|---:|
| Validation training | 10,675 | 10,675 | 0 |
| Test training | 14,241 | 14,094 | 147 |
| All feature targets | 17,832 | 17,635 | 197 |

Training membership uses the unchanged 006 target-before-first-evaluation-origin rule. The first target is 15 September 2024, 21:00 UTC. Validation training ends 4 December 2025, 15:00 UTC; test training ends 2 May 2026, 05:00 UTC. All feature targets end 28 September 2026, 20:00 UTC.

`result/joined-reference.csv` retains every original row, with `feature_time`, `target_time`, `valid_time_utc`, `interval_start_utc`, `weather_actual_w_m2`, `satellite_w_m2`, `is_missing`, `validation_training` and `test_training`. Satellite nulls remain blank; membership flags are 0/1. No event labels, forecasts, scores or fitted models are produced here.

The 147 missing test-training values span 13–14 February, 15–19 March and 31 March–1 April 2026: 25, 97 and 25 hourly endpoints respectively. The additional 50 missing values are in July, outside either training set. Exact UTC endpoints and every missing row are retained in `result/report.json` and `result/missing-reference.csv`.

Original target labels are fixed UTC+03, as previously verified; seasonal DST is not applied. Target time must equal origin plus 24 hours. Radiation is the mean over the preceding hour, so the timestamp is its interval endpoint. All joins, intervals and purged training memberships were checked exactly.

Source: **EUMETSAT CM SAF SARAH3, served by Open-Meteo**, requested at 34.7744° N, 32.4229° E; returned grid 34.75° N, 32.4° E, elevation 71 m. The fixed request uses `models=eumetsat_sarah3`, `shortwave_radiation`, GMT and Unix time, 13 September 2024 through 1 October 2026. The original response finished at **2026-10-04T09:01:58.890135Z**. `result/provenance.json` pins the request, HTTP headers, response, full CSV and every input hash.

This is satellite-derived irradiance, not local ground-sensor truth. Historical publication times remain unverified. The official documentation gives inconsistent SARAH3 delay labels (one day in the selector, two days in the source table), so the target-before-origin rule alone does not establish that a label was available then. Any downstream use must retain this retrospective limitation.

Primary references: [Open-Meteo Satellite Radiation API](https://open-meteo.com/en/docs/satellite-radiation-api), [SARAH3 product DOI](https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003).

Reproduce into a new directory from the repository root:

```sh
python3 -B app/experiments/reference-training-001/prepare.py --output app/experiments/reference-training-001/NEW-RESULT
```

The preparation refuses an existing output and verifies pinned input hashes before and after the join. It uses the standard library and the existing source-schema checker, without network access, package installation or changes outside this experiment.
