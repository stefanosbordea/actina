# Supplied operating envelope — protocol v1

Frozen before evaluator implementation and retained tests. Prior work was a read-only capability audit and elementary hand derivation; no operating-envelope evaluator or outcome study ran. These fixtures are synthetic, not Paphos plant evidence. Stefanos owns forecasting, plant modelling and scheduling. This work evaluates unchanged supplied traces against separately declared limits.

## Question and scope

Can a supplied trace meet water delivery, reserve and ending stock yet violate a declared unit operating constraint? Return **revise trace**, **supply evidence**, or **checked limits met**. Never return plant authorization or claim recovered solar, electricity savings, optimal scheduling, calibrated Paphos limits, or a novel physical model.

One unit; one net-product-water rate basis; one positive finite elapsed-hour horizon. The checks are maximum rate, minimum rate during explicitly declared production, continuous up/down ramp, minimum online duration and minimum offline duration. Do not model pumps, feed pressure, flushing consumption, startup trajectories, water quality, grid permission or multi-train aggregation. Supplied state history supports duration accounting only. Unknown startup/flush/quality physics remains outside this assessment.

Existing water checks do not answer this question: `web/public/plan-sequence.mjs` and `model/scheduler.py` explicitly exclude ramps/minimum runs; `results/storage-requirements/protocol-v1.json` is water-only. `results/execution-accounting/PROTOCOL.md` evaluates measured totals, not state transitions. The prior throughput proposal in `results/paphos-feasibility/next-protocol-review.json` did not implement these constraints.

Primary motivation: [Hu and Konstantinou, arXiv:2601.07295v1](https://arxiv.org/html/2601.07295v1), §§II-A/II-B, discusses pump operating ranges, flushing and minimum off duration. This numerical preprint supplies neither verified Paphos limits nor measurements for our fixtures. Its optimization and reported benefits are not adopted. Source checked 2026-10-03.

## Input contract

`evaluateOperatingEnvelope(input)` takes:

```json
{
  "schema": 1,
  "kind": "supplied_unit_operating_envelope",
  "unit_id": "synthetic-unit",
  "rate_basis": "net_product_water",
  "horizon": {"start_hour": 0, "end_hour": 2},
  "trajectory": {
    "representation": "continuous_piecewise_linear",
    "points": [{"hour": 0, "rate_m3_h": 2}, {"hour": 2, "rate_m3_h": 2}]
  },
  "states": [{"from_hour": 0, "to_hour": 2, "state": "online", "producing": true}],
  "initial_state": {"state": "online", "age_hours": 2},
  "limits": {
    "maximum_rate_m3_h": 5,
    "minimum_production_rate_m3_h": 0,
    "ramp_up_m3_h2": 3,
    "ramp_down_m3_h2": 3,
    "minimum_online_hours": 0,
    "minimum_offline_hours": 0
  }
}
```

- Identity, basis and horizon are required. Nonempty unit identity; finite nonnegative start; end strictly later. All declared rates, limits and ages are finite nonnegative numbers. Declared production minimum cannot exceed declared maximum.
- `trajectory`, `states`, `initial_state` and `limits` may be absent/null. Absent limit keys and null limit values mean unknown, never zero/infinity/default permission. An empty limits object is allowed and cannot pass overall. Reject unknown schema fields and unsupported basis/representation/state names.
- A continuous piecewise-linear trajectory has at least two points at strictly increasing hours, starts exactly at the horizon start and ends exactly at its end. Every connecting segment is the supplied continuous path; there are no implicit jumps, interpolation outside the horizon or fitted points.
- Alternate trajectory: `{"representation":"interval_mean","intervals":[{"from_hour":0,"to_hour":2,"rate_m3_h":2}]}`. Means form an exact, ordered, positive-duration, gap-free partition. They are not point rates or a continuous path. Never connect their means to manufacture ramps.
- `states` is null or a complete ordered positive-duration partition using `state:"online"|"offline"` and `producing:true|false|null`. `producing:true` requires online. Offline implies not producing. For online intervals, null producing means unknown applicability of the minimum production rate. Online/production states are supplied declarations; positive flow does not establish online/production state and zero flow does not establish offline state. No unstated zero-flow requirement is imposed on offline/nonproduction records.
- `initial_state` describes the state immediately before the horizon start and its elapsed age at that boundary. Its state is online/offline; age can be null. A different first interval state establishes a transition exactly at the horizon start. A matching state carries its age into the first run. Missing initial state leaves the boundary history unknown.
- No extrapolated shutdown at the horizon end. State intervals are half-open; the final one has a left limit at the ending boundary. Rate-bound tests on a productive interval may use endpoint limits because the supplied path is continuous.
- Bound input size to at most 26,352 rate points/mean intervals and 26,352 state intervals. This is an evaluation resource bound, not a plant sampling requirement.

## Exact checks

Interpret every parsed finite binary64 input as its exact rational value, including elapsed-hour endpoints. Subtract exact times before division/multiplication. Numeric comparison tolerance is **zero**. Equality meets the bound. No hidden epsilon or rounded display decides status. Physical uncertainty is not a floating-point tolerance and is not modelled here. Keep tiny representation residuals as exact accounting distinctions; do not describe them as material field failures.

For continuous points `(t_i,q_i)`, the slope is `(q_(i+1)-q_i)/(t_(i+1)-t_i)` in m³/h². Maximum-rate extrema occur at vertices. For each declared productive state interval, evaluate the continuous path at its boundaries and contained vertices; its minimum is attained among those values. State boundaries need not coincide with rate samples. Ramp-up checks slope ≤ declared up limit; ramp-down checks −slope ≤ declared down limit. Opposite-signed slopes do not violate a nonnegative limit. Checks apply throughout the declared horizon, regardless of online state, except the explicitly production-conditioned minimum rate.

Interval means retain necessary failures: a mean above the maximum proves that maximum could not hold throughout its interval. A mean below the minimum proves a failure only if its **whole interval** is explicitly productive. A partly productive interval cannot be subdivided into invented mean rates. Otherwise means cannot certify pointwise rate compliance; ramps remain unknown. A wholly nonproductive horizon makes the minimum-production check not applicable when its limit is declared. Missing production applicability remains unknown. Violations proven elsewhere are retained despite unknown portions.

For durations, merge adjacent intervals with the same online/offline state, ignoring producing-flag changes. At an observed transition, compare the completed run's actual known duration with its corresponding minimum. Add initial age to the first run only when the initial state matches. If a transition occurs exactly at the start, check the supplied prior state's age as a completed run too. A newly witnessed transition establishes the next run's start exactly.

When the first run's age is unknown, its visible duration is a lower bound: visible duration ≥ minimum suffices for that completed run; shorter visible duration is unknown, not a violation. If `initial_state` itself is missing, a possible transition from the opposite state at the start remains unknown for that opposite state's positive minimum; do not certify an unobserved boundary. A declared zero minimum needs no history to meet that constraint.

The final run is not completed. If its known elapsed duration meets its minimum, it adds no obligation. Otherwise report required continuation as a tail obligation and mark that duration check unknown, not violated. For known age, remaining minimum and maximum are both `minimum-age`. For unknown age with visible duration v, remaining range is `[0,max(0,minimum-v)]`; history is needed to resolve it. Requirements extend beyond supplied evidence, never into an invented stop. Missing entire state data makes duration checks unknown even if zero limits were supplied: there is no state history to assess.

A declared check with no applicable runs/production intervals is `not_applicable` only if complete supplied evidence establishes that absence and no unresolved start boundary affects it. Missing limits always remain unknown. Within a check, known violation outranks unknown portions; otherwise unknown outranks met/not_applicable.

## Result contract

Top-level shape:

```json
{"schema":1,"kind":"supplied_unit_operating_envelope_review","status":"met|violated|unknown","decision":"checked_limits_met|revise_trace|supply_evidence","checks":{"maximum_rate":{},"minimum_production_rate":{},"ramp_up":{},"ramp_down":{},"minimum_online":{},"minimum_offline":{}},"tail_obligations":[],"scope":[]}
```

Each check has `status: met|violated|unknown|not_applicable`, `reasons:[]`, and `violations:[]`. Each violation has `kind`, `from_hour`, `to_hour`, `observed`, `limit`, `excess_or_shortfall`, and `sources` (JSON-pointer strings identifying input evidence). All fields except kind/sources are quantities. Kinds are `point_rate`, `productive_rate`, `segment_slope`, `interval_mean_bound`, or `completed_duration`. Excess/shortfall is strictly positive; units follow the check. Rate/ramp extrema can identify a point or segment; mean-based witnesses identify the whole interval and never invent an instant. Duration witnesses identify the completed run/transition, including explicit pre-horizon history where used. No particular diagnostic prose is required; mathematical expectations and exact values below may not change.

Quantities use `{value:number|null,exact:{numerator:string,denominator:string}}`; numeric value is display only. Null display means a nonzero exact quantity lies outside finite nonzero binary64 display range, not missing evidence. Tail obligation fields: `state`, `at_hour`, `remaining_min_hours`, `remaining_max_hours`, with quantities in this convention.

Any check violated → overall violated / revise_trace. Otherwise any check unknown or unresolved tail → unknown / supply_evidence. Otherwise → met / checked_limits_met. Scope must state declared single-unit checks only, no plant authorization, no forecast/schedule generation and no electricity/solar-benefit claim. Input/schema errors throw; they are not ordinary unknown evidence.

## Frozen experiment and expectations

`protocol-fixtures.json` contains hand-derived expectations, written before the evaluator and test implementation. All examples are synthetic. Expected rational strings are exact; final witness field-name adapters may select them without changing expected mathematics. Invalid-input fixtures must reject rather than quietly sort, bridge gaps, coerce types or assume missing values.

Matched water counterexample: triangular continuous rate samples `(0,0),(1,4),(2,0)` versus constant rate 2, same demand 2, initial stock 2, capacity 4, reserve 1, terminal target 2. Both produce/deliver 4 m³ and end at 2 m³. Triangle inventory is `2+2t²−2t` on `[0,1]` and `6t−2t²−2` on `[1,2]`; minimum 3/2 at t=1/2, maximum 5/2 at t=3/2. Flat inventory remains 2. Both are water-feasible; a declared up/down ramp limit 3 rejects triangular slopes ±4 and admits flat slopes 0. Do not substitute the existing uniform-hour replay for this within-hour calculation.

Freeze fixtures, protocol and source hashes before evaluating. Retain commands, exit status, input and implementation hashes, failures, and output witnesses. Independent tests use rational arithmetic or direct interval-duration accounting, not evaluator internals. Include exact-equality, just-over-bound, missing declaration, mean-versus-trajectory, producing applicability, merged state intervals, carried initial age, unknown initial age, observed start transition and unfinished tail cases. Numerical nonzero residuals remain visible and qualified.

The current hourly-reference corpus supplies means and no complete unit-state/initial-age/operating-limit evidence. Its correct demonstration is missing evidence, not interpolated ramp violations or inferred startup counts. No authenticated Paphos limit packet has been identified. This protocol can justify revising a supplied trace under its declared limits or requesting the missing evidence; it cannot establish actual plant feasibility.
