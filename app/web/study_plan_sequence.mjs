import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {mkdirSync, readFileSync, writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {replayPlan} from './public/plan-resilience.mjs';
import {replaySequence} from './public/plan-sequence.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== '--output') throw Error('Usage: node web/study_plan_sequence.mjs --output <new-directory>');
const output = resolve(args[1]), HOUR = 3600000, EPS = 1e-6;
const sha = value => createHash('sha256').update(value).digest('hex');
const sources = ['web/public/data.json', 'web/public/manifest.json', 'web/public/plan-resilience.mjs', 'web/public/plan-sequence.mjs', 'web/study_plan_sequence.mjs', 'results/continuous-plan-study/PROTOCOL.md'];
const bytes = Object.fromEntries(sources.map(path => [path, readFileSync(resolve(root, path))]));
const hashes = Object.fromEntries(sources.map(path => [path, sha(bytes[path])]));
const data = JSON.parse(bytes[sources[0]]), manifest = JSON.parse(bytes[sources[1]]);
assert.equal(hashes[sources[0]], manifest.data_sha256);
assert.equal(data.days.length, 92); assert.equal(manifest.days, 92); assert.equal(manifest.schedules, 460);
assert.deepEqual(data.tanks, [500, 1000, 2000, 4000, 8000]);
assert.equal(data.demand, 120); assert.equal(data.unit_capacity, 500);
assert.equal(data.days[0].date, '2026-07-01'); assert.equal(data.days.at(-1).date, '2026-09-30');
mkdirSync(output, {recursive: false});
const started = new Date().toISOString();
const conditions = [
  {id: 'nominal', scenario: {}},
  {id: 'demand_10', scenario: {demand_multiplier: 1.1}},
  {id: 'demand_20', scenario: {demand_multiplier: 1.2}},
  {id: 'production_loss_10', scenario: {production_multiplier: .9}},
  {id: 'midday_outage', scenario: {}, outage: true},
  {id: 'combined_10', scenario: {demand_multiplier: 1.1, production_multiplier: .9}}
];
const policies = ['retained_reference', 'flat_120_m3_h'];
const dailyKeys = ['initial_storage_m3', 'final_storage_m3', 'min_storage_m3', 'available_production_m3', 'demand_m3', 'delivered_m3', 'unmet_m3', 'spill_m3', 'max_reserve_deficit_m3', 'mass_balance_error_m3'];
const columns = ['tank_m3', 'condition_index', 'policy_index', 'block_index', ...dailyKeys];
const daily = [], pairs = [], selected = [];
function sum(values) {
  let total = 0, correction = 0;
  for (const value of values) { const adjusted = value - correction, next = total + adjusted; correction = (next - total) - adjusted; total = next; }
  return total;
}
function inputFor(tank, condition, policy) {
  return {capacity: tank, reserve: tank * .2, initial: tank * .5, target: tank * .5, unitCapacity: data.unit_capacity,
    blocks: data.days.map(day => ({times: day.times, production: policy === 0 ? day.schedules[String(tank)].production : Array(24).fill(data.demand), demand: data.demand})),
    scenario: condition.scenario, outages: condition.outage ? data.days.map(day => ({start: day.times[12], end: new Date(Date.parse(day.times[12]) + 2 * HOUR).toISOString()})) : []};
}
function resetDiagnostic(input, condition) {
  const records = [], additions = [], removals = [];
  let previous = input.initial;
  for (const [i, block] of input.blocks.entries()) {
    const transfer = i ? input.initial - previous : 0;
    additions.push(Math.max(0, transfer)); removals.push(Math.max(0, -transfer));
    const replay = replayPlan({...block, capacity: input.capacity, reserve: input.reserve, initial: input.initial, target: input.target,
      scenario: {...condition.scenario, ...(condition.outage ? {outage: {start_hour: 12, duration_hours: 2}} : {})}});
    records.push(replay.totals); previous = replay.totals.final_storage_m3;
  }
  const totals = Object.fromEntries(['available_production_m3', 'demand_m3', 'delivered_m3', 'unmet_m3', 'spill_m3'].map(key => [key, sum(records.map(r => r[key]))]));
  Object.assign(totals, {initial_storage_m3: input.initial, final_storage_m3: previous, artificial_added_m3: sum(additions), artificial_removed_m3: sum(removals)});
  totals.mass_balance_error_m3 = input.initial + totals.artificial_added_m3 - totals.artificial_removed_m3 + totals.available_production_m3 - totals.delivered_m3 - totals.spill_m3 - previous;
  assert.ok(Math.abs(totals.mass_balance_error_m3) <= EPS, 'Reset diagnostic accounting');
  return {scope: 'Artificial daily reset; post-first water additions/removals are not physical supply.', totals,
    daily: records.map((r, i) => ({block_index: i, added_m3: additions[i], removed_m3: removals[i], totals: r}))};
}
for (const tank of data.tanks) for (const [conditionIndex, condition] of conditions.entries()) {
  const pair = {tank_m3: tank, condition_id: condition.id, initial_storage_m3: tank * .5, policies: {}};
  for (const [policyIndex, policy] of policies.entries()) {
    const input = inputFor(tank, condition, policyIndex), untouched = JSON.stringify(input), result = replaySequence(input);
    assert.equal(JSON.stringify(input), untouched, 'Source plans were mutated');
    assert.equal(result.rows.length, 92 * 24); assert.equal(result.blocks.length, 92);
    assert.ok(Math.abs(result.totals.mass_balance_error_m3) <= EPS, 'Global continuous accounting');
    assert.ok(result.totals.max_abs_accounting_residual_m3 <= EPS, 'Exposed hourly/block/global accounting');
    for (const [i, block] of result.blocks.entries()) {
      assert.equal(block.initial_storage_m3, i ? result.blocks[i - 1].totals.final_storage_m3 : input.initial, 'Inventory carry');
      daily.push([tank, conditionIndex, policyIndex, i, ...dailyKeys.map(key => block.totals[key])]);
    }
    if (condition.id === 'nominal' && policyIndex === 0) for (const [i, row] of result.rows.entries()) {
      assert.ok(Math.abs(row.storage_end_m3 - data.days[Math.floor(i / 24)].schedules[String(tank)].storage[i % 24]) <= EPS, 'Nominal retained trajectory');
    }
    const reset = resetDiagnostic(input, condition);
    pair.policies[policy] = {continuous: {totals: result.totals, events: result.events}, daily_reset: reset};
    if (tank === 4000 && condition.id === 'demand_10') {
      const firstWeek = {...input, blocks: input.blocks.slice(0, 7)};
      const week = replaySequence(firstWeek);
      selected.push({policy, input: firstWeek, result: week});
      if (policyIndex === 0) writeFileSync(resolve(output, 'seven-day-demand-10-source.json'), JSON.stringify({schema: 1, kind: 'fixed_plan_sequence_source', label: 'Illustrative retained plans, 1–7 July 2026', control_rate_m3_h: 120, specific_energy_kwh_m3: 3.4, inputs: firstWeek}, null, 2) + '\n', {flag: 'wx'});
    }
  }
  const a = pair.policies[policies[0]].continuous.totals, b = pair.policies[policies[1]].continuous.totals;
  pair.reference_minus_flat = Object.fromEntries(['available_production_m3', 'delivered_m3', 'unmet_m3', 'spill_m3', 'final_storage_m3'].map(key => [key, a[key] - b[key]]));
  pairs.push(pair);
}
assert.equal(pairs.length, 30); assert.equal(daily.length, 5520); assert.equal(selected.length, 2);
const flatWeek = selected.find(r => r.policy === policies[1]);
assert.ok(Math.abs(flatWeek.result.totals.unmet_m3 - 16) <= EPS, 'Seven-day flat analytical unmet demand');
assert.ok(Math.abs(Date.parse(flatWeek.result.events.find(e => e.type === 'stockout').time) - (Date.parse(flatWeek.input.blocks[0].times[0]) + 2000 / 12 * HOUR)) <= 1, 'Flat analytical stockout instant');
for (const path of sources) assert.equal(sha(readFileSync(resolve(root, path))), hashes[path], `Changed during study: ${path}`);
const report = {schema: 1, kind: 'continuous_fixed_plan_study', status: 'completed', started_at: started, completed_at: new Date().toISOString(),
  command: [process.execPath, ...process.argv.slice(1)], source_sha256: hashes, inputs_unchanged: true,
  design: {days: 92, tanks: data.tanks, conditions, policies, continuous_trajectories: 60, continuous_block_replays: daily.length,
    daily_reset_diagnostic_replays: daily.length, additional_first_week_demonstration_replays: 14, dates: data.days.map(d => d.date), numeric_tolerance_m3: EPS},
  pairs, daily: {columns, rows: daily},
  limitations: ['Illustrative retained fixed plans and persistent declared disturbances; no new schedule or forecast.',
    'Both alternatives start with the same water once. Larger tank comparisons also change starting inventory.',
    'Daily-reset diagnostic explicitly counts artificial water transfers. They are not actual supply.',
    'Higher final inventory may accompany worse service; no single overall winner or savings claim.',
    'Hourly uniform flows; no ramps, minimum runs, water quality, pressure, real plant measurements or operating authority.',
    'First-event and accounting behavior is separately checked by the independent oracle; this report alone is not independent validation.']};
for (const [name, value] of [['study.json', report], ['first-week.json', selected]]) writeFileSync(resolve(output, name), JSON.stringify(value) + '\n', {flag: 'wx'});
console.log(JSON.stringify({output, pairs: pairs.length, continuous_trajectories: 60, block_replays: daily.length, first_week_flat_unmet_m3: flatWeek.result.totals.unmet_m3}));
