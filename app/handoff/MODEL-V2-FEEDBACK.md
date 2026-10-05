# Aktina v2: features and filtering

4 October 2026. Suggestions for Stefanos's next model; no new model or gain is claimed here.

## Start with three changes

1. **Describe tomorrow's sun position.** Add target-time solar elevation and day-of-year cycles. The current seven inputs contain hour and month, but no solar geometry. Test a clear-sky-normalized radiation feature and smart-persistence reference, with a fixed guard near sunrise/night to avoid division by almost zero. These are candidate features, not assumed improvements.
2. **Use information about tomorrow's clouds that was available today.** A target-day cloud or radiation forecast could add information that yesterday's weather lacks. Use archived forecasts with a fixed 24-hour lead and a pinned weather model; never substitute tomorrow's realized reanalysis. Open-Meteo's [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) provides fixed lead times, including radiation and cloud cover. Verify coverage, issue timing and hourly averaging before joining.
3. **Remove features by measured contribution.** Keep the existing model as a control. Add each feature group separately, then test removing temperature, humidity or cloud cover one at a time. Select on chronological validation blocks with a 24-hour boundary gap. Retain the full comparison, including losses; correlation alone does not establish that a feature is useless.

## What filtering should mean

Check duplicate or missing timestamps, non-finite values, units, time zone and physically invalid records. Record every exclusion. Fit any imputation or scaling using training data only. Rolling statistics must use only values available at the forecast origin.

Do not smooth the target, delete cloudy days, remove difficult test hours or discard false positives to raise F1. If using a daylight-only training experiment, keep the full-period test and report daylight as a separate, explicitly defined slice. A training filter must not silently change the evaluation denominator.

## Older data and deep learning

The current downloader does not pin a weather model. Open-Meteo documents historical IFS data from 2017 and ERA5 from 1940; its default combines sources. That does not prove older Paphos data are accurate or unusable. Pin a source and audit overlap, missingness and seasonal changes before adding years. [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)

Sinha, Hodge and Monteleoni trained solar sequence models on 2016–2017 data at seven US stations and tested 2018. They used solar zenith, clear-sky normalization and weather history; their task was week-ahead forecasting, not our 24-hour Paphos classifier. It supports testing those features and compact sequence models, not claiming deep learning must win or cannot work with two years. Our existing neural experiment lost. [Paper, sections 3–5](https://doi.org/10.1017/eds.2022.20)

## Handoff for evaluation

Send timestamped validation/test predictions, the feature list, training cutoff, model version and any exclusions. State whether timestamps identify forecast origin or target. Loukas can check F1, precision, recall and false-positive/negative counts on the same hours, then connect the accepted output to the demo. Keep radiation truth fixed at **>600 W/m²**; choose prediction thresholds on validation. The current test has already been inspected, so further gains on it are exploratory until checked on a new frozen holdout.
