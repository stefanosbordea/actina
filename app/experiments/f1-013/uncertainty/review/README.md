# Independent paired-uncertainty review

PASS. The separate checker imports no production helper. It reconstructs all daily TP/FP/FN counts from the pinned 013 per-hour decisions, preserves the full 150-day validation and 149-day test calendars, and checks the exact satellite availability masks. All 20,000 saved circular block draws are recreated from the declared seed and order using explicit sampled-day lists. Each draw is shared across both references, six methods and all metrics.

Pooled sampled ratios are recomputed from integer totals with `Fraction` before binary64 display conversion. All 120 percentile intervals match an independent sorted linear-interpolation implementation exactly. All undefined-draw counts are zero. The 24 comparisons against raw have exact zero point differences, draw differences and interval endpoints. This confirms that the primary 013 arm changes nothing relative to raw in either period.

The retained run exited 0 in 4.03 external wall seconds and completed 7,550 checks. See `receipt-001.json`, `execution-001.log` and `result.json`. The reviewed `paired.py` hash is `b17fac79fc1246670da983f1adb34429d3ae3b094136454c60aa3c72664f8f18`.

These descriptive intervals do not create independent holdout evidence, account for repeated experiment selection or change the failed 013 admission gate.
