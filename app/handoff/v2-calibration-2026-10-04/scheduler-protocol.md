# Test scheduling comparison

**Withdrawn handoff, pending replacement.** Stefanos deleted the 15:32 request while this draft was being prepared. Root instructed a hold. This is a retained proposal, not an approved or executed study. No new v2 test prediction was read, no schedule was run and no original model file was changed. Validation threshold selection remains separate.

## What the supplied scheduler actually does

`model/scheduler.py` uses production between 100 and 400 m³/h, tank capacity 4,000 m³, initial stock 2,000 m³, reserve 800 m³ and fixed energy 3.4 kWh/m³. Demand is base 200 m³/h multiplied by the supplied hourly shape, a 1.15 multiplier in June–September and a 1.10 multiplier when the target hour's realized temperature exceeds 30°C. This demand is a retrospective scenario shared by every method, not an independently issued demand forecast.

Initial production is 400 when forecast GHI is strictly above 600 and 100 otherwise. The reserve-repair loop ranks hours by the continuous forecast, highest first, with earlier hours winning equal-value ties. Therefore the scheduler uses both event decisions and irradiance ranking. A 0/1 or two-level surrogate for 008 would discard information and change the method unnecessarily.

Realized cost uses €101/MWh when **actual** GHI is strictly above 600, otherwise €183/MWh. These are illustrative prices linked to a radiation proxy, not measured market prices, proven curtailment or the later 011 clock tariff. `run()` carries stock from one day to the next and does not require final stock to equal initial stock. Its printed €/m³ divides each method's total cost by its own production. That faithful statistic alone is not an equal-water saving.

The earlier `app/tools/reproduce_scheduler.py` preserves the source and runs isolated copies. Its retained unchanged and persistence reproductions are relevant implementation controls. Do not import the original scheduler directly, because its module-level code executes and writes `eval/schedule_hourly.csv`.

## Requested methods and inputs

If the request is renewed, first freeze source identities and the validation-selected v2 threshold. Then open the test inputs once and require exact joins to the unchanged original test support. Use the original 24-hour shift from CSV feature time to target time. Keep the original complete target days, demand and actual radiation. Refuse missing, duplicate or mismatched rows instead of improving results by dropping days. Preserve the excluded partial boundary days.

| Requested label | Initial production calls | Reserve-repair ranking |
|---|---|---|
| Yesterday | Original `baseline > 600` | Original continuous baseline |
| v1 | Original test `predicted > 600` | Original continuous prediction |
| Raw forecast | Supplied v2 CSV `forecast > 600` | That exact supplied forecast column |
| v2 tuned | Supplied v2 `predicted > frozen validation threshold` | Original continuous v2 prediction |
| 008 | Frozen selected consensus-two-source calls, lower .50 / upper .60 | Its retained raw ECMWF day2 values |
| Perfect forecast | `actual > 600` | Actual GHI |

Raw forecast here means the supplied v2 column. It must not silently become the older ECMWF day2 source. Their issue provenance differs or is unverified. These are matched target-hour comparisons, not proof of matched historical issuance. Flat daily-mean production is the common reference and an additional row.

The isolated helper should accept two separate inputs, event bits and ranking values. Only the original initial-production expression changes to consume the bits. Keep the cap/repair order, minimum rate, maximum rate, tank carry, sorting ties and iteration budget unchanged. For any ordinary 600-threshold forecast, verify this helper reproduces the original function exactly before applying tuned or 008 bits. Keep the original source bytes intact and retain the wrapper diff.

## Faithful original result

First retain the requested unmodified-policy comparison. For each row save hourly production, demand, inventory, actual tariff, total produced water, delivered demand, initial/final stock, minimum/maximum stock, constraint violations, total cost and €/m³. Flat remains exactly the original daily-mean rule.

Define `unit_cost = total_cost / total_production` and `saving_vs_flat_pct = 100*(1-unit_cost/flat_unit_cost)`. For this diagnostic, a percentage of perfect-forecast saving can be `100*(flat_unit_cost-unit_cost)/(flat_unit_cost-perfect_heuristic_unit_cost)`, explicitly labeled **share of same-heuristic perfect-forecast saving**. It is not an optimality bound. Keep negative values and values above 100. A nonpositive denominator is undefined, not zero or a passing result. Unequal production and ending inventory must appear beside these numbers.

## Proposed matched-service result, separately labeled

The smallest useful normalization is to keep every method's original production until the final complete test day, then reconcile that day's plan to end at the common initial stock of 2,000 m³. This avoids a new whole-period planner and preserves the supplied controller's earlier behavior and stock carry. The correction uses the final day's current stock, shared demand, original proposed plan and forecast ranking, not actual tariff or radiation. It is an evaluation settlement convention, not a learned improvement.

On that final day choose the feasible plan closest in total absolute hourly production difference to the original proposal. Retain the same 100–400 production limits, 800–4,000 inventory bounds, final-day starting stock and hourly demand. Require final stock 2,000. Resolve equally close solutions using a fixed linear preference for the supplied sunnier-hour ranking, then the pinned deterministic solver. Declare numerical tolerances and retain residuals before execution. Do not change prices or repair any earlier infeasibility. If any plan or flat is infeasible, retain the failure and do not produce a matched-service saving for it.

All feasible normalized methods then deliver the same demand, produce the same total water and finish with the same stock. Their nominal total desalination energy is also equal. Calculate total cost under the same actual-price series, then €/m³ using the common water denominator. Report how much final-day production was changed so the normalization's effect is visible.

For the matched result, use a separate **perfect-information minimum-cost bound** with these same physical constraints, initial/final stock, demand and actual prices over the exact test horizon. A clairvoyant linear optimizer is appropriate only for this explicit benchmark. It is not a substitute for Stefanos's scheduler in any forecast row. The original same-heuristic perfect row remains in the faithful diagnostic, while this bound provides the defensible ceiling in the matched table.

Set `saving_vs_flat_pct = 100*(C_flat-C_method)/C_flat` and `perfect_saving_captured_pct = 100*(C_flat-C_method)/(C_flat-C_oracle)`. Require positive denominators. Do not cap negative values or values above 100. Audit unexpected bound violations rather than clipping them. This is an illustrative forecast-to-price scheduling comparison, not recovered-solar or field-profit evidence.

## Work needed after a replacement request

Confirm the original/matched panel distinction and terminal settlement before freezing execution. Implement the isolated bits/ranking wrapper, complete-day joins, original-source reproduction fixtures, final-day normalization and the clearly labeled clairvoyant bound. Pin all inputs, frozen v2 selection, source code and numerical choices. Preserve per-hour outputs, all failures, actual commands and exit statuses. Independently replay mass balance, terminal stock, tariffs and aggregate ratios.

No extra all-axis research gate is required for this comparison. Report the requested euros and percentages alongside service and provenance evidence. The presently withdrawn request authorizes no simulation or test-file access under this draft.
