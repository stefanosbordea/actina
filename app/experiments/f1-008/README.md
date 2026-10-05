# Two weather sources, separate correction thresholds

**Five of six test metrics improve; weather precision regresses. No replacement.** The complete run and independent saved-model replay passed. The selected correction does not meet the requirement to improve without sacrificing another metric.

| Test reference | Method | Precision | Recall | F1 | False alarms | Misses |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Weather, 3,567 hours | ECMWF control | 98.512% | 98.317% | 98.414% | 15 | 17 |
| Weather, 3,567 hours | Selected two-source correction | 98.417% | 98.515% | 98.466% | 16 | 15 |
| Satellite, 3,517 hours | ECMWF control | 95.766% | 97.436% | 96.594% | 42 | 25 |
| Satellite, 3,517 hours | Selected two-source correction | 95.879% | 97.846% | 96.853% | 41 | 21 |

## Mechanism and result

008 is a separate experimental event predictor for the same Aktina project. It reuses the project's weather data and evaluation periods, adds archived ECMWF/GFS information and trains fresh LightGBM models. It does not load or continue Stefanos's trained weights, and his model's predictions are comparison controls rather than input features. The selected arm fits a cross-entropy LightGBM regressor to weather/satellite event targets, then applies the saved correction rule. This is research modelling alongside the evaluation work, not merely a tool that calculates F1. It uses an established learning method informed by academic research, not a new learning algorithm invented from scratch.

NOAA GFS radiation adds target-day information to the existing ECMWF-based features. The learner also sees the difference between the forecasts and its magnitude. A second decision rule permits separate score thresholds for adding and removing ECMWF's high-solar calls. These scores are not proven calibrated confidence estimates.

Four fixed arms distinguish information from decision policy: weather-only or joint-reference training, each with and without GFS. The two no-GFS arms reuse saved models' probabilities. Every arm receives the same 121-pair validation policy search. Only four new fits were needed. No source, configuration, seed or cutoff was changed after the test.

Validation selects joint-reference training with both weather sources. Keep an existing positive call when its score is above 0.50; add a positive call only above 0.60. On the test this changes seven calls. Against weather, it corrects four misses, adds one false alarm and introduces two misses. Against satellite, it corrects four misses, removes two false alarms and adds one false alarm. Both explanations refer to the same seven changes.

The matched joint-reference arm without GFS falls back to unchanged ECMWF. Thus this selected policy's additional-source comparison has the same failed six-metric result as its ECMWF comparison. The unselected weather-only two-source arm removes one false alarm but adds one miss on each reference. It is not substituted after observing the test.

Raw GFS and the fixed mean of GFS/ECMWF also remain in the report as diagnostic baselines. Their test F1 is lower than ECMWF's on both references. A second forecast is not automatically a better forecast; its role must be learned and measured.

## Evidence

- [Frozen protocol](PROTOCOL.md), [113 pinned inputs](inputs.json), [actual execution receipt](run-receipt.json), [complete report](result/report.json).
- [Selection frozen before test](result/validation-selection.json), all four validation grids, saved weights and per-hour probabilities/decisions in `result/`.
- [Independent checker](review/check.py) and [review result](review/result.json): all 17,832 feature rows, 24,916 labels, 28,532 prediction rows, 484 policy pairs and 1,536 metric records reconstructed; all four saved models replay with zero probability error.
- [GFS intake](../nwp-alternative-001/README.md): every target has valid radiation. Eight invalid cloud percentages remain in the raw response; the entire cloud column was excluded before scoring.
- [Full-paper reading and implementation links](../research-2026-10-04/full-pdf-followthrough.md).

Run from the repository root with the existing NumPy/pandas/LightGBM environment:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 python app/experiments/f1-008/run.py --output app/experiments/f1-008/NEW-RESULT
```

The runner refuses existing outputs or changed inputs. `test_policy.py` covers strict boundaries, both correction directions, an unchanged perfect control, conflicting references and missing satellite values.

This is an exploratory comparison on historical hours inspected in earlier experiments. Weather and satellite are estimates, with shared upstream dependencies; neither is local sensor truth. Historical publication availability remains unverified. No result here establishes live forecast superiority, actual curtailed energy, operating savings, statistical significance or scientific novelty. Original `model/`, `data/`, `eval/`, product and delivery files remain unchanged.
