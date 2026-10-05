import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve, relative} from 'node:path';
import {performance} from 'node:perf_hooks';
import {replayPlan} from './public/plan-resilience.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
if (args.length !== 2 || args[0] !== '--output') throw Error('Usage: node web/study_plan_resilience.mjs --output results/new-study.json');
const output = resolve(args[1]);
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const sources = ['web/public/data.json', 'web/public/manifest.json', 'web/public/plan-resilience.mjs', 'web/study_plan_resilience.mjs'];
const bytes = Object.fromEntries(sources.map(path => [path, readFileSync(resolve(root, path))]));
const hashes = Object.fromEntries(sources.map(path => [path, sha(bytes[path])]));
const data = JSON.parse(bytes[sources[0]]), manifest = JSON.parse(bytes[sources[1]]);
if (hashes[sources[0]] !== manifest.data_sha256) throw Error('Retained data differs from its manifest.');
if (data.days.length !== 92 || manifest.days !== 92 || manifest.schedules !== 460 || JSON.stringify(data.tanks) !== JSON.stringify([500, 1000, 2000, 4000, 8000]) || data.demand !== 120) throw Error('Unsupported retained study inputs.');
const EPS = 1e-7, begun = new Date().toISOString(), clock = performance.now();
const scenarios = [
  {id: 'nominal', label: 'Nominal', scenario: {}},
  {id: 'demand_10', label: 'Demand +10%', scenario: {demand_multiplier: 1.1}},
  {id: 'demand_20', label: 'Demand +20%', scenario: {demand_multiplier: 1.2}},
  {id: 'production_loss_10', label: 'Production −10%', scenario: {production_multiplier: .9}},
  {id: 'midday_outage', label: 'Production outage 12:00–14:00', scenario: {outage: {start_hour: 12, duration_hours: 2}}},
  {id: 'combined_10', label: 'Demand +10%, production −10%', scenario: {demand_multiplier: 1.1, production_multiplier: .9}}
];
const policies = ['retained_reference', 'flat_120_m3_h'];
const columns = ['date_index', 'tank_m3', 'scenario_index', 'policy_index', 'initial_storage_m3', 'final_storage_m3', 'min_storage_m3', 'reserve_margin_m3', 'max_reserve_deficit_m3', 'unmet_m3', 'spill_m3', 'terminal_deficit_m3', 'first_reserve_breach_hour', 'first_stockout_hour', 'first_overflow_hour', 'mass_balance_error_m3', 'maximum_demand_multiplier', 'minimum_initial_storage_m3'];
const cases = [], summary = [], findEvent = (result, type) => result.events.find(event => event.type === type)?.hour ?? null;
let handWorked;
function aggregate(results) {
  const mean = key => results.reduce((sum, result) => sum + result.totals[key], 0) / results.length;
  return {days: results.length, reserve_breach_days: results.filter(result => result.totals.max_reserve_deficit_m3 > EPS).length,
    unmet_demand_days: results.filter(result => result.totals.unmet_m3 > EPS).length,
    terminal_shortfall_days: results.filter(result => result.totals.terminal_deficit_m3 > EPS).length,
    spill_days: results.filter(result => result.totals.spill_m3 > EPS).length,
    minimum_reserve_margin_m3: Math.min(...results.map(result => result.totals.reserve_margin_m3)),
    maximum_reserve_deficit_m3: Math.max(...results.map(result => result.totals.max_reserve_deficit_m3)),
    mean_unmet_m3_per_day: mean('unmet_m3'), mean_spill_m3_per_day: mean('spill_m3'), mean_terminal_shortfall_m3_per_day: mean('terminal_deficit_m3'),
    maximum_absolute_mass_balance_error_m3: Math.max(...results.map(result => Math.abs(result.totals.mass_balance_error_m3)))};
}
for (const tank of data.tanks) for (const [scenarioIndex, {id, label, scenario}] of scenarios.entries()) {
  const paired = [[], []];
  for (const [dateIndex, day] of data.days.entries()) {
    const reference = day.schedules[String(tank)];
    for (let policyIndex = 0; policyIndex < policies.length; policyIndex++) {
      const result = replayPlan({times: day.times, production: policyIndex === 0 ? reference.production : Array(24).fill(120), demand: data.demand,
        capacity: tank, reserve: tank * .2, initial: tank * .5, target: tank * .5, scenario});
      if (Math.abs(result.totals.mass_balance_error_m3) > EPS) throw Error(`Mass balance failed: ${day.date}, ${tank}, ${id}, ${policies[policyIndex]}`);
      if (id === 'nominal' && policyIndex === 0 && result.rows.some((row, hour) => Math.abs(row.storage_end_m3 - reference.storage[hour]) > EPS)) throw Error('Nominal replay differs from retained trajectory.');
      paired[policyIndex].push(result);
      const t = result.totals;
      cases.push([dateIndex, tank, scenarioIndex, policyIndex, t.initial_storage_m3, t.final_storage_m3, t.min_storage_m3, t.reserve_margin_m3, t.max_reserve_deficit_m3,
        t.unmet_m3, t.spill_m3, t.terminal_deficit_m3, findEvent(result, 'reserve_breach'), findEvent(result, 'stockout'), findEvent(result, 'overflow'), t.mass_balance_error_m3,
        result.margins.maximum_demand_multiplier, result.margins.minimum_initial_storage_m3]);
      if (day.date === '2026-07-15' && tank === 4000 && id === 'demand_10' && policyIndex === 0) {
        const at10 = 2000 - 10 * 132, at11 = at10 + 120 - 132, end = 2000 + 2880 - 24 * 132;
        if (Math.abs(result.rows[9].storage_end_m3 - at10) > EPS || Math.abs(result.rows[10].storage_end_m3 - at11) > EPS || Math.abs(t.final_storage_m3 - end) > EPS) throw Error('Independent hand-worked example does not match replay.');
        handWorked = {date: day.date, tank_m3: tank, policy: policies[policyIndex], scenario_id: id,
          arithmetic: {initial_m3: 2000, reserve_m3: 800, hourly_demand_m3: 132,
            storage_at_10_local: {expression: '2000 - 10 * 132', m3: at10},
            storage_at_11_local: {expression: '680 + 120 - 132', m3: at11},
            terminal_storage: {expression: '2000 + 2880 - 24 * 132', m3: end},
            first_reserve_crossing_hour: {expression: '(2000 - 800) / 132', hour: 1200 / 132}},
          nominal_production_m3_by_hour: reference.production, totals: t, events: result.events, margins: result.margins,
          conclusion: 'The fixed plan meets all water demand but breaches the declared reserve and ends below its original inventory target. No corrective rescheduling is attempted.'};
      }
    }
  }
  const compare = predicate => paired[0].filter((reference, i) => predicate(reference.totals, paired[1][i].totals)).length;
  summary.push({tank_m3: tank, scenario_id: id, scenario_label: label, identical_initial_storage_m3: tank * .5, reserve_m3: tank * .2,
    policies: Object.fromEntries(policies.map((policy, i) => [policy, aggregate(paired[i])])),
    paired_days: {both_breach_reserve: compare((a, b) => a.max_reserve_deficit_m3 > EPS && b.max_reserve_deficit_m3 > EPS),
      reference_only_breaches_reserve: compare((a, b) => a.max_reserve_deficit_m3 > EPS && b.max_reserve_deficit_m3 <= EPS),
      flat_only_breaches_reserve: compare((a, b) => a.max_reserve_deficit_m3 <= EPS && b.max_reserve_deficit_m3 > EPS),
      reference_has_more_unmet_water: compare((a, b) => a.unmet_m3 > b.unmet_m3 + EPS),
      flat_has_more_unmet_water: compare((a, b) => b.unmet_m3 > a.unmet_m3 + EPS),
      equal_unmet_water: compare((a, b) => Math.abs(a.unmet_m3 - b.unmet_m3) <= EPS)}});
}
if (!handWorked || cases.length !== 5520) throw Error('Incomplete study.');
for (const path of sources) if (sha(readFileSync(resolve(root, path))) !== hashes[path]) throw Error(`Study input changed while running: ${path}`);
const report = {schema: 1, kind: 'AquaShift fixed-plan resilience experiment', status: 'completed',
  execution: {started_at: begun, completed_at: new Date().toISOString(), elapsed_ms: performance.now() - clock,
    command: [process.execPath, ...process.argv.slice(1)], reproduce_from_repository_root: `node web/study_plan_resilience.mjs --output ${relative(root, output)}`,
    node: process.version, platform: process.platform, architecture: process.arch},
  input_sha256: hashes, inputs_unchanged_at_completion: true,
  design: {days: 92, tanks: data.tanks, scenarios, policies, replays: cases.length, paired_cases: cases.length / 2, breach_numeric_tolerance_m3: EPS,
    dates: data.days.map(day => day.date), demand_m3_h: 120, reserve_fraction: .2, initial_and_terminal_fraction: .5,
    pairing: 'Every reference/flat pair has the same date, tank, initial water, demand, derating and outage. Only the supplied hourly production profile differs.'},
  limitations: ['Declared deterministic disturbances, not measured events, forecast errors or estimated probabilities.',
    'Each tank starts 50% full. Larger tanks therefore also start with more water; differences across tank sizes cannot be attributed to capacity alone.',
    'Each day restarts from its own declared initial water. The study is not a continuous 92-day reservoir trajectory.',
    'Fixed plans receive no corrective rescheduling. Uniform hourly flows, production derating and an outage are the complete replay physics.',
    'Reserve breaches and terminal shortfalls are separate from unmet demand. A reserve crossing does not mean customers receive no water.',
    'No ramps, minimum runs, water quality, pressure, grid permission or electrical feasibility are assessed.',
    'No energy recovery, customer saving, forecast improvement, field validation or scientific novelty is claimed. Stefanos’s primary forecast and scheduler remain unchanged.'],
  summary, hand_worked_case: handWorked,
  case_outputs: {format: 'Columnar rows; index fields resolve through design.dates, design.scenarios and design.policies. Hour 0 is the first supplied timestamp; events may lie inside an hour. Null means no such event or no feasible initial-water bound.', columns, rows: cases}};
const encoded = JSON.stringify(report) + '\n';
if (Buffer.byteLength(encoded) > 1024 * 1024) throw Error('Study output exceeds the 1 MiB retention bound.');
writeFileSync(output, encoded, {flag: 'wx'});
console.log(JSON.stringify({output, bytes: Buffer.byteLength(encoded), replays: cases.length, paired_cases: cases.length / 2, input_data_sha256: hashes[sources[0]], hand_worked_minimum_m3: handWorked.totals.min_storage_m3, elapsed_ms: report.execution.elapsed_ms}));
