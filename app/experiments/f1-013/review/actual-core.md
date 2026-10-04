# Independent actual-core review

The actual `decision.py` passed the separate full-action oracle on 3,143 synthetic cases. This is implementation evidence, not a forecast-quality result. No historical scenario files, candidate actions or realized outcomes were opened by this check.

The executed source SHA256 is `8812e5dbe66a8f1d389103d0a4ab9945540e21335319067fb431e0f8dcdd7f30`. The reviewer imports only the production module under test. Its oracle reconstructs exact scenario ratios, exhausts all possible action bitmasks and ranks feasible actions independently. It does not call production score, coefficient, reduction or ranking helpers to determine the expected answer.

The 407,109 checks cover every two-hour, two-reference, two-scenario distribution and every raw vector, 128 seeded four-hour distributions with all raw vectors, 64 eight-hour cases with forced unanimous hours, and explicit edge cases. They check all 40,032 actual ledger records, including rejected actions and exact failed safeguards. Every coefficient for every possible positive K is checked separately against direct scenario sums.

Both objectives matched the full-action optimum in every case. There were 3,340 strict-gain selections and 2,946 raw fallbacks across the two objectives. Count increases and decreases both occurred. Tie resolution was exercised at changed-bit count, K and selected-hour tuple. Shared scenario permutation and uniform path repetition preserved selected actions. The check also rejected ten malformed inputs, an expired deadline and safeguards smaller than binary64 resolution.

Undefined precision at K=0 stays null. Conditional recall is null only when no scenario contains a positive truth. Empty action with empty truth has empirical F1=1. A positive raw count prohibits an empty candidate. All-empty truth with positive raw count retains raw. These conventions agree with the protocol and differ deliberately from undefined observed empty-day metrics.

## Preserved coverage failure

Attempt 001 exited 1 because its fixtures never reached the smaller-K tie breaker. It found no solver disagreement. The complete first log, execution receipt and checker source remain as `core-check-001.log`, `core-execution-001.json` and `core-check-001.py`.

The added fixture has eight scenarios with truth `{1}` and five with truth `{0,2}`, identically under both references. Raw is `{0}`. Actions `{1}` and `{0,1,2}` both score F1=8/13 and change two raw bits. Intermediate pairs score less. The smaller-K rule selects `{1}`. Attempt 002 then passed, including two exercised K-tie resolutions.

Attempt 002 exited 0 in 7.84 wall seconds, with 7.62 seconds inside the checker, 5.43 CPU seconds and peak macOS RSS 33,701,888 bytes. The subprocess receipt records the exact command, source and log hashes. `core-result.json` is extracted unchanged from that retained log.

Reproduce from the repository root with the installed Python environment:

```text
/Users/kixem/Documents/Loucas-Stefanos-Workspace-2026-09-19/AquaShift/.venv/bin/python app/experiments/f1-013/review/core-check.py
```

Finite synthetic coverage does not prove behavior for arbitrary inputs. The algebraic argument is recorded separately in `mathematics.md`. Historical source identity, freeze sequencing, joins, masks, decisions and observed metrics still require the runner audit and post-run independent reconstruction.
