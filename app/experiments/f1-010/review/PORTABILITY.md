# Portable paired-exchange audit

The original `check.py`, `result.json` and execution receipt remain unchanged. The original checker executes at import and writes its retained result. CI must use the separate `portable.py`, whose callable `main()` returns fresh evidence without writing any file. Importing it does not run the audit.

Saved LightGBM probabilities may differ across numerical libraries. Portable replay accepts at most `1e-15` absolute error and requires exact default 0.5 decisions. On every full day, it reconstructs both min and mean pair rankings from the replayed probabilities. The selected added and removed hours must match exactly, including ties. Every strict action at the frozen margins 0, 0.05, 0.10, 0.20, 0.30 and 0.50 must match exactly. This guards all retained policies, including rejected candidates and padding hours, rather than only the final no-swap choice.

All existing input hashes, common-issue chronology, training cutoffs, labels, missingness, masks, pair ledgers, counts, metrics and validation selection checks remain. No fitting, experimental policy change or original-result rewrite is involved. The probability tolerance cannot excuse a changed pair or action.

Run the eight focused tests through unittest discovery with `test_portable.py`. Invoke `runpy.run_path('app/experiments/f1-010/review/portable.py')['main']()` and save its return value outside the retained original evidence. The local portable result and receipt report the actual verification outcome. A local pass does not establish a Linux pass.
