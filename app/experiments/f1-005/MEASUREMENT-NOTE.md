# Additional fixed diagnostics

Before execution, the review requested an exact CSV round-trip check for every guarded point and binary decision, plus counts at exactly 600 and its next binary64 neighbour. These diagnostics do not change the frozen rule or rows. Preserve the binary64 hexadecimal point representation as well as the decimal value, because rounding a positive floor to displayed 600 would erase its strict comparison.

For each reference basis, retain corrected/new false positives and false negatives relative to the raw analogue's original probability decision. Count raw-median disagreements separately. The output preserves a weather-proxy decision, not a physical-surplus safety guarantee. The term projection refers to nearest permitted binary64 values, not a nearest point in an open real half-space.

The reusable function accepts a validated threshold argument, default 600. The retained experiment uses 600 only. This is interface support, not a threshold search.

The supplied scheduler also ranks all forecast magnitudes to repair shortfalls (`model/scheduler.py`, lines 46 and 62–66). The correction can reverse order within the positive or negative class. It therefore preserves only the strict-threshold event calls, not dispatch, costs, water paths or the operational plan. This experiment does not feed corrected values into that scheduler or the demonstration.
