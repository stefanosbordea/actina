# Aktina forecast research

**4 October 2026. Research results; no model replacement.** Stefanos's original `model/`, `data/` and `eval/` remain unchanged. The website still presents the supplied demonstration. These experiments are separate and retain unsuccessful candidates.

## What improved

The strongest change so far is adding the archived numerical weather forecast. The original predictor largely extrapolates historical weather; tomorrow's weather forecast adds information about the target day. A fixed day2 forecast improves the retained test precision, recall and F1 over both the original predictor and previous-day persistence. The paired day-block intervals for the differences versus persistence still include zero. No corresponding interval against the original predictor was computed. This is an exploratory result, not established live superiority.

A conditional residual prototype then looks up 64 earlier hours with similar forecast radiation, cloud and solar geometry. It transfers their forecast errors to the target hour, producing a median, event probability and empirical interval. The solar-scaled variant changes only the error scaling. These are adaptations of published analogue-ensemble and forecast-postprocessing methods, not a claim to have invented the field. [Research and primary sources](research-2026-10-04/solar-synthesis-review.md).

Against the original weather-model reference, raw residual analogues lower test MAE from **8.806 to 6.921 W/m²**. A retrospective paired day bootstrap puts the reduction at **1.693–2.065 W/m²** (95% percentile interval). But they add one false alarm versus the fixed weather forecast and fail the validation precision gate. Experiment 004 therefore retains the fixed forecast; it does not promote the analogue.

## A different reference changes the numbers

The original targets come from a weather-model/reanalysis archive, not a local irradiance sensor. We scored the exact same frozen predictions against pinned SARAH3 satellite estimates, without refitting or choosing a new cutoff. The table below uses the **same 3,517 test hours** for every method. Fifty reference-null hours remain explicitly unscored; they are not imputed.

| Fixed method | Precision | Recall | F1 | MAE, W/m² | False alarms / misses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original predictor | 94.553% | 94.359% | 94.456% | 25.351 | 53 / 55 |
| Previous-day persistence | 95.147% | 96.513% | 95.825% | 22.094 | 48 / 34 |
| Archived day2 forecast | 95.766% | 97.436% | 96.594% | 19.325 | 42 / 25 |
| Raw residual analogues | 95.670% | 97.436% | 96.545% | 18.227 | 43 / 25 |
| Solar-scaled analogues | 95.578% | 97.538% | 96.548% | 18.272 | 44 / 24 |

The raw analogue's MAE reduction survives this reference substitution but narrows to **1.098 W/m²**, about **5.7%**. Its extra false alarm remains. No satellite-specific confidence interval or significance claim is made. The original weather-reference 21% reduction must not be presented as a measured field gain.

All eight methods, both periods, the full original reference, the common-hour original reference and the common-hour satellite reference are retained in the [reference comparison](reference-sensitivity-001/README.md). Validation is materially harder: fixed day2 F1 is **80.708%** against satellite estimates, versus **90.586%** against the original reference on identical available hours. The favorable test season is not the whole performance record. Satellite estimates are another reference, not ground-station truth; agreement does not prove recovered curtailment or plant savings.

## Evidence and next test

| Work | Result and retained evidence |
| --- | --- |
| [001: fixed challengers](f1-001/README.md) | Includes a neural classifier; no all-metric test win over persistence. |
| [002: purged linear models](f1-002/README.md) | Lower error in one history model; selected classifier loses recall. No promotion. |
| [003: archived weather inputs](f1-003/README.md) | Fixed forecast improves test point scores; selected learned classifier loses required precision. No promotion. |
| [004: conditional residual synthesis](f1-004/README.md) | Error and uncertainty experiments; validation retains the fixed forecast. Independent reconstruction and paired-day audit retained. |
| [Reference substitution](reference-sensitivity-001/README.md) | Scores every fixed method on a different reference; no fitting or reselection. Independent recomputation checks all 48 method/period/reference comparisons. |
| [Prospective capture](prospective-001/README.md) | Future forecasts captured on 4 October before the declared target periods. Outcomes are not available yet. |

The prospective test uses two previously fixed 24-hour sets. Satellite retrieval becomes eligible on **8 October and 9 October at 09:00 UTC** respectively. The raw forecast and two fixed analogue variants are locked before those target intervals. Exact timestamps, hashes, training memberships and source errors are retained. These two short sets test transfer to a live capture; they cannot establish year-round superiority.

## Research direction

Synthesis is useful for expressing uncertainty, normalizing known physics and reusing scarce real observations. It does not create independent weather measurements. Rematerialization saves working memory by recomputing intermediate values; it cannot recover tomorrow's unknown clouds.

For Aktina's water-storage idea, the next useful extension is coherent daily error trajectories, followed by a comparison of water service and energy use under the same physical constraints. Independent hourly scenarios from 004 are not sufficient for that test because they do not preserve cloud persistence. Actual surplus electricity also depends on grid/load conditions; radiation above 600 W/m² is only the current proxy. Forecast improvement, schedule feasibility and physical savings require separate evidence.
