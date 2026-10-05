# Supplied operating limits

Two traces can have identical hourly production and still require different plant movements. This reviewer checks a supplied trace against supplied limits. It does not choose a schedule.

## The analytical example

Both two-hour traces average 2 m³/h in each hour, deliver 4 m³, leave 2 m³ in storage, and meet the same 1 m³ reserve and 4 m³ tank capacity. The initial stock is 2 m³ and demand is 2 m³/h.

| Supplied trace | Stock range | Rate change | Declared limit of 3 m³/h² |
|---|---:|---:|---|
| Constant 2 m³/h | 2–2 m³ | 0 | Met |
| Linear 0 → 4 → 0 m³/h | 1.5–2.5 m³ | +4, then −4 m³/h² | Violated |

The hourly averages cannot distinguish these traces. Reporting a safe ramp from those averages would hide the second trace's violation. These are synthetic examples, not Paphos operating results.

The [independent water proof](independent-water-proof.py) uses exact rational arithmetic and does not import the operating reviewer. It checks inventory extrema inside each interval, not just its endpoints.

## Review supplied files

```sh
node web/review_operating_envelope.mjs --input supplied-trace.json --output new-review.json
```

The report retains the original UTF-8 input and its SHA-256 identity, plus the identity of the exact evaluator bytes used. Existing reports are preserved. A successful command means the review was saved; read its decision for violations or missing evidence.

Reproduce the matched example into a new directory:

```sh
node results/operating-envelope/run-study.mjs --output results/operating-envelope/my-study
node --test web/test_operating_envelope.mjs web/test_operating_cli.mjs
```

The study runs the independent water proof, checks the frozen inputs, creates a review for each supplied trace and retains commands, exits and file identities. It also checks that mean-only evidence returns `supply_evidence`.

The [frozen protocol](PROTOCOL.md) specifies the input, checks and numerical rules. A declaration is not verified operator authority. Pressure, water quality, flushing consumption, electrical behavior and permission to run remain outside these checks. Stefanos retains the plant model and scheduler; this is an independent review of what is supplied.

[Source research and roadmap responsibility](research.json).

Verified source `d0d28ed`: [GitHub checks](https://github.com/dlukel/aquashift/actions/runs/37148688749) passed all 645 tests and the study. The [retained verification](verification.json) binds the checked sources and handoff. The published interface is unchanged.
