# Portable saved-weight audit

`check-initial.py` preserves the original independent checker. Its `result.json`, `check.log` and `execution-receipt.json` remain unchanged. That Mac run reproduced every saved network coefficient bit for bit. The independent polynomial evaluator differed by at most `6.83e-13 W/m²` in irradiance and `1.07e-14` in probability.

Matrix multiplication and nonlinear functions can round differently under Linux and Mac numerical libraries. Before adding the audit to Linux CI, the portable checker explicitly allows `1e-12 kW/m²` coefficient error, equal to `1e-9 W/m²`. It retains the original independent polynomial limits of `1e-8 W/m²` and `1e-11` event probability. This is a verification portability change, not a model change or a new fit.

Every row must still produce the exact saved decision at **all 21 probability thresholds from 0 to 1 in steps of 0.05**. These cover every pair in the 121-entry correction grid and the default cutoff. The original selected-policy checks also remain. A floating-point difference below the numeric tolerance is rejected if it changes any threshold decision. Dataset membership, timestamps, labels, saved CSV/NPZ correspondence and frozen input/output hashes remain exact.

Five regression tests cover harmless rounding, excessive coefficient error, excessive probability error, every threshold crossing and invalid values. The separate local portable result and execution receipt retain the actual replay outcome. Neither a local pass nor these tolerances imply that a Linux run has already passed.
