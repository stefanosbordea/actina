# AktinaBench 004: conditional residual scenarios

Frozen for review before fitting or scoring. No 004 result is known. This is a retrospective research experiment: the original test has already been inspected in earlier experiments. It changes no original model, inputs, published result, schedule or UI.

## Question and evidence

Can conditional historical residual scenarios improve on the archived day2 forecast itself, while describing uncertainty? Experiment 003's TRAIN/CV-only diagnostic motivates the mechanism: 27/38 direct-forecast validation misses occur at 550–600 W/m² and 15/21 false calls at 600–650. The selected classifier recovers 27 misses but adds 31 false calls, fixing none of the direct forecast's existing false calls. Cloudy near-threshold training examples are sparse. These are development observations, not a new holdout.

This adapts established [analogue ensembles](https://doi.org/10.1016/j.apenergy.2015.08.011) and [probabilistic NWP post-processing](https://arxiv.org/abs/2101.06717); it claims no new forecasting theorem. Scenario generation reuses TRAIN residuals. It creates neither new observed truth nor extra independent samples. The reference targets themselves come from an unpinned historical weather archive, not an independent local irradiance sensor. Related forecast/reference model structure may contribute to apparent skill.

## Fixed inputs and memberships

Reuse original `data/features.csv`, `data/paphos_weather_data.csv`, `eval/cv_predictions.csv`, `eval/test_predictions.csv`, and pinned `../nwp-archive-001/archive.json` (SHA256 bae187f19e9bacf6c00343666feda994bb051d7053b77f0cc53b9f75555378fc). Use only day2 radiation/cloud, never day1. Join the target at origin +24 hours with the already checked fixed UTC+03 label convention. Radiation is a preceding-hour mean; cloud is a point value. Historical archive publication availability remains unverified.

Keep every original validation/test origin and actual value. Truth is actual radiation strictly >600 W/m². Training origins must have target timestamps strictly before the first evaluation origin: the same 24-hour purge as 001–003. Freeze the bank for the entire validation block; refit on all eligible pre-test rows only after the validation choice is saved. All newly fitted methods use the same training membership. Stop on duplicate or absent joins, nonfinite original/radiation inputs or changed labels. Cloud nulls remain explicit and never remove rows.

## Geometry and common distance features

At latitude 34.7744° and longitude 32.4229°, apply the approximate equations in [NOAA's solar-position note](https://gml.noaa.gov/grad/solcalc/solareqns.PDF). Use six midpoints of the preceding hour: 5, 15, 25, 35, 45 and 55 minutes after its start. Fractional-year denominator is 365 or 366 as specified for leap years; local clock offset is fixed +03. No atmospheric/refraction correction is applied.

Let s=max(100,1000 × mean(max(cos(zenith),0))) across those six samples. This is a **geometrical scale**, not atmospheric clear-sky irradiance or an upper physical bound. Input coszen is the six-sample mean before clipping. Solar-hour sine/cosine use the middle of the preceding hour. A declared daytime slice is s>100, independently of actual radiation. No evaluation hour is deleted, no night value is forced to zero, and no clear-sky upper cap is applied.

Six distance inputs: day2 radiation/s, forecast cloud percentage, cloud-missing indicator, mean coszen, sine and cosine of target solar hour. Impute cloud using the current training set's nonmissing median; preserve its missing indicator. Fail if that median cannot be calculated. Fit each feature's mean and population standard deviation on training only; replace zero standard deviations by 1. Use the same standardized inputs for raw/normalized analogues and Ridge. Distances are unweighted squared Euclidean distances: no learned weights or feature search.

## Fixed methods

Method order, also used for final exact ties:

1. `persistence`: original baseline radiation, cutoff600.
2. `original`: retained original-model predictions, cutoff600, unchanged including any negative values.
3. `nwp_day2`: archived day2 radiation, cutoff600; primary stronger control and fallback.
4. `median_bias`: day2 plus the TRAIN median raw residual (actual−day2), clipped below at zero; cutoff600.
5. `ridge_bias`: Ridge(alpha=1, fit_intercept=True, solver=svd) on the six training-standardized inputs, predicting the TRAIN raw residual; day2 plus correction clipped below at zero; cutoff600. No hyperparameter search.
6. `global_residual`: 64 unconditioned TRAIN residual representatives. Sort raw residuals by value then source origin. Select ranks floor((j+.5)N/64), j=0…63. Scenarios are max(0,q+r_j).
7. `analogue_raw`: choose exactly K=64 nearest training rows using the common distance features. Resolve equal distances by earlier source origin. Scenarios are max(0,q+r_j).
8. `analogue_solar`: use the **same 64 neighbors** as analogue_raw. Scenarios are max(0,q+s_target × r_j/s_j). The difference from the raw analogue isolates residual scaling, not a changed neighborhood or training set.

For scenario methods, the point forecast is the fixed sample median. Probability is the fraction of the 64 scenarios strictly above600. Retain all scenario source-origin IDs and ordering. These are marginal hourly scenarios, not joint daily trajectories; no claim about consecutive cloud, ramp or storage events follows from them. The global representative quantiles are deterministic, with no random synthesis seed.

Point-method event probabilities are their hard 0/1 threshold decisions; mark them as deterministic. They have no prediction interval: interval coverage/width are null, not an invented zero-width uncertainty product. New corrected point forecasts and scenarios are clipped below zero only. Original controls remain numerically unchanged.

## Selection and scoring

Scenario default probability cutoff is .5, strict probability>cutoff. Search exactly [.30,.35,.40,.45,.50,.55,.60,.65,.70] on validation only. Point methods remain at their fixed radiation cutoff600. Scenario median forecasts are not replaced by the selected classifier's decision, and the same intervals accompany every cutoff.

A method/configuration qualifies only when validation precision AND recall each meet the maximum of the original model, persistence and fixed day2 forecast. Compare count ratios exactly; undefined metrics cannot qualify. Within scenario methods, choose greatest F1, then precision, recall, cutoff nearest .5, then lower cutoff. If none qualifies, report its .5 default as unqualified. Across methods, rank qualifying choices by F1, precision, recall, distance from their natural decision cutoff (zero for point methods), then earlier method order. If none qualifies, choose unchanged nwp_day2. Save every grid and the chosen method/settings before test fitting or scoring. No test-driven retuning or reselection.

Report selected and fixed-default outcomes for each complete split and every target month, supplemented by the predeclared daytime slice: TP/FP/FN/TN, precision, recall, F1, median/point MAE and RMSE, and Brier score of the probability against actual>600. Scenario intervals are empirical 5th/95th percentiles using linear interpolation; coverage is inclusive and width is upper−lower. Report empirical 90% interval coverage and mean width together. Empty slices retain zero hours and undefined scores. These are empirical intervals with no exchangeability, calibration or nominal-coverage guarantee.

Promotion is separate: the validation-selected candidate must strictly exceed the original model on F1/precision/recall, match or exceed fixed persistence on all three with a strict gain, AND match or exceed fixed day2 on all three with a strict gain, over the same full test. Retain every loss. Even a pass remains retrospective and requires new independent evidence before release; no new model is handed off as an upgrade merely because a different test row looks favorable.

## Retention and execution

Use installed Python/NumPy/pandas/SciPy/scikit-learn only, at most two CPU threads and no network during execution. Save protocol/code/input hashes; exact joined features and geometry; memberships; training cloud median/scaler; Ridge coefficients; global source IDs; each analogue query's 64 source IDs and distances; scenario values or their exact reproducible inputs; all predictions, grids, full/month/daytime metrics, comparison CSV and execution log. Never overwrite a prior run or original artifact.

A separate stdlib check must verify joins, NOAA geometry fixtures, training cutoffs, missingness, source-hour identities, no evaluation labels in any scenario bank, scenario reconstruction/clipping, selected/default decisions, interval/Brier metrics, every hour/month/daytime slice, grids and selection. Record any floating representation tolerance explicitly. Independent uncertainty review may resample paired days after the choice is frozen; it cannot select a replacement winner.
