# Additional GFS forecast archive

**Radiation-only input is ready; the original radiation/cloud intake failed its cloud-quality check.** One fixed historical request returned 17,856 hourly rows, including all 17,832 required targets and 24 padding hours. Radiation has no missing, nonfinite or negative values. Cloud has no nulls but contains five values of 101% and three of −1%; those values remain unchanged in the raw response and diagnostics.

`result/radiation-only.csv` contains all 17,832 origins/targets, exact UTC epochs, valid endpoints, radiation-interval starts and `gfs_day2_radiation_w_m2`. Its SHA-256 is `8ecdaee979277ad2a417311a7cbf4e5a93da2ca33724931873224c7c3d519359`. The entire cloud column is excluded under `RADIATION-ONLY.md`; no hour was removed or value clipped. No forecast score, model fit or accuracy-based selection occurred.

The original strict failure remains in `result/failure.json` and `run.log`. `result/diagnostic-join.csv` preserves all raw target values; `quality-flags.csv` lists the eight affected hours. The two-variable intake has not been relabelled as successful.

| UTC valid endpoint | Raw cloud % |
|---|---:|
| 2024-11-09 12:00 | 101 |
| 2025-01-04 00:00 | 101 |
| 2025-01-16 12:00 | 101 |
| 2025-03-06 12:00 | 101 |
| 2025-04-23 06:00 | 101 |
| 2025-05-09 12:00 | −1 |
| 2025-05-30 12:00 | −1 |
| 2025-11-14 06:00 | −1 |

## Source and timing

The fixed selector is `gfs_global`: NOAA NCEP GFS distributed by Open-Meteo, chosen from documented global coverage and native radiation/cloud availability, not comparative scores. The official selector combines native global GFS resolutions as required by the requested fields. This is a second model family relative to ECMWF, not proven statistically independent information.

Request: `https://previous-runs-api.open-meteo.com/v1/forecast`, coordinates 34.7744° N, 32.4229° E; `models=gfs_global`; `hourly=shortwave_radiation_previous_day2,cloud_cover_previous_day2`; `start_date=2024-09-15`; `end_date=2026-09-28`; `timezone=GMT`; `timeformat=unixtime`. Exact encoded URL, HTTP headers/Date and local timing are saved in `result/request.json` and `response-metadata.json`.

The sole request returned HTTP 200 and finished at **2026-10-04T09:55:47.111091Z**. Raw response: 330,655 bytes, SHA-256 `e41f4d3fbc498d4fb6e6be7706af3090904124291c2528cf55d2e9c9a4f14d19`. Returned grid: 34.734787° N, 32.460938° E, elevation 71 m. Required targets run from 2024-09-15 21:00 UTC through 2026-09-28 20:00 UTC. All timestamps and original hashes match; no original file changed.

Day2 is the provider's nominal 48-hour offset. Historical publication time, operational availability and exact upstream revision remain unverified. Original labels use the previously recovered fixed UTC+03 convention, not seasonal DST. Radiation averages the preceding hour; cloud refers to the valid time. The retained raw response keeps every padding hour. No current/future forecast polling or retries occurred.

Weather data by [Open-Meteo](https://open-meteo.com/), using NOAA NCEP GFS. Open-Meteo's [API data licence](https://open-meteo.com/en/licence) is [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); [NOAA terms](https://www.weather.gov/disclaimer) also identify the provider. Our changes are CSV conversion, UTC joining, quality flags and removal of the entire cloud column from the explicitly separate usable input. No provider endorsement is implied.

Primary technical references: [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), [GFS coverage and variables](https://open-meteo.com/en/docs/gfs-api), [official selector code](https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Controllers/ForecastapiController.swift).

`fetch.py` is the one-request reproducer and preserves failures; `diagnose.py` reconstructs the flagged join without a new request; `radiation_only.py` exports the separately declared radiation input. All outputs refuse overwrite. A later experiment must freeze its evaluation before using this source; no model or benchmark is changed here.
