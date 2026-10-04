# Independent uncertainty check

Both recorded runs exited 0. Original inputs and results remain unchanged.

`check.py` verifies 270 integer-weight fixtures against exact rational expanded tails. It independently expands all 20,000 calendar draws, then applies the original missing-day mask. Point values and percentile bounds agree within 2.76e-12. Paired daily-regret CVaR is checked separately from the difference of cost CVaRs.

Strict all-eight-axis frequencies depend on tiny floating-point comparisons. `check-frequency.py` recomputes every sign using exact integer sums of the saved binary64 values and integer fractional-tail weights. Validation shuffled fractions are 0.5950 and 0.5754 under exact arithmetic, versus the original 0.5468 and 0.5222. Coherent fractions are 0.0332 and 0.0906, versus 0.0328 and 0.0888. Test fractions agree. The changed comparisons are grid-tail differences at numerical resolution, including values that round to zero. They do not establish meaningful physical improvements.

The original strict all-axis frequencies are numerically unstable, do not portably replay and are unsuitable for interpretation. Retain them as original output only. Exact arithmetic on solver-rounded outputs does not remove solver error. No frequency is a probability of future superiority or an admission test. Interval reconstruction passes, but this is not a blanket pass for the original report.

Commands from the repository root, using the existing Python environment:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/uncertainty/review/check.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 python app/experiments/physical-011/uncertainty/review/check-frequency.py
```

Actual commands, times, exits and hashes are in `execution-001.json` and `frequency-execution.json`. Neither check fits models or changes source results.
