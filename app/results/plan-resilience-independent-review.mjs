// Retained and rerun from two ephemeral independent audit probes.
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {replayPlan} from '../web/public/plan-resilience.mjs';

const times = Array.from({length: 24}, (_, h) => `2026-07-15T${String(h).padStart(2, '0')}:00:00+03:00`);
const tolerance = 1e-6;
const issues = [];
let state = 771;
const rand = () => ((state = Math.imul(state, 1664525) + 1013904223 >>> 0) / 4294967296);
let boundaryCases = 0, demandBoundaryCases = 0, feasibleInitialCases = 0, capacityInsufficientCases = 0;

for (let k = 0; k < 350; k++) {
  const capacity = 20 + rand() * 2000, reserve = capacity * rand() * .7;
  const initial = reserve + (capacity - reserve) * rand(), startHour = Math.floor(rand() * 24);
  const args = {times, production: Array.from({length: 24}, () => rand() * 500), demand: Array.from({length: 24}, () => rand() * 300),
    capacity, reserve, initial, target: initial, startHour,
    scenario: {production_multiplier: rand(), demand_multiplier: rand() * 2, outage: {start_hour: rand() * 15, duration_hours: rand() * 8}}};
  const result = replayPlan(args);
  boundaryCases++;
  const boundary = result.margins.maximum_demand_multiplier;
  if (boundary !== null) {
    demandBoundaryCases++;
    const at = replayPlan({...args, scenario: {...args.scenario, demand_multiplier: boundary}});
    const above = replayPlan({...args, scenario: {...args.scenario, demand_multiplier: boundary + 1e-5}});
    if (at.totals.reserve_margin_m3 < -tolerance || at.totals.unmet_m3 > tolerance ||
        above.totals.reserve_margin_m3 >= -tolerance && above.totals.unmet_m3 < tolerance) {
      issues.push({case: k, type: 'demand boundary', at: at.totals, above: above.totals});
    }
  }
  const required = result.margins.minimum_initial_storage_m3;
  if (required !== null) {
    feasibleInitialCases++;
    const at = replayPlan({...args, scenario: {...args.scenario, initial_storage_m3: required}});
    if (at.totals.reserve_margin_m3 < -tolerance || at.totals.unmet_m3 > tolerance) {
      issues.push({case: k, type: 'initial bound', required, totals: at.totals});
    }
  } else {
    capacityInsufficientCases++;
    const full = replayPlan({...args, scenario: {...args.scenario, initial_storage_m3: capacity}});
    if (full.totals.reserve_margin_m3 >= -tolerance && full.totals.unmet_m3 < tolerance) {
      issues.push({case: k, type: 'false infeasible'});
    }
  }
  if (Math.abs(result.totals.mass_balance_error_m3) > tolerance || result.rows.some(row =>
    Math.abs(row.delivered_m3 + row.unmet_m3 - row.demand_m3) > tolerance || row.delivered_m3 < -tolerance)) {
    issues.push({case: k, type: 'accounting'});
  }
}

// Separate minute-step integration: no use of replay segments or margin formulas.
state = 449;
let minuteStepCases = 0;
for (let k = 0; k < 70; k++) {
  const capacity = 500, reserve = 100, initial = Math.floor(rand() * 501), startHour = Math.floor(rand() * 12);
  const production = Array.from({length: 24}, () => Math.floor(rand() * 400));
  const demand = Array.from({length: 24}, () => Math.floor(rand() * 200));
  const start = Math.floor(rand() * 60) / 4, duration = Math.floor(rand() * 24) / 4;
  const args = {times, production, demand, capacity, reserve, initial, target: initial, startHour,
    scenario: {production_multiplier: .75, demand_multiplier: 1.2, outage: {start_hour: start, duration_hours: duration}}};
  const result = replayPlan(args);
  let storage = initial, spill = 0, unmet = 0, delivered = 0, minimum = initial;
  for (let minute = startHour * 60; minute < 1440; minute++) {
    const hour = Math.floor(minute / 60), off = minute / 60 >= start && minute / 60 < start + duration;
    const made = off ? 0 : production[hour] * .75 / 60, needed = demand[hour] * 1.2 / 60;
    const free = storage + made - needed, discarded = Math.max(0, free - capacity), missed = Math.max(0, -free);
    storage = Math.min(capacity, Math.max(0, free));
    spill += discarded; unmet += missed; delivered += needed - missed; minimum = Math.min(minimum, storage);
  }
  const expected = {final_storage_m3: storage, spill_m3: spill, unmet_m3: unmet, delivered_m3: delivered, min_storage_m3: minimum};
  for (const [field, value] of Object.entries(expected)) {
    if (Math.abs(result.totals[field] - value) > tolerance) issues.push({case: k, type: 'minute-step comparison', field, expected: value, actual: result.totals[field]});
  }
  minuteStepCases++;
}

const paths = ['web/public/plan-resilience.mjs', 'web/public/resilience-ui.mjs', 'web/test_plan_resilience.mjs', 'web/test_workspace.mjs', 'results/plan-resilience-independent-review.mjs'];
const hashes = Object.fromEntries(paths.map(path => [path, createHash('sha256').update(readFileSync(new URL(`../${path}`, import.meta.url))).digest('hex')]));
const receipt = {
  schema: 1,
  status: issues.length ? 'FAIL' : 'PASS',
  executed_at: new Date().toISOString(),
  command: 'node results/plan-resilience-independent-review.mjs > results/plan-resilience-independent-review.json',
  exit_code: issues.length ? 1 : 0,
  runtime: process.version,
  provenance: 'The two ephemeral audit probe algorithms were reconstructed as this retained script and rerun. Random calls, seeds, case counts, bounds and tolerances preserve the original probe semantics. This receipt records this retained execution.',
  scope: 'Independent checks of fixed-plan water accounting and reserve-support bounds. Not a plant model, operational certification or proof of field performance. UI hashes record the reviewed version; this numerical script does not exercise UI behavior.',
  boundary_probe: {seed: 771, cases: boundaryCases, demand_boundary_cases: demandBoundaryCases, demand_multiplier_increment: 1e-5,
    feasible_initial_cases: feasibleInitialCases, capacity_insufficient_cases: capacityInsufficientCases, tolerance_m3: tolerance},
  minute_step_probe: {seed: 449, cases: minuteStepCases, step_minutes: 1, compared_fields: 5, comparisons: minuteStepCases * 5,
    tolerance_m3: tolerance, outage_boundary_grid_minutes: 15},
  issue_count: issues.length,
  issues,
  sha256: hashes
};
console.log(JSON.stringify(receipt, null, 2));
process.exitCode = receipt.exit_code;
