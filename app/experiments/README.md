# Aktina forecast research

**4 October 2026. Research results; no model replacement.** Stefanos's original `model/`, `data/` and `eval/` remain unchanged. The website still presents the supplied demonstration. These experiments are separate and retain unsuccessful candidates.

## What improved

The strongest change so far is adding the archived numerical weather forecast. The original predictor largely extrapolates historical weather; tomorrow's weather forecast adds information about the target day. A fixed day2 forecast improves the retained test precision, recall and F1 over both the original predictor and previous-day persistence. The paired day-block intervals for the differences versus persistence still include zero. Experiment 005 below separately compares its constrained correction with the original predictor. These are exploratory results, not established live superiority.

A conditional residual prototype then looks up 64 earlier hours with similar forecast radiation, cloud and solar geometry. It transfers their forecast errors to the target hour, producing a median, event probability and empirical interval. The solar-scaled variant changes only the error scaling. These are adaptations of published analogue-ensemble and forecast-postprocessing methods, not a claim to have invented the field. [Research and primary sources](research-2026-10-04/solar-synthesis-review.md).

Against the original weather-model reference, raw residual analogues lower test MAE from **8.806 to 6.921 W/m²**. A retrospective paired day bootstrap puts the reduction at **1.693–2.065 W/m²** (95% percentile interval). But they add one false alarm versus the fixed weather forecast and fail the validation precision gate. Experiment 004 therefore retains the fixed forecast; it does not promote the analogue.

Further implementations are complete and independently checked:

- **005, constrained correction:** retain the archived forecast's event calls while correcting its numerical values. Weather-test MAE is **6.918**, with unchanged precision **98.512%**, recall **98.317%**, F1 **98.414%**, 15 false alarms and 17 misses. The correction changes only three raw-analogue test values; it does not learn better event decisions. Satellite-validation numerical error worsens, so it is not a general replacement.
- **006, learned event classifier:** add solar geometry and strictly past forecast-error context. The validation-selected model catches one additional weather-test event with no additional false alarm: **994 TP, 15 FP, 16 FN**, F1 **98.465%**. Against the satellite test reference, all three classification measures worsen. The higher test F1 of a different candidate does not change the validation selection.
- **007, joint-reference supervision:** train against both weather and satellite event estimates. Test recall and F1 improve under both references, but precision worsens under both. No replacement.
- **008, additional GFS information and separate correction thresholds:** the selected candidate improves five of six test precision/recall/F1 measures. Satellite improves throughout; weather precision falls from **98.512% to 98.417%**. Its extra false alarm disqualifies an all-metric upgrade. All four saved models replay exactly in independent checks.

For the user's direct comparison with the original model, 005 reduces weather-test mistakes from **69 to 32** and MAE from **14.266 to 6.918 W/m²** on identical hours. Its exploratory paired-day F1 difference is **+1.866 percentage points**, with a marginal 95% interval of **+0.924 to +2.957**. Against satellite estimates on identical common hours, the F1 difference is **+2.138 points**, interval **+1.148 to +3.266**. Both test precision intervals include zero. These post-inspection intervals neither adjust for multiple experiments nor preserve dependence across days. The extra weather information, correction and model architecture are not isolated by this comparison. [Full bootstrap and independent review](f1-005/review/paired-bootstrap-review.json).

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

## Completed evidence

| Work | Result and retained evidence |
| --- | --- |
| [001: fixed challengers](f1-001/README.md) | Includes a neural classifier; no all-metric test win over persistence. |
| [002: purged linear models](f1-002/README.md) | Lower error in one history model; selected classifier loses recall. No promotion. |
| [003: archived weather inputs](f1-003/README.md) | Fixed forecast improves test point scores; selected learned classifier loses required precision. No promotion. |
| [004: conditional residual synthesis](f1-004/README.md) | Error and uncertainty experiments; validation retains the fixed forecast. Independent reconstruction and paired-day audit retained. |
| [005: constrained correction](f1-005/README.md) | Reusable function lowers numerical test error while exactly preserving NWP event calls. Satellite-validation error worsens; independent audit checks 7,133 hours and all 30 metric records. |
| [006: event classifier with past errors](f1-006/README.md) | Three fixed configurations, six fits; validation-selected classifier passes the original-reference test gate by one recovered event, but satellite test reverses the gain. No replacement recommendation. |
| [007: joint-reference supervision](f1-007/README.md) | Six fixed fits and exact independent replay. Averaging reference-event targets improves recall/F1 but regresses precision; both references reported separately. |
| [008: two-source correction](f1-008/README.md) | Four fixed fits, matched no-GFS arms and 121 frozen policy pairs. Five of six selected test metrics improve; weather precision regression blocks replacement. |
| [Historical training reference](reference-training-001/README.md) | Exact SARAH joins for all 17,832 targets, explicit missingness and unchanged purged memberships. |
| [Additional forecast source](nwp-alternative-001/README.md) | One NOAA GFS archive request. Complete radiation-only subset; invalid cloud values and original failed intake preserved. Independent raw-source audit passes. |
| [Reference substitution](reference-sensitivity-001/README.md) | Scores every fixed method on a different reference; no fitting or reselection. Independent recomputation checks all 48 method/period/reference comparisons. |

The [review pack](../delivery/Aktina-Competition-Pack.zip), current site, slides and silent video are already prepared from completed evidence for the **6 October competition deadline**. Experiments 005–008 are separate research artifacts and have not been wired into the supplied scheduler or presented as operating gains. The scheduled future-forecast task was deleted at the user's request. Its existing captures remain as audit records; no scheduled follow-up or future result is a delivery dependency.

## Research direction

Synthesis is useful for expressing uncertainty, normalizing known physics and reusing scarce real observations. It does not create independent weather measurements. Rematerialization saves working memory by recomputing intermediate values; it cannot recover tomorrow's unknown clouds.

For Aktina's water-storage idea, the next useful extension is coherent daily error trajectories, followed by a comparison of water service and energy use under the same physical constraints. Independent hourly scenarios from 004 are not sufficient for that test because they do not preserve cloud persistence. Actual surplus electricity also depends on grid/load conditions; radiation above 600 W/m² is only the current proxy. Forecast improvement, schedule feasibility and physical savings require separate evidence.
