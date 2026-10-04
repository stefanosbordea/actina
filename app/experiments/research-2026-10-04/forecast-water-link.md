# Connecting event corrections to water scheduling

Proposal dated 2026-10-04. No 013 outcome or candidate-call file was read for this proposal. No new schedule was run. The inspected sources are the 013 protocol and implementation, `app/model/scheduler.py`, the 011 optimizer and protocol, and the 012 protocol, runner and retained report. This is an implementable retrospective study, pending its own frozen protocol, fixtures and independent review.

The strongest faithful test of the **specific 013 intervention** is a declared minimal change to raw irradiance that reproduces its exact event calls, followed by the unchanged 011 solar-aware point optimizer. It tests a concrete interface choice. Binary event decisions alone do not identify irradiance magnitude, and a positive scheduling result would not establish a calibrated numerical forecast.

## Why a separate connection is needed

The app scheduler minimizes a clock tariff. Radiation contributes only a `1e-6` preference within tariff ties. Its reported high-radiation flags use `>=600`, whereas 013 defines an event by strict `>600`. Feeding new calls to that display or comparing its tariff savings would neither reproduce the event definition nor establish a substantive forecast-to-grid connection.

The 011 optimizer actually uses forecast PV in grid purchases. For a fixed feasible water plan `q`, its hourly grid requirement is `max(3.4*q - PV, 0)`. This is the appropriate unchanged downstream mechanism. Replacing it with a binary discounted tariff or rewarding production in flagged hours would introduce an artificial benefit mechanism.

| Route | What it would establish | Decision |
|---|---|---|
| Minimal class-consistent change to raw GHI, then the unchanged point optimizer | The downstream effect of the exact calls through one fully specified, least-change interface | Primary proposal |
| Reuse original conditional scenarios in the 012 optimizer | The value of those scenarios for water scheduling | Retain as strong control. It does not carry the particular 013 event intervention |
| Condition, truncate or reweight scenarios as if the selected event bits were observations | A new predictive distribution whose calibration and interpretation need a separate argument | Exclude. The bits are decisions computed from the same scenarios, not new observations |
| Use 009's saved mean, median or quantiles | A different continuous or probabilistic forecast experiment | Exclude from this matched issue study. Saved 009 rows have rolling hourly origins, and its selected event policy is not its mean or median |
| Give flagged hours a new price, fixed PV output or arbitrary irradiance margin | The effect of a new physical or economic assumption | Exclude |

In particular, concatenating the 009 forecasts for a calendar day does not make all their information available at the previous day's 00:00 issue. A future common-issue 009 reforecast could be a separate study with its own training and information audit. The original, persistence, 008 and 009 event comparisons remain in the 013 evaluation on their exact original hours.

## One mapping, declared before outcomes

For raw binary64 GHI `f[h]` and frozen 013 bit `x[h]`, define:

```text
boundary_positive = nextafter(float64(600), float64(+infinity))
g[h] = max(f[h], boundary_positive)  if x[h] is true
g[h] = min(f[h], float64(600))       otherwise
```

This leaves every already-consistent raw value unchanged. It changes only an added or removed event, by the smallest representable magnitude needed to satisfy its class. The false class includes 600. The true class starts at `0x1.2c00000000001p+9`, exactly one binary64 step, `2^-43` W/m², above 600.

Over real numbers the positive class is open, so an added event has no attained nearest point. The binary64 restriction supplies the stated numeric choice. Do not silently replace it with 600, 601, a rounded decimal or a learned margin. Save raw and mapped values in numeric NPZ arrays, including exact binary identities. Check `g > 600` against every saved 013 bit after serialization. Do not route this through the app's inclusive display threshold.

The chain is raw GHI and retained historical scenarios → frozen 013 bits → this mapping → unchanged PV conversion → unchanged point optimization → fixed water plan → later reference-based scoring. Use the four predeclared 013 arms, with conditional robust still primary. No selection based on their event or water outcomes. No revised neighbor sets, new probabilities, calibration, projection scale or new fit.

This is an event-consistent scheduling input, not a measured irradiance correction. Record continuous MAE and RMSE against both references as separate diagnostics. Those scores may worsen even if event scores improve. A one-step boundary addition may have negligible physical effect, which is a legitimate result rather than a reason to enlarge its magnitude.

## Frozen matched comparison

1. Pin the completed 013 decision-freeze artifacts and independent audit, the 012 planning manifest, all relevant arrays, source joins and the exact 011 optimizer. Consume 013 calls for all 299 padded horizons without opening its outcome tables to choose arms. If a required artifact is incomplete or a hash differs, stop before new scoring.
2. Retain all 150 validation and 149 test horizons. Keep their issue D−1 00:00 fixed UTC+03, endpoints D00–D23, physical intervals D−1 23:00 through D23:00, and fixed historical cutoffs. Neither outcome availability nor successful event correction selects a planned day. Historical publication availability remains unverified.
3. Copy all six saved 012 controls unchanged: tariff context, raw point, recency intact, recency shuffled, conditional intact and conditional shuffled. Both conditional controls are mandatory because neither dominates every existing metric. Do not choose the weaker one or a different comparator for each day. Tariff context is descriptive, never the principal control.
4. Generate four new mapped point plans. Use `solve(pv(g))` with no risk anchor, exactly the existing point objective and tie rules. The corresponding raw control is `solve(pv(f))`. First reproduce all 299 saved raw-point controls using the pinned environment, recording bitwise equality and maximum differences, with the existing 1e-6 m³ audit tolerance as the refusal threshold. Keep the original archived plans for scoring. If a mapping equals raw bit for bit, copy that archived raw plan exactly and record the deterministic identity instead of creating a numerical tie difference.
5. Keep demand 120 m³/h, production 0–500 m³/h, tank 4,000 m³, reserve 800 m³, initial and final storage 2,000 m³, and SEC 3.4 kWh/m³. Every plan delivers 2,880 m³ and uses 9,792 kWh of nominal desalination energy. Keep PV `min(1700, 1.7*max(GHI,0))`, unlimited grid backup, no export value and the existing endpoint-hour €101/183/130 per MWh tariff. Preserve the 011 action floor, objective caps, solver tolerances and tie rules. No new physical or tariff parameter.
6. Save and hash all ten methods on all 299 horizons before loading evaluation references or masks. This produces 2,990 retained plan records, including 1,196 new candidate records. An unchanged-input identity record remains a candidate record. Retain source clocks, exact event bits, GHI/PV differences, production, inventory, every solver status and actual execution receipt.
7. Score the unchanged 139 validation and 144 test complete common-reference horizons under weather and satellite separately. Retain the 148 complete weather-only days per period as sensitivity. Keep all excluded and partial days with reasons. Event and continuous forecast diagnostics additionally use 013's unchanged original-hour masks, not these reduced physical-day masks.

## Outcomes and decision rule

Recompute water balance and grid consumption from saved production, without trusting optimizer slack variables. Preserve exact rational water residuals alongside the existing numerical tolerances. Report total water and plant energy, inventory limits, mean and CVaR90 grid cost and grid energy, unused PV, peak grid power, and full daily outcomes under each reference. Grid import reduction is not desalination-energy reduction.

For every candidate, retain the full paired comparison against **each** of the five non-tariff controls, including both conditional 012 plans. Report daily cost and grid differences, their mean, CVaR90, extrema and better/equal/worse counts. Calculate daily cost-regret CVaR separately from the difference between two cost CVaRs. Preserve tiny differences and flag values below the existing reporting resolution without turning them into exact ties.

Keep the existing eight-axis aggregate gate and daily-regret risk gate in each period. An operational upgrade recommendation requires verified identical service and both gates against raw point **and every retained non-tariff control**, in both periods. No arm, day, reference, metric or control may be dropped after inspection. Report narrower raw-control gains separately if stronger controls win. Retain the unchanged 013 event gates as a distinct finding. A water gate cannot erase a precision, recall or F1 regression, and an event gate cannot imply water benefit.

At minimum, independent fixtures and replay must check strict 600 equality and adjacent floats, no-change identity, additions and removals, invalid input refusal, exact NPZ round trip, threshold preservation, point-control reproduction, complete issue/mask identities, water constraints and fractional-tail CVaR. Also check the fixed-plan sensitivity bounds `abs(grid(P1)-grid(P2)) <= sum(abs(P1-P2))` and `abs(cost(P1)-cost(P2)) <= sum(price*abs(P1-P2))`. These are diagnostics for the interface, not bounds on realized costs after the plan changes.

No 013 outcomes have been examined here, but earlier experiments used the same historical periods. This remains exploratory. A favorable result can justify testing this exact interface prospectively. A null or adverse result rejects this particular connection, not every possible amplitude model. Local operating limits, issued-data availability, genuine curtailment and field savings remain separate evidential requirements.

## Primary-paper grounding

- [Elmachtoub and Grigas, Smart “Predict, then Optimize”, arXiv v5](https://arxiv.org/pdf/1710.08005), PDF pp. 8–11, §§2–3 and Definition 1, explicitly evaluates the downstream decision induced by a forecast. Its linear cost-vector setting does not directly supply a training loss for our PV-dependent grid epigraph. We adopt the paired decision-evaluation principle, not its SPO+ method or guarantees.
- [Donti, Amos and Kolter, NeurIPS 2017](https://proceedings.neurips.cc/paper/2017/file/3fc2c60b5782f641f76bcefc39fb2392-Paper.pdf), PDF pp. 7–8, Eq. (11) and §4.2, separates prediction error from realized generation-scheduling cost. That supports checking both here. No differentiable training or transfer of their numerical gains is proposed.
- [Hu and Konstantinou, Stochastic Power-Water Coordination](https://arxiv.org/pdf/2601.07295), PDF pp. 4–5, Eqs. (24)–(42), models salt balance, flushing and storage constraints omitted by the retained fixed-efficiency plant. Their model motivates these stated limits, not a claim that this illustrative plan is plant-ready.

The missing numeric magnitude is an identifiability limit of binary calls, not a blocker to the explicitly declared experiment above. No new data or algorithm is needed to execute that bounded chain. It must not be presented as an inherent physical consequence of higher F1 or as a new scientific invention.
