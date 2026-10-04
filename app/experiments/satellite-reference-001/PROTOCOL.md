# Satellite reference intake 001

Declare this intake before its request. Acquire the complete fixed period **13 September 2024 through 1 October 2026 inclusive**, in UTC. Do not calculate forecast scores, event labels, model comparisons or training targets in this intake.

Request `https://satellite-api.open-meteo.com/v1/archive` with latitude `34.7744`, longitude `32.4229`, `models=eumetsat_sarah3`, `hourly=shortwave_radiation`, `timezone=GMT`, `timeformat=unixtime`, and those exact dates. Radiation units must be W/m². A timestamp denotes the end of the preceding-hour mean. The first returned interval therefore begins at 23:00 UTC on 12 September 2024.

Three earlier availability checks are already known: 10 December 2025, 3 July 2026 and 1 October 2026, saved under `satellite-intake-001/result`. Each returned 24 hours without nulls. These samples establish only sampled availability and schema; they do not establish full-period coverage, accuracy or statistical independence. Preserve their identities in the request protocol. The full date window is fixed before reading this response and is not selected by outcomes.

Preserve the raw response, HTTP headers/Date, exact URL, local start/end UTC, elapsed retrieval time and SHA256 identities. Retain all hours, nulls and padding beyond the existing forecast experiment's range. Export every returned hour to CSV; a null remains missing. Reject wrong units/time basis, duplicate, unordered or missing timestamps, wrong period, nonfinite/negative radiation and inconsistent array lengths. Missing values are reported, never silently excluded or imputed. Report missing intervals as contiguous spans. Schema verification is not accuracy verification.

One request only. Refuse an existing attempt directory; preserve HTTP failures and errors. No silent retries, API keys, installation, forecast scoring, fitting or changes to original inputs. The response limit is 2 MiB; an over-limit prefix is retained and marked incomplete.

This is an EUMETSAT SARAH3 satellite-derived estimate served by Open-Meteo, **not a ground sensor**, operational plant data or replacement for the current benchmark reference. Provider processing, spatial mapping and product revisions remain relevant limitations. Pinning the model selector and response bytes does not authenticate provenance or establish an immutable upstream product revision. Record the returned grid coordinates rather than claiming exact measurements at the requested coordinates. A separate experiment must declare matching and evaluation rules before use.

Primary references: [Open-Meteo Satellite Radiation API](https://open-meteo.com/en/docs/satellite-radiation-api), [SARAH3 product DOI](https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003).
