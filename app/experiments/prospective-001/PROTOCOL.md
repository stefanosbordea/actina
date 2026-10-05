# Prospective forecast capture 001

Frozen before the first request. This experiment captures one forecast; it does not fit a model, evaluate accuracy, change Stefanos's inputs or schedule recurring work.

## Fixed request and prediction

- Provider: Open-Meteo live Forecast API, `https://api.open-meteo.com/v1/forecast`.
- Paphos: latitude 34.7744, longitude 32.4229. Requested model: `ecmwf_ifs025`; this is a provider model selector, not an immutable model version.
- Hourly fields: `shortwave_radiation,cloud_cover`; `timezone=GMT`, `timeformat=unixtime`, `forecast_days=7`.
- Preserve all returned hours and nulls. Export every hour to CSV. The fixed event prediction is radiation **strictly greater than 600 W/m²**; exactly 600 predicts false, null radiation remains unknown.
- Radiation is the mean over the preceding hour. Cloud cover is instantaneous at the valid timestamp. Unix timestamps and all recorded clocks are UTC.

## Target selection

Use the existing supplied-file capture helper's `capture_finished_at_utc`, after saving the full response and full predictions CSV. Let `ceil_hour(t)` be the earliest whole UTC hour greater than or equal to `t`.

- Primary: exactly 24 consecutive radiation intervals, beginning at `ceil_hour(capture_finished_at_utc + 24 hours)`.
- Secondary: exactly 24 consecutive intervals, beginning at `ceil_hour(capture_finished_at_utc + 48 hours)`; these are the next 24 intervals after the primary.
- An interval beginning at `s` uses the radiation timestamp `s + 1 hour`. Both sets must be fully covered by returned timestamps. Nulls remain selected; values never influence inclusion. All other returned hours remain in the raw response and CSV.
- Store every selected interval's start/end and elapsed time from local capture completion. These are observed capture-to-valid-time leads, **not** model initialization or issuance leads.

## Evidence and failure rules

Record the exact request, raw response, HTTP headers including Date, local request start/end UTC, elapsed monotonic time, file SHA256 values, script/protocol/helper identities, and the helper's per-role first-observed times. Run the existing helper's byte verification. Preserve failed responses and errors. Refuse an existing output directory; do not retry silently or replace a failed attempt. Reject invalid units, non-UTC timestamps, duplicate or missing hours, nonfinite/out-of-range values and incomplete target coverage. A failed capture receives no success status.

Local clocks, HTTP Date and hashes are evidence of this local capture, not trusted timestamp attestation or authenticated provider provenance. The live API may assemble runs; a pinned selector and observed capture do not establish a single run's issuance time. This vintage differs from the archived `previous_day2` experiment.

## Later evaluation

No reference data are fetched and no accuracy claim is made in this capture. Before the first forecast request, the primary future reference is declared as `https://satellite-api.open-meteo.com/v1/archive`, `models=eumetsat_sarah3`, latitude 34.7744, longitude 32.4229, `hourly=shortwave_radiation`, `timezone=GMT`, `timeformat=unixtime`. This is a satellite-derived radiation reference, not ground-station truth or the reconstruction target used in experiment 003.

Reference retrieval becomes eligible only 48 hours after the final valid timestamp of the target set being evaluated. Match the preceding-hour means by exact UTC valid timestamp; reference event labels also use strictly greater than 600 W/m². Missing, duplicate, invalid or unavailable reference hours fail a complete-set assessment; never drop them to obtain a score. Preserve failed attempts. The waiting period is an eligibility condition, not a promise of provider availability. No persistence/original-model comparison is valid without independently establishing the same inputs available at the relevant decision time. No retrospective replacement of the fixed target sets, reference or threshold. This capture does not schedule that later retrieval.

Official documentation: [Forecast API](https://open-meteo.com/en/docs), [model updates](https://open-meteo.com/en/docs/model-updates), [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api), [Satellite Radiation API](https://open-meteo.com/en/docs/satellite-radiation-api).
