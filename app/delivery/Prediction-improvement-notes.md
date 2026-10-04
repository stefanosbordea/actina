# Prediction work for Stefanos

2 October 2026. The model in this package is an independently built provisional reference. It is ready to be replaced by your model after the same checks.

The reference does **not** beat the strongest simple comparison we tested. On 2,208 hours from July–September, its average radiation error is **8.812 W/m²**, against **7.638 W/m²** for latest-available same-hour persistence: the model is 15.37% worse. The paired day bootstrap gives a 95% interval of 0.178 to 2.066 W/m² for the model's additional error. Its 8% gain against an older two-day persistence comparison must not become the headline.

The reference study assumes an issue time of 18:00 Cyprus time for every hour of the following day. For targets at 00:00–18:00, persistence uses the previous day's matching hour. For targets at 19:00–23:00 it uses the matching hour two days earlier. The latter is necessary because those hours on the previous day have not happened at issue time. Every persistence source timestamp is checked against the assumed cutoff. Using the hour ending at 18:00 assumes zero reporting delay; real publication and delivery delay still need testing.

Our data comes from Open-Meteo's historical ECMWF IFS grid. It is a real downloaded historical weather product, not sensor observations, measured grid surplus or an archive of what was available at each original issue time. Passing the chronological checks does not establish operational forecast accuracy. The 600 W/m² flag represents high solar radiation; it does not establish curtailment.

One useful experiment has now run. We trained a model to correct the latest persistence prediction, using training targets before June and evaluating June only. The June errors were:

| Comparison | All-hour MAE | Daylight MAE |
| --- | ---: | ---: |
| Latest available persistence | 8.404 | 14.398 |
| Direct LightGBM radiation model | 11.817 | 19.850 |
| LightGBM correction to persistence | 9.997 | 17.009 |

All errors are W/m². The correction improves on the direct model by 15.4%, but is still 19.0% worse than persistence. In June's 43 daylight hours with 20–60% cloud cover it reduced error from persistence's 24.395 to 17.044 W/m². Only five daylight hours had cloud cover above 60%; that is too little evidence for a reliable claim. Cloud cover at the target hour is used for this diagnosis only, never as an input.

This experiment was designed after seeing the original test failure, and June had already informed the threshold. It is exploratory development, not new blind evidence. The frozen July–September model, threshold and predictions have not been replaced. Its source, two text checkpoints, June predictions and results are in `results/june_residual_experiment/`.

The next improvement should add tomorrow's **issued** weather forecast, especially cloud cover and solar radiation, rather than tomorrow's reconstructed weather. Use an individual archived model run that was published before the 18:00 cutoff; record initialization time, actual availability time, forecast horizon and raw response. The continuous historical forecast series stitches the first hours of successive runs, so it is insufficient by itself to prove a day-ahead forecast. See [Open-Meteo historical forecast documentation](https://open-meteo.com/en/docs/historical-forecast-api) and the [Single Runs API](https://open-meteo.com/en/docs/single-runs-api).

Before further comparisons, freeze one candidate, one source-availability rule, the 600 W/m² scenario threshold, the baselines and the scoring code. A concrete proposed new blind period is 3–31 October 2026, with daily inputs and forecasts saved at 18:00 before any following-day outcomes are read. This is a proposed protocol: no collection job or automation has been configured. The new `scripts/record_forecast_handoff.py` can preserve supplied raw files and their first-observed times here; it does not fetch forecasts or attest original publication. Keep all-hour and daylight errors, cloudiness groups, false positives and missed high-radiation hours. Do not tune on that period and then reuse it to claim success.

For your handoff, supply an hourly CSV with offset-aware `time`, `actual`, `predicted` and the latest-safe `baseline`. Include `forecast_issue_time` and a model text file with feature names, training target dates and source timing. The evaluation tool rejects duplicate hours, missing hours, nonfinite values, wrong test dates, altered truth and a baseline that uses unavailable hours. Run:

```sh
.venv/bin/python eval/evaluate.py --predictions /absolute/path/to/stefanos_predictions.csv --threshold 600 --output results/stefanos_model_v1
```

Without a reviewed model and feature history this command establishes numerical prediction accuracy only. It does not certify the external model's feature timing.
