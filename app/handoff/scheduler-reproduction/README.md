# Supplied schedule reproduced

The supplied `eval/schedule_hourly.csv` is reproduced **byte for byte** when the original scheduler selects `baseline` instead of `predicted`. All 7,104 rows and every column match. Both files have SHA-256 `9dc00d7c015478864bb8259ba22ac6f7a32cc356300e23c4cd5f1e0add86de20`.

Running the **unchanged** `model/scheduler.py` with the retained input files produces [unchanged-model.csv](unchanged-model.csv). Against the supplied export, this changes 7,095 forecast values, 469 production values and 1,069 tank levels. Actual radiation, demand and flat production remain identical. The original files were checked before and after and remain unchanged.

| Original script's illustrative summary | Flat €/m³ | Model schedule €/m³ | Reduction vs flat |
|---|---:|---:|---:|
| Winter–spring | 0.598 | 0.576 | 3.6% |
| Summer | 0.543 | 0.488 | 10.0% |

The persistence control prints 3.6% and 10.2%, respectively. These are the scheduler's unit-cost calculations, not a demonstrated model improvement over persistence or observed electricity-bill savings. Demand uses the target day's recorded temperature; radiation above 600 W/m² defines the illustrative discount. Neither represents a verified operational forecast or observed grid curtailment.

The website and silent walkthrough retain the supplied export and label its forecast source. The regenerated model schedule is ready for Stefanos to review; this report establishes the export identity, not which version he intends to submit.

Reproduce from the repository root with pandas and NumPy installed:

```sh
python app/tools/reproduce_scheduler.py
```

The command copies inputs into temporary directories, runs the unchanged source and a one-selector persistence control, and saves both outputs and logs here. [report.json](report.json) records input/source/output hashes, exit codes and all column comparisons.
