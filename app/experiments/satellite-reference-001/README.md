# Satellite reference 001

One request completed on **4 October 2026 at 09:01 UTC**. Schema and timestamp coverage verified; no forecast scoring or training performed.

- Source selector: Open-Meteo `eumetsat_sarah3`, a satellite-derived estimate, not a ground sensor.
- Requested point: 34.7744°N, 32.4229°E. Returned grid: **34.75°N, 32.4°E**, elevation 71 m.
- Coverage: **17,976 hourly timestamps**, 13 September 2024 00:00 UTC through 1 October 2026 23:00 UTC inclusive. No timestamp gaps or duplicates.
- **197 null radiation values**, retained in both raw JSON and CSV. All requested padding hours remain present.

| Missing valid timestamps, UTC (2026) | Hours |
|---|---:|
| 13 February 00:00 through 14 February 00:00 | 25 |
| 15 March 00:00 through 19 March 00:00 | 97 |
| 31 March 00:00 through 1 April 00:00 | 25 |
| 1 July 00:00 through 2 July 00:00 | 25 |
| 20 July 00:00 through 21 July 00:00 | 25 |

Radiation is the mean over the hour preceding its valid timestamp. The first returned interval begins on 12 September 2024 at 23:00 UTC. Missing values are not zero and were not imputed or removed.

`PROTOCOL.md` and `result/protocol.json` precede the request. The latter records the three already-known availability samples. `result/response.json` preserves all provider bytes; `result/response-metadata.json` holds HTTP Date/headers and clocks. `result/reference-full.csv` exposes every row. `result/summary.json`, `fetch-receipt.json` and `test-receipt.json` retain checks and executed-command results. Six focused tests pass.

Raw response SHA256: `207b57c01a0a5cb6b8b71307b905e116d25c5f9ca845940898ae6628f516666c` (286,536 bytes). CSV SHA256: `1c95569b0b1d0d2bea3910e01e917a41dc37c7aedee3d25a7477af55bf7fc7df`.

```sh
python3 -B -m unittest discover -s app/experiments/satellite-reference-001 -p test_fetch.py -v
```

The exact acquisition command is retained in `fetch-receipt.json`; rerunning it refuses the existing attempt. A separate evaluation must declare matching and missingness rules. This intake neither replaces the existing benchmark reference nor establishes forecast accuracy or statistically independent errors.
