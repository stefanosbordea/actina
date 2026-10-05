# Independent runtime review

PASS on the recorded second execution, exit 0. The checker imports no experiment helper and performs no fitting or LP re-solving.

- 153,616 forecast-only distances, exact ranks and chronological selected sets reconstructed
- 3,674,112 scenario values reconstructed from their original source rows
- All 1,794 water plans checked, with 598 exact reproductions of the prior recency policies
- Scenario cost, grid energy, unused PV and per-solve daily-regret objectives independently replayed
- Every original outcome cohort, comparison and admission gate checked
- All 54 pinned input and output identities unchanged

Scenario cost reconstruction error is zero. Exact binary64 water residuals are retained in `water-exact.csv`. The largest is 1.706e-12 m³, below the frozen 1e-6 m³ numerical tolerance. This is not evidence of physical plant error or operational certification.

Both conditional policies pass the eight aggregate axes in both periods. Both fail validation daily-regret CVaR. Coherent validation tails are +€0.408 and +€0.528 per day for weather and satellite references. Shuffled tails are +€0.125 and +€0.768. Conditional coherent lowers modeled cost on all 144 test days under both references. These already-inspected test gains do not cancel the validation losses or justify promotion.

The first checker failed because Python's compensated `sum(float)` differs from the protocol's explicit left-to-right additions. Its source, log and receipt remain as `check-attempt1.py`, `check-001.log` and `execution-001.json`. Only the independent checker changed. The corrected run and hashes are in `execution-002.json`.

From the repository root, with the existing Python environment:

```sh
PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-012/review/check.py
```

The result is retrospective and uses estimated references, illustrative plant parameters and unlimited grid backup. Nominal forecast times do not prove historical publication availability. No field savings, calibration, novel theorem or general superiority is established.
