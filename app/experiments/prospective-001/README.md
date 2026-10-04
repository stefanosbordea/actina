# Prospective forecast 001

Captured once on **4 October 2026 at 08:58:50 UTC**. Status: `CAPTURED_BYTES_VERIFIED_NO_ACCURACY`.

Pinned Open-Meteo request `ecmwf_ifs025`; 168 returned hours, zero radiation/cloud nulls. The fixed prediction is shortwave radiation strictly above 600 W/m². No reference outcomes have been fetched or scored.

| Set | First interval start (UTC) | Final interval end (UTC) | Reference retrieval eligible (UTC) |
|---|---|---|---|
| Primary, 24 hours | 5 October 09:00 | 6 October 09:00 | 8 October 09:00 |
| Secondary, 24 hours | 6 October 09:00 | 7 October 09:00 | 9 October 09:00 |

The first interval begins at least 24 hours after capture completion; the secondary begins at least 48 hours after it. Actual leads and every selected timestamp are in `capture-001/selected-targets.json`. Radiation timestamps identify the **end** of the preceding-hour mean.

- `PROTOCOL.md`: request, threshold, target selection and future satellite-reference rules, declared before the request.
- `capture-001/response.json`: complete provider response; `predictions-full.csv`: all 168 hours, including unselected hours.
- `capture-001/request.json`, `response-metadata.json`, `capture-metadata.json`: exact URL, HTTP Date/headers, local clocks and SHA256 identities.
- `capture-001/capture/manifest.json`: preserved payloads, per-role first-observed times and hashes. `selected-targets.json` binds that manifest.
- `capture-run-receipt.json`, `verification-receipt.json`, `test-receipt.json`: executed commands, status and retained logs. Eight focused tests pass.

Capture finished `2026-10-04T08:58:50.739698+00:00`; target manifest generated `2026-10-04T08:58:50.741754+00:00`. Raw response SHA256: `603289aad68422bec648785a5e1d7b525fc77bd15d6b01354dba49fb00ac7eff`.

From the repository root:

```sh
python3 -B -m unittest discover -s app/experiments/prospective-001 -p test_capture.py -v
python3 -B app/scripts/record_forecast_handoff.py verify app/experiments/prospective-001/capture-001/capture
```

The recorded acquisition command is in `capture-run-receipt.json`; rerunning it refuses the existing directory. This is one capture, with no recurrence. Hash verification proves saved bytes, not externally attested timing. Capture-to-valid-time leads are not issuance leads, and this live forecast is a different vintage from archived `previous_day2`. The declared future SARAH3 reference is satellite-derived, not ground-station truth. There is no validated live original-model comparison.

## Scheduled assessment

A local follow-up is configured for **8 and 9 October at 12:30 Cyprus time**, with **10 October** reserved for an incomplete reference attempt. It runs the [delayed evaluator](evaluation/README.md), preserves all attempts and stops after both sets are complete or the schedule expires. The host and desktop application must be available for the scheduled work. This configuration is not evidence that retrieval or scoring has happened.

## Fixed research candidates

`analogue-001/lock-001/manifest.json` locks the raw live forecast and two residual-analogue variants for these exact 48 hours. The lock completed at 09:10:17 UTC on 4 October, before any selected interval began. All 17,832 historical training targets precede the original capture. Its SHA256 is `e20601b627197a67a81b1e4867625de4697cb755ec5c9d2b1886f0bb3b5a8f8c`.

`analogue-001/README.md` explains the fixed K64 methods and transfer from archived day2 training to this live capture. Predictions, source-hour IDs, scenarios and preprocessing remain under `analogue-001/lock-001/`; execution and seven passing fixture tests are recorded in `analogue-001/run-receipt.json`. Neither analogue was selected for promotion by experiment 004. These are locked research candidates with no future accuracy result yet; the original reference waiting rules remain unchanged.

The candidate lock followed the raw capture by 11 minutes 27 seconds. Its first interval starts 23 hours 49 minutes 42 seconds after candidate availability, although the endpoint is 24 hours 49 minutes 42 seconds later. The original raw-forecast leads are unchanged; the candidates do not establish 24 hours of lead before the entire first interval.

Independent reconstruction of all 144 predictions and their historical neighbours/scenarios passed; `analogue-001/review-lock-v2-result.json` retains the result. The earlier floating-point near-tie audit failure and its diagnosis are preserved separately. No candidate or locked output changed during review.
