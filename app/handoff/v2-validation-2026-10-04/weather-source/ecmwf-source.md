# Retained ECMWF source

The saved request explicitly pins **`models=ecmwf_ifs025`**. Both `previous_day1` and `previous_day2` are already present in the archive. Day1 radiation and cloud have no missing values across the original training, validation and test targets.

[Exact successful request](https://previous-runs-api.open-meteo.com/v1/forecast?latitude=34.7744&longitude=32.4229&start_date=2024-09-13&end_date=2026-09-28&hourly=shortwave_radiation_previous_day1,cloud_cover_previous_day1,shortwave_radiation_previous_day2,cloud_cover_previous_day2&models=ecmwf_ifs025&timezone=GMT&timeformat=unixtime)

```text
https://previous-runs-api.open-meteo.com/v1/forecast?latitude=34.7744&longitude=32.4229&start_date=2024-09-13&end_date=2026-09-28&hourly=shortwave_radiation_previous_day1,cloud_cover_previous_day1,shortwave_radiation_previous_day2,cloud_cover_previous_day2&models=ecmwf_ifs025&timezone=GMT&timeformat=unixtime
```

This request completed with HTTP 200 on 4 October 2026 at 08:42 UTC. The returned grid location is 34.75, 32.5, with elevation 71 m. The response contains 17,904 hourly UTC epochs. Its SHA-256 is `bae187f19e9bacf6c00343666feda994bb051d7053b77f0cc53b9f75555378fc`.

| Original split | Target hours | Day1 radiation | Day1 cloud | Day2 radiation | Day2 cloud |
|---|---:|---:|---:|---:|---:|
| Training | 10,699 | 10,699 | 10,699 | 10,699 | 10,699 |
| Validation | 3,566 | 3,566 | 3,566 | 3,566 | 3,437 |
| Test | 3,567 | 3,567 | 3,567 | 3,567 | 3,567 |

Numbers are non-null values. Every target joins to a saved archive hour. The 129 missing day2 cloud values run from 17 April 2026 at 18:00 through 23 April at 02:00 in the recovered fixed +03:00 labels. Day1 cloud remains available during that interval. The original final model combined training and validation, giving 14,265 hours and the same 129 day2 cloud gaps. These are original, unpurged split counts.

| Original split | First target, fixed +03:00 | Last target, fixed +03:00 |
|---|---|---|
| Training | 2024-09-16 00:00 | 2025-12-05 18:00 |
| Validation | 2025-12-05 19:00 | 2026-05-03 08:00 |
| Test | 2026-05-03 09:00 | 2026-09-28 23:00 |

The join uses each original feature timestamp as the origin and adds 24 hours for its target. Original CSV labels have no timezone metadata. The retained timestamp checks recover fixed +03:00, so this join does not apply seasonal Europe/Nicosia offsets. Archive times remain UTC epoch seconds. Radiation is a preceding-hour mean and is not shifted to the interval start.

`day1` and `day2` denote provider-declared nominal offsets, not authenticated publication timestamps. With target = origin +24h, day1 is nominally at the origin and day2 nominally 24h before it. Their presence in the saved archive does not prove availability at a historical decision time or establish original operational vintages.

Stefanos's retained v2 downloader requests `previous_day1` with `timezone=auto` and no `models` parameter. This pinned archive is a distinct source. Its day1 coverage does not establish identity with the v2 input or justify treating the retained day2 control as the same forecast.

Reproduce from the repository root:

```sh
python3 app/handoff/v2-validation-2026-10-04/weather-source/check.py --check
```

Executed successfully with the existing project Python. The receipt is [ecmwf-source.json](ecmwf-source.json), with eight input hashes, exact request settings, split boundaries and field coverage. [check.py](check.py) is offline and reads only timestamps and weather fields for its calculations. No new forecast scores or training were produced.
