# Locked analogue research forecasts

Two fixed research methods and the original live forecast are locked for the same 48 future hours. This is an inference record, not an accuracy result or product upgrade. Experiment 004 selected the raw archived forecast; it did not select either analogue.

The lock completed on 4 October 2026 at 09:10:17 UTC, before the first interval starts on 5 October at 09:00 UTC. The original forecast was captured at 08:58:50 UTC. All 17,832 historical training targets precede that capture; the latest is 28 September at 20:00 UTC. Provider publication availability remains unverified.

Candidate availability is the later lock, 11 minutes 27 seconds after the raw capture. The first interval starts 23 hours 49 minutes 42 seconds after that lock; its valid endpoint is 24 hours 49 minutes 42 seconds after it. The candidates are prospective under the frozen before-interval rule, but were not available 24 hours before the entire first interval. Prediction-file leads remain relative to the original forecast capture; `run-receipt.json` separately records the lock-relative leads without changing targets or timestamps.

`lock-001/manifest.json` pins every output and the unchanged source inputs. `predictions.json` and `predictions.csv` contain three methods for every interval: `nwp_live`, `analogue_raw` and `analogue_solar`. Probability decisions use strictly >.5, with the event defined as radiation strictly >600 W/m². The raw control has a deterministic 0/1 probability and no invented interval.

`training-bank.csv` preserves target values, archived forecasts, residuals and source hours. `parameters.json` records the historical cloud median and six-input transform. `neighbors.json` retains 64 common source IDs and distances per target. `scenarios.json` holds both sets of residual scenarios; their empirical 5th/95th percentiles are not guaranteed-coverage intervals or coherent daily trajectories.

The historical bank uses nominal archived day2 forecasts. This live capture has different observed capture-to-valid leads; its model initialization/publication time is unknown. This is a transfer test across those vintages. Historical reference values are weather-model/reanalysis output, not independent sensors. No satellite reference, future truth, accuracy score, threshold search, scheduling or plant control was used.

## Checks and reproduction

Seven analytical/capture tests passed before inference. The runner checks raw payload hashes, original selected hours and raw CSV values, preserves missing-input status, and refuses an existing output directory or a lock at/after the first target interval. Local clock records and hashes are not trusted timestamp attestation.

From the repository root, using the existing versions recorded in the manifest:

```sh
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/prospective-001/analogue-001/test_adapter.py
PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/prospective-001/analogue-001/run.py --output app/experiments/prospective-001/analogue-001/lock-new
```

The second command intentionally fails after the original deadline; it cannot create a new retrospective result labelled prospective. Reconstruction of the retained lock is separate from rerunning inference. Later reference evaluation must retain the original target sets, missingness and retrieval waiting rule; it must not refit, retune or reselect methods.

Independent reconstruction passed with exit 0: 12 source files, all seven locked outputs, 17,832 historical rows, 48 queries, 3,072 ordered neighbour IDs, 6,144 scenario values and all 144 predictions. Scenarios, medians, interval endpoints and CSV predictions reproduced with zero difference; decisions matched exactly. The independent geometry/scaler calculation uses declared numeric tolerances.

The first reviewer attempt changed one near-tie ordering when independently recomputing floating-point scalers. Both source rows remained within the same 64 neighbours and had zero residuals. That failed attempt and its diagnosis are retained. The second check independently validates the fitted parameters, then applies their saved values to reconstruct the exact operational ordering. No candidate, threshold or locked output was changed.

```sh
python3 -B app/experiments/prospective-001/analogue-001/review-lock-v2.py
```

`review-lock-v2-result.json` and its execution receipt preserve the reconstruction details; `run-receipt.json` pins them. This check establishes reproducibility, not future accuracy.
