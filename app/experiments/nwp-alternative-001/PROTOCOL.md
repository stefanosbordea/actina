# One additional archived forecast source

Choose NOAA GFS by documented global coverage and availability of radiation/cloud fields, before reading its outcomes or comparing any score. Use the fixed Open-Meteo selector `gfs_global`, not Best Match or a grid of alternative providers. The official controller maps this selector to global GFS native resolutions; it is not an immutable upstream version identifier.

Make one bounded historical request to the Previous Runs API for Paphos (34.7744 N, 32.4229 E), 15 September 2024 through 28 September 2026 UTC, inclusive. Request only `shortwave_radiation_previous_day2` and `cloud_cover_previous_day2`, with GMT and Unix time. No sample-date selection, retries, provider switch, current forecast request or automatic recurrence. The response limit is 2 MiB and timeout 50 seconds. Retain HTTP errors and raw bytes if unsuccessful.

The provider defines day2 as a fixed nominal 48-hour forecast offset. At the retained target = origin +24 hours, this is a nominal 24-hour margin before the prediction origin. It does not prove a forecast's original publication time, exact initialization, real-time availability or absence of reconstructed history. This source is a different numerical weather model from ECMWF, not established statistically independent evidence.

Save the exact request, local UTC start/end, HTTP status/headers/Date, response bytes and SHA-256. Validate zero UTC offset, units, exact complete UTC hourly timestamps, duplicate rejection, array lengths and finite nonnegative radiation / cloud in [0,100] when present. Retain all null values and padding. Report returned grid coordinates; do not claim point measurements at requested coordinates.

Join all 17,832 retained experiment-006 target hours using saved UTC epochs and the established fixed UTC+03 source-label convention. Verify origin +24 hours equals the target and its exact epoch. Radiation denotes the preceding-hour mean; cloud refers to valid time. Preserve every row and missing indicator. Report missingness over all returned and joined hours, with full missing-row output and contiguous spans. No imputation or removal of inconvenient hours.

Hash original data/model/eval files and existing join/timestamp evidence before and after. Only this directory may be written. No fitting, target scoring, model comparison, threshold selection, new dependency, account or key. A later experiment must declare any use before evaluation; the previously inspected benchmark is not an independent holdout.

Attribution: NOAA NCEP GFS, distributed by Open-Meteo. Open-Meteo offers API data under CC BY 4.0; retain the provider and licence links and identify our UTC join/CSV conversion as changes. Provider attribution implies no endorsement. Raw response bytes remain unmodified.

Primary sources: [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), [GFS documentation](https://open-meteo.com/en/docs/gfs-api), [official model selector implementation](https://github.com/open-meteo/open-meteo/blob/main/Sources/App/Controllers/ForecastapiController.swift), [Open-Meteo licence](https://open-meteo.com/en/licence), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), [NOAA terms](https://www.weather.gov/disclaimer).
