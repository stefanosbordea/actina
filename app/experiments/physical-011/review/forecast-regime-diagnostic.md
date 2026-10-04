# Forecast coverage of the frozen error banks

The frozen 64-day banks do not cover much of the forecast supply range where they are applied. This is a limitation of unconditional historical-error transfer, independent of the LP implementation. It does not establish a change in the error distribution or explain the realized results.

Only raw archived NWP values, source indices and timestamp columns enter this diagnostic. No reference value, residual, candidate production or realized cost enters a calculation. All 299 planned horizons remain, including boundary and missing-satellite horizons.

## Measured coverage

The diagnostic ratio is total illustrative forecast PV energy divided by the fixed 9,792 kWh production load. It uses exactly the frozen conversion `P = min(1700, 1.7 × max(GHI, 0))`. A ratio of one means equal total modeled supply and load. Timing, storage and rate limits can still require grid purchases.

| Period | Historical bank range | Target range | Bank median | Target median | Below bank minimum | Above bank maximum |
|---|---:|---:|---:|---:|---:|---:|
| Validation, 150 horizons | 0.373–0.949 | 0.187–1.269 | 0.680 | 0.638 | 15 | 29 |
| Test, 149 horizons | 0.616–1.269 | 0.276–1.473 | 0.932 | 1.329 | 1 | 95 |

Thus 44 of 150 validation horizons and 96 of 149 test horizons lie outside their bank's observed descriptor range. All 30 June and 31 July test horizons exceed the test-bank maximum. In validation, April has 24 of 30 horizons above the bank maximum, while December has seven and January five below the minimum. These comparisons are forecast-to-forecast, not forecast-to-realized-weather.

The bank is frozen for an entire period. At the last issue, its newest source endpoint is 3,577 hours old on validation and 3,553 hours old on test. This is the declared design, not a time-leakage defect. It combines an autumn bank with winter-to-spring target forecasts, and a late-winter/spring bank with summer target forecasts. The forecast ranges demonstrate different supply conditions. They do not show that conditioning will improve errors, tails or decisions.

[Every horizon](forecast-regime-horizons.csv) retains its ratio, empirical bank rank, nearest descriptor gap, out-of-range flags and source age. [All 128 bank days](forecast-regime-bank.csv) retain their forecast descriptors. The [summary](forecast-regime-diagnostic.json) includes monthly coverage and exact source hashes.

## One proposed conditional descriptor

For a prospective bounded comparison, use the cumulative forecast PV curve in water-equivalent units:

`F[h] = sum(P[0:h+1]) / 3.4`, in m³.

Select the nearest 64 eligible historical days by `mean(abs(F_history − F_target))`. This single, unweighted descriptor reflects both total available energy and its timing relative to the tank's cumulative water balance. The scalar supply/load ratio above is a coverage diagnostic, not a competing tuned candidate. No candidate using either descriptor has been fitted or scored here.

Use raw archived NWP for both curves. Keep the original period's earliest-issue cutoff, complete paired historical days, 64 scenarios, physical constraints, tariff, raw-point baseline and optimizer unchanged. Candidate selection considers all eligible historical days before that cutoff. Break exact computed-distance ties by earliest source day, with no fitted near-tie tolerance. Preserve all distances, ranks and selected IDs. Do not update the pool using evaluation outcomes or availability.

This is a physically motivated distance, not a learned metric or a claim that forecast similarity implies identical error laws. It omits weather variables, forecast vintage changes, residual calibration and plant physics absent from 011. A cumulative curve can distinguish equal-energy morning and afternoon supply patterns that the scalar ratio cannot. The chosen equal weighting is a fixed hypothesis, not an established optimum.

## Separating two mechanisms

Use a fixed two-by-two comparison: recency bank versus conditional bank, each with intact versus shuffled daily paths. Within each bank, apply the same frozen per-hour permutations to both reference families. Exact hourly marginals must match before and after shuffling. The same fixed plan must therefore have equal expected hourly-sum cost under both families, while daily tails may differ.

Comparing recency with conditional banks tests the combined change in selected error marginals and their historical paths. Comparing intact with shuffled paths within the same bank isolates temporal arrangement while retaining those marginals. It does not prove calibration or causal field value. Keep all four outputs and both validation/test gates, with no retrospective choice of a winning arm. Reproduce the old recency controls to rule out implementation drift.

The proposal follows inspection of 011 and is explicitly exploratory. It is not an independent confirmation. Academic review of analogous conditioning methods is being prepared separately. This note makes no novelty or superiority claim.

## Reproduce

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/review/forecast_regime_diagnostic.py
```

The script refuses to overwrite its generated diagnostic files. It checks frozen source hashes, raw forecast identity and nominal issue chronology. Original files remain unchanged. Historical publication availability remains unverified, so nominal timestamp compliance is not a live-availability certificate.
