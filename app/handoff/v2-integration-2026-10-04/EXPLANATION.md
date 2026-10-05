# What 019 changes

It builds directly on Stefanos’s v2, not on 008.

1. **Stefanos’s part:** the nine v2 inputs and LightGBM design predict next-day radiation, including NWP radiation and cloud cover. His source is merged unchanged.
2. **The extension:** refit that design using an early-stopping window inside training, then keep that radiation curve fixed. It is a new fit of his design, not his exact supplied fitted weights.
3. **The correction:** one logistic model with 15 weights uses the v2 prediction, weather forecasts, calendar/solar features and past errors to decide whether an hour will exceed 600 W/m². Only observations resolved before each forecast origin enter its past-error inputs. The event cutoff was selected from earlier training predictions.
4. **Loukas’s contribution:** matched-hour evaluation, comparison controls, the v2-based event correction, independent replay evidence and the website integration. 008 remains a separate research comparator.

| Same 3,566 validation hours | Precision | Recall | F1 | False alarms | Misses |
|---|---:|---:|---:|---:|---:|
| Supplied v2 | 91.29% | 85.62% | 88.36% | 25 | 44 |
| 008 | 92.81% | 88.56% | 90.64% | 21 | 35 |
| V2 + correction 019 | 94.08% | 88.24% | 91.06% | 17 | 36 |

019 beats 008’s observed validation F1 and precision, with four fewer false alarms and one additional miss. It improves all three event scores against supplied v2. The gain over 008 is small, its uncertainty interval includes zero, and validation has been reused. It is not an established win on unseen data. Numeric radiation error and operating savings did not improve through this correction.

[Stefanos’s code and refit screenshot](screenshots/019-stefanos-v2-code.png) · [Correction screenshot](screenshots/019-event-correction-code.png) · [Exact code walkthrough](../../experiments/v2-019/CODE-GUIDE.html) · [Full method and audit](../../experiments/v2-019/README.md)
