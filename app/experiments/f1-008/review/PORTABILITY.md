# Saved-model replay across platforms

The original Mac audit required bit-identical probabilities and passed. Ubuntu CI run [37194305754](https://github.com/stefanosbordea/actina/actions/runs/37194305754) failed that comparison with a maximum absolute difference of `2.168404344971009e-19` in the validation weather model. The retained failure log records the actual error. This is consistent with last-bit floating-point rounding across the Mac and Linux numerical libraries, not evidence that the fitted trees or supplied features changed.

The portable check allows at most `1e-15` absolute difference in saved-model probabilities. It independently requires **identical decisions at every threshold from 0 to 1 in steps of 0.05** for every row. These thresholds cover all 121 frozen correction pairs and the default 0.5 cutoff. A smaller numeric change that crosses any threshold still fails. Hashes, joins, labels, reused probabilities, event counts and frozen policy selection retain their exact checks.

`check-initial.py`, `result.json`, `check.log` and `execution-receipt.json` preserve the first successful Mac audit. `ci-first-failure.log` and its JSON receipt preserve the first Linux failure. The experiment runner, protocol, fitted models, policies and original results are unchanged.

The local portable run passed all four replay regression tests and the complete independent audit. Its four model replays remain bit-identical on this Mac. Results and command evidence are in `portable-result.json`, `portable-tests.log` and `portable-execution-receipt.json`. CI invokes `check()` through `runpy` and writes fresh evidence under `app/build/release-check`, leaving the retained initial audit intact.
