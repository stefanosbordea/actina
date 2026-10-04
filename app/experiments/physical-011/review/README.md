# Independent review

PASS, actual exit0. `check.py` makes197,353 checks without importing the optimizer or runner. It reconstructs17,832 source endpoints,1,837,056 scenario values,1,196 water plans, source chronology, complete-day masks, solar/grid allocation, costs, fractional-tail statistics and both admission rules. All30 pinned input/output files remain unchanged. Scenario cost replay error is zero.

The largest exact binary64 water violation is15/8796093022208m³, about1.7053e-12m³. `water-exact.csv` retains every plan's rational extrema and ending stock. These representation residuals are within the frozen1e-6m³ tolerance. They are not evidence of operational plant failure. Every horizon still has the declared2880m³ production and9792kWh desalination energy within that tolerance. Grid reductions represent changed solar allocation, not lower desalination energy.

The coherent candidate fails validation admission. Its satellite grid-energy tail rises0.4892kWh and both references have positive daily-regret tails. The shuffled candidate improves all eight aggregate axes in both periods, but validation regretCVaR remains +€0.2985 for weather and +€1.5755 for satellite. Both candidates improve on test. This does not establish coherent-trajectory superiority or a no-regret upgrade. Lower aggregate cost tails can coexist with some days being worse than the baseline.

`check-portable.py` separately confirms every numerical member and all3072 reconstructed Unicode timestamps in the derived bank copies. No object array was unpickled. Its first attempt incorrectly required identical ZIP member order. That checker, failed log and receipt are retained. The repaired member-set comparison passed with exact value checks. Original archives remain unchanged.

These checks do not independently re-solve the LP or authenticate historical publication time. The plant, PV conversion and tariff are illustrative. Unlimited grid backup maintains service. This is retrospective evidence, not measured curtailment recovery, operating authorization or field savings.

Reproduce from the repository root using the existing environment:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/review/check.py
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/review/check-portable.py
```

Actual Python paths, commands, exit codes and hashes are in `execution-001.json` and `portable-execution-002.json`.
