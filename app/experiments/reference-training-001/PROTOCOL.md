# Historical satellite training-reference join

Prepare a reference join only. No forecast scoring, event-label selection, model fitting, threshold search or original-file changes.

The retained `satellite-reference-001` source already covers 13 September 2024 through 1 October 2026, including every experiment-006 training target. Reuse those exact bytes; do not make a duplicate API request. Preserve the existing validation/test reference unchanged.

Pin the original request, HTTP receipt, acquisition protocol, raw response, full CSV, source schema checker and summary. Also pin experiment-006 features, feature targets, both purged training-origin lists and its report. Re-run the original schema checker on the retained raw response and require byte-identical CSV reconstruction. Verify HTTP status, request identity, zero UTC offset, units and complete hourly coverage. Every target must precede the original source retrieval finish time.

Join all 17,832 experiment-006 rows, in their existing order, by exact target UTC. Original naive target labels use the established fixed UTC+03 convention; do not apply seasonal DST. Verify target equals origin plus 24 hours and its saved UTC epoch. `shortwave_radiation` is the mean for the preceding hour, so interval start is exactly valid time minus one hour. Reject duplicate or absent timestamps, inconsistent metadata, changed original values or invalid nonmissing radiation.

Preserve every joined row. Null satellite values remain blank with a missing indicator. Include separate membership flags for the exact validation and test training sets; independently verify their target-before-first-evaluation-origin purge. Report all-row and both training-set totals, available counts, missing counts and contiguous missing spans. Save every missing joined row separately. Do not impute, drop, replace or choose labels here.

Source attribution: EUMETSAT CM SAF SARAH3, distributed through Open-Meteo. This is a satellite-derived irradiance estimate, not local ground-sensor truth. The returned grid and source request are retained; archive retrieval does not establish historical publication availability. The immutable reference joins are for a separately declared experiment, not an operational-data claim.

Refuse existing outputs; use the standard library only. Recheck all pinned source hashes after preparation. Save command, exit status and output identities. No network data request or new dependency is needed.
