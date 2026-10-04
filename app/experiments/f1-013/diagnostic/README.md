# Why the conditional decisions stayed unchanged

Within all 299 retained conditional day ledgers, raw NWP is the only candidate satisfying every expected-score safeguard. The exact optimizer therefore has no admissible alternative to choose. This describes the reduced candidate set, not every possible dominated 24-bit action.

The worst-reference objective has strict gains before safeguards on seven validation days and three test days. The precision safeguard rejects every one of those opportunities. Recall rejects none of the positive-objective candidates in any of the eight period/bank/objective groups. Every positive-objective candidate changes the daily number of calls, so this diagnosis is not a repeat of a fixed-count search.

## Complete day counts

“Precision blocks” means no positive-objective candidate passes precision alone. The corresponding F1 column uses the same independent definition. These counts overlap and must not be added.

| Period | Bank | Objective | Days with gains before safeguards | Days with gains after all safeguards | Precision blocks | F1 blocks |
|---|---|---|---:|---:|---:|---:|
| Validation | Recency | Worst reference | 12 | 1 | 11 | 0 |
| Validation | Recency | Mean reference | 19 | 1 | 14 | 7 |
| Validation | Conditional | Worst reference | 7 | 0 | 7 | 0 |
| Validation | Conditional | Mean reference | 21 | 0 | 16 | 14 |
| Test | Recency | Worst reference | 4 | 0 | 4 | 0 |
| Test | Recency | Mean reference | 16 | 0 | 16 | 12 |
| Test | Conditional | Worst reference | 3 | 0 | 3 | 0 |
| Test | Conditional | Mean reference | 17 | 0 | 17 | 14 |

The distinction between a family acting alone and in combination matters. For validation conditional mean-reference gains, dropping precision alone from the full set would reopen seven days. Dropping F1 alone would reopen five days. These are properties of the saved finite candidate sets, not recommendations to drop safeguards. On test conditional mean-reference gains, precision alone rejects all 17 days, while F1 independently rejects 14.

One test conditional day has an unguarded strict F1 opportunity for each reference separately, but no action strictly improves both. No day has that conflict after each reference's own P/R/F1 safeguards. There is also no day where both references independently permit a positive joint-objective action but their intersection rejects all such actions. Precision rejection explains the primary conditional result more directly than reference conflict.

## Evidence and scope

The diagnostic reads all 598 bank/day records and produces all 1,196 objective rows. It checks the exact fractions, recorded failures, objective values and selected optimum against each saved candidate ledger. The finite-set attribution fixtures include overlapping constraints, reference conflict and refusal of corrupted saved failures.

It opens no realized outcomes, masks or observed-score reports. No forecast is fitted, no policy is tuned or selected, and no 013 result is replaced. Expected scenario improvements and rejected alternatives do not establish realized improvements, calibration or a reason to weaken the gate.

- [Every day and objective](result/every-day.csv)
- [All aggregate counts and exact objective maxima](result/summary.json)
- [Definitions fixed before this diagnostic](PROTOCOL.md)
- [Input hashes](inputs.json)
- [Execution receipt](result/execution-receipt.json)
- [Actual process command and exit](process-receipt.json)
- [Three passing synthetic fixtures](preflight.log)

Execution completed with exit 0 in 2.180 seconds wall time and 2.167 seconds CPU time. Peak RSS was 38,404,096 bytes on macOS. The input lock is `4781c35d09b8c81d96ef61869db78a15c4280be9c93badbe7b2afe3f50a516bf`.

Reproduce from the repository root in a separate copy where `diagnostic/result/` does not exist:

```sh
/Users/kixem/Documents/Loucas-Stefanos-Workspace-2026-09-19/AquaShift/.venv/bin/python app/experiments/f1-013/diagnostic/run.py
```

The runner refuses to overwrite retained output.
