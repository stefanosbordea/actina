# Delayed prospective evaluation

No future reference has been retrieved or scored. The immutable forecast lock contains the captured ECMWF control and both fixed analogue candidates for the original two 24-hour sets.

Run from the repository root with Python 3. Standard library only; no installation or training. These commands make one SARAH3 request after eligibility and refuse an existing output directory.

Primary, **not before 2026-10-08 09:00 UTC**:

```sh
python3 app/experiments/prospective-001/evaluation/evaluate.py --target-set primary --output app/experiments/prospective-001/evaluation/primary-attempt-001
```

Secondary, **not before 2026-10-09 09:00 UTC**:

```sh
python3 app/experiments/prospective-001/evaluation/evaluate.py --target-set secondary --output app/experiments/prospective-001/evaluation/secondary-attempt-001
```

Exit `0` means all 24 expected hours and all candidates were assessed. Exit `2` means the original set is incomplete: `assessment.json` retains the missingness and any explicitly labelled common-hour diagnostic. Exit `1` means refusal or failure; inspect `failure.json`. Raw responses, headers, request parameters and hashes remain in each attempt. A retry requires an explicit new attempt directory; it never overwrites an earlier result or changes the reference. Eligibility does not guarantee SARAH3 availability.

`rows.json` keeps every expected hour. Absent reference timestamps and present nulls remain distinguishable. Invalid/duplicate responses fail assessment; they cannot become a favourable subset. Event rules remain radiation >600 W/m² and analogue probability >0.5. No winner is selected, and no model is promoted. Two 24-hour sets cannot establish general superiority or field savings.

`input-lock.json` pins 32 files, including both manifest chains and all analogue outputs. Its SHA256 is embedded in the evaluator. Capture and analogue content is verified from retained bytes before any network request. Local hashes/timestamps do not authenticate provider provenance or issuance time.

Offline checks:

```sh
python3 -m unittest discover -s app/experiments/prospective-001/evaluation -p test_evaluate.py -v
```

The recorded early primary invocation exited `1` at 2026-10-04 09:13 UTC and saved `early-refusal-001/failure.json`. The production gate precedes input loading and the sole network call; the offline test additionally uses a network spy to assert zero calls on early refusal. No HTTP response or assessment was produced by that invocation. See `execution-receipt.json` for commands, exits and file identities. Fixture evaluations are constructed local tests, not future accuracy results.
