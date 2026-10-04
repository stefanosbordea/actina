# V2 sunny-hour threshold

**008 has the higher validation F1. Lowering v2's threshold raises recall and lowers precision.** This is a comparison of saved validation predictions, not a final test result or a replacement for Stefanos's model.

| Method | Precision | Recall | F1 | False calls | Missed hours |
|---|---:|---:|---:|---:|---:|
| Stefanos v2, predicted >600 | 91.289% | 85.621% | 88.364% | 25 | 44 |
| Stefanos v2, predicted >562 | 84.911% | 93.791% | 89.130% | 51 | 19 |
| Saved two-source model 008 | 92.808% | 88.562% | 90.635% | 21 | 35 |

All methods use the same 3,566 validation target hours and the same actual radiation >600 W/m² truth rule. The selected v2 threshold is 562 W/m². Its F1 is 1.505 percentage points below 008. It catches 16 more positive hours than 008 but makes 30 more false calls. Choosing by F1 favours 008. Choosing solely by recall favours tuned v2. Neither statement means one is best for every scheduling cost.

The scan evaluated every integer threshold from 500 through 650, then selected maximum exact F1. Exact ties prefer the threshold closest to 600, then the higher threshold. The protocol and source hashes were frozen before this scan. All 151 rows are retained in `validation-table.csv`. The independent review reconstructs the fixed grid and selected counts without importing the selection implementation.

This adjusts the interpretation of **Stefanos's own v2 predictions**. It does not retrain his model, replace its features or change its numeric curve. MAE remains 18.697 W/m² at either event threshold. Both this threshold and 008's saved policy were selected on validation, so these are tuning results. V2 also used validation for early stopping. There is no new v2 test evaluation here.

008 is a separate trained research model, not a continuation of Stefanos's v1 or v2 weights. [Model lineage and code map](../../../docs/MODEL-MAP.md) explains the distinction. Its higher event F1 does not produce a substitute v2 radiation curve.

## Recheck the retained result

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python app/handoff/v2-calibration-2026-10-04/review.py --check
```

`review.json` retains the independent reconstruction. `run-receipt.json`, `fixtures.log` and `validation-scan.log` identify the executed commands and their exit status. `PROTOCOL.md` records the pre-execution state. Do not edit its frozen hashes after the result.

The scan ran on 4 October 2026 at 12:44 UTC. The user subsequently resumed research based directly on Stefanos's v2. That work is isolated from this completed scan and does not alter these results. The scheduler proposal remains unexecuted. No deployment selection is inferred from this comparison. The application can display the compared outputs with their identities intact while Stefanos's modelling work remains authoritative.
