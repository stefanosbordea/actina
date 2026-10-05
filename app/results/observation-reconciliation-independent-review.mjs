// Independent point/cutoff oracle. No browser, integration, scheduler or field data.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {reconcileObservations} from '../web/public/observation-reconciliation.mjs';
import {pilotExample, pilotExampleCSV} from '../web/public/pilot.mjs';

const root = new URL('../', import.meta.url), started = new Date().toISOString();
const hash = file => createHash('sha256').update(readFileSync(new URL(file, root))).digest('hex');
const HOUR = 3600000, start = Date.parse('2026-07-01T00:00:00+03:00');
const iso = offset => new Date(start + offset * HOUR).toISOString();
const checks = [], issues = [];
function check(name, fn) {
  try { fn(); checks.push(name); }
  catch (error) { issues.push({name, message: error.message}); }
}
function fixture() {
  const plan = {times: Array.from({length: 24}, (_, h) => iso(h)), production: Array(24).fill(100), demand: 100,
    capacity: 4000, reserve: 800, initial: 2000, target: 2000, unit_capacity_m3_h: 500,
    storage_start: Array(24).fill(2000), storage: Array(24).fill(2000)};
  const record = {schema: 1, kind: 'AquaShift observation intake review', status: 'PARTIAL', issues: [], reviewAsOf: iso(14),
    identity: {contract: {sha256: 'a'.repeat(64)}, observations: {sha256: 'b'.repeat(64)}},
    sourceDeclaration: structuredClone(pilotExample),
    observations: pilotExampleCSV.slice(1).map(values => Object.fromEntries(pilotExampleCSV[0].map((key, i) => [key, values[i]])))};
  return {record, plan, mapping: {tank: 'tank-demo', production: 'unit-demo', unit_power: 'unit-demo', available_power: 'grid-demo'},
    tolerances: {tank_storage_m3: 10, production_rate_m3_h: 5, unit_load_kw: 10, power_difference_kw: 5},
    review_as_of: iso(14), specific_energy_kwh_m3: 3.4};
}
const lookup = (r, kind, hour = 10) => r.rows.find(row => row.kind === kind && row.time === iso(hour));
const invalid = [
  ['unrecognised input', a => {a.dispatch = true;}],
  ['unrecognised record', a => {a.record.verified = true;}],
  ['unrecognised point semantics', a => {a.record.observations[0].interval_end = iso(11);}],
  ['unsupported interval measurement', a => {a.record.sourceDeclaration.assets[0].measurements[0].measurement = 'water_volume_m3';}],
  ['wrong units', a => {a.record.observations[0].unit = 'litres';}],
  ['unknown measurement asset', a => {a.record.observations[0].asset_id = 'different-tank';}],
  ['mapping to a different measurement', a => {a.mapping.tank = 'unit-demo';}],
  ['unknown mapping role', a => {a.mapping.energy = 'unit-demo';}],
  ['missing source identity', a => {delete a.record.identity.observations;}],
  ['bad hash representation', a => {a.record.identity.observations.sha256 = 'file-name';}],
  ['blocked intake', a => {a.record.status = 'BLOCKED';}],
  ['retained intake issues', a => {a.record.issues = [{message: 'invalid'}];}],
  ['available before observation', a => {a.record.observations[0].available_at = iso(9);}],
  ['duplicate equivalent offset', a => {a.record.observations.push({...a.record.observations[0], time: iso(10)});}],
  ['point outside exclusive end', a => {a.record.observations[0].time = iso(14); a.record.observations[0].available_at = iso(14);}],
  ['off cadence', a => {a.record.observations[0].time = iso(10.5); a.record.observations[0].available_at = iso(11);}],
  ['missing observation column', a => {delete a.record.observations[0].available_at;}],
  ['negative tolerance', a => {a.tolerances.unit_load_kw = -1;}],
  ['unsupported tolerance', a => {a.tolerances.energy_kwh = 0;}],
  ['zero specific energy', a => {a.specific_energy_kwh_m3 = 0;}],
  ['nonfinite specific energy', a => {a.specific_energy_kwh_m3 = Infinity;}],
  ['invalid plan balance', a => {a.plan.storage[10] += 0.1;}],
  ['invalid initial balance', a => {a.plan.storage_start[0] = 1999;}],
  ['terminal mismatch', a => {a.plan.target = 2001;}],
  ['unit capacity exceeded', a => {a.plan.unit_capacity_m3_h = 99;}],
  ['unsupported plan constraint', a => {a.plan.ramp_limit = 10;}],
  ['nonconsecutive plan time', a => {a.plan.times[4] = iso(4.5);}],
  ['offsetless cutoff', a => {a.review_as_of = '2026-07-01T10:00:00';}],
  ['invalid calendar cutoff', a => {a.review_as_of = '2026-02-30T10:00:00Z';}]
];
for (const [name, edit] of invalid) check(name, () => {const a = fixture(); edit(a); assert.throws(() => reconcileObservations(a));});

check('earlier cutoff hides every future reading but retains nominal comparisons', () => {
  const a = fixture(); a.review_as_of = iso(9);
  const r = reconcileObservations(a);
  assert.equal(r.coverage.known_observations, 0);
  assert.ok(r.rows.every(row => row.status === 'unknown' && row.observed === null && row.difference === null && row.sources.length === 0));
});
check('availability equality accepted without using original intake summary', () => {
  const a = fixture(); a.record.knownSlots = 0; a.record.streams = []; a.record.reviewAsOf = iso(9); a.review_as_of = iso(10 + 5/60);
  const r = reconcileObservations(a);
  assert.equal(r.coverage.known_observations, 4); assert.equal(lookup(r, 'reported_power_difference').difference, 358);
});
check('one millisecond before availability withholds only late side', () => {
  const a = fixture(); a.review_as_of = new Date(Date.parse('2026-07-01T10:05:00+03:00') - 1).toISOString();
  const p = lookup(reconcileObservations(a), 'reported_power_difference');
  assert.equal(p.observed, 1258); assert.equal(p.expected, null); assert.equal(p.difference, null); assert.equal(p.sources.length, 1);
});
check('no mappings means unknown, not zero', () => {
  const a = fixture(); a.mapping = {};
  assert.ok(reconcileObservations(a).rows.every(row => row.status === 'unknown' && row.observed === null));
});
check('outside plan still allows only same-instant reported power comparison', () => {
  const a = fixture(); a.plan.times = a.plan.times.map(t => new Date(Date.parse(t) + 86400000).toISOString());
  const r = reconcileObservations(a);
  assert.equal(lookup(r, 'tank_storage').expected, null); assert.equal(lookup(r, 'production_rate').expected, null);
  assert.equal(lookup(r, 'reported_power_difference').difference, 358);
});
check('return object does not alias source inputs', () => {
  const a = fixture(), before = JSON.stringify(a), r = reconcileObservations(a);
  r.plan.production[0] = 999; r.source.declaration.assets[0].label = 'mutated'; r.source.identity.contract.sha256 = 'changed';
  r.rows[0].sources[0].value = 99; r.mapping.tank = 'other';
  assert.equal(JSON.stringify(a), before);
});

const seed = 92817; let state = seed;
const random = () => {state = (Math.imul(state, 1664525) + 1013904223) >>> 0; return state / 4294967296;};
let scalarComparisons = 0;
const trials = 300;
for (let trial = 0; trial < trials; trial++) check(`point oracle ${trial}`, () => {
  const a = fixture(), hour = Math.floor(random() * 26) - 1, fraction = Math.floor(random() * 4) / 4, at = hour + fraction;
  const end = at + 0.25, cutoff = at + (random() < 0.5 ? 0 : 0.1), rows = [];
  a.record.sourceDeclaration.window = {start: iso(at), end: iso(end)}; a.record.sourceDeclaration.cadence_minutes = 15;
  a.review_as_of = iso(cutoff); a.record.observations = rows;
  const measurements = [
    ['tank-demo', 'tank_storage_m3', 'm3', random()*4000],
    ['unit-demo', 'production_rate_m3_h', 'm3/h', random()*500],
    ['unit-demo', 'unit_load_kw', 'kW', random()*1700],
    ['grid-demo', 'available_power_kw', 'kW', random()*1700]
  ];
  for (const [asset_id, measurement, unit, value] of measurements) {
    if (random() < 0.12) continue;
    rows.push({time: iso(at), available_at: iso(at + (random() < 0.5 ? 0 : 0.05)), asset_id, measurement, unit, value});
  }
  if (random() < 0.25) delete a.specific_energy_kwh_m3;
  const r = reconcileObservations(a), visible = measurement => rows.find(row => row.measurement === measurement && Date.parse(row.available_at) <= Date.parse(a.review_as_of));
  const inPlan = at >= 0 && at < 24, boundary = at >= 0 && at <= 24 && Number.isInteger(at);
  const cases = [
    ['tank_storage', 'tank_storage_m3', boundary ? 2000 : null, 10, false],
    ['production_rate', 'production_rate_m3_h', inPlan ? 100 : null, 5, false],
    ['modeled_power', 'unit_load_kw', inPlan && a.specific_energy_kwh_m3 ? 340 : null, 10, false],
    ['reported_power_difference', 'unit_load_kw', visible('available_power_kw')?.value ?? null, 5, true]
  ];
  for (const [kind, measurement, expected, tolerance, oneSided] of cases) {
    const row = r.rows.find(row => row.kind === kind), observed = visible(measurement)?.value ?? null;
    const difference = observed === null || expected === null ? null : observed - expected;
    assert.equal(row.observed, observed); assert.equal(row.expected, expected); assert.equal(row.difference, difference);
    assert.equal(row.status, difference === null ? 'unknown' : (oneSided ? difference : Math.abs(difference)) > tolerance ? 'requires_explanation' : 'within_tolerance');
    assert.ok(row.sources.every(source => Date.parse(source.available_at) <= Date.parse(a.review_as_of)));
    scalarComparisons += 5;
  }
});

const files = ['web/public/observation-reconciliation.mjs', 'web/public/pilot.mjs', 'web/public/plan-resilience.mjs', 'web/test_observation_reconciliation.mjs', 'results/observation-reconciliation-independent-review.mjs'];
console.log(JSON.stringify({schema: 1, started_at: started, completed_at: new Date().toISOString(), node: process.version,
  command: 'node results/observation-reconciliation-independent-review.mjs > results/observation-reconciliation-independent-review.json',
  scope: 'Independent deterministic contract probes plus seeded point-oracle comparisons; invented inputs only, no browser, meter integration or field validation.',
  seed, trials, rejected_contract_cases: invalid.length, deterministic_cases: 6, passed_checks: checks.length,
  scalar_comparisons: scalarComparisons, issue_count: issues.length, issues, hashes: Object.fromEntries(files.map(file => [file, hash(file)])),
  identity_limitation: 'Constructed fixture hashes are explicitly caller metadata, not byte-authentication evidence.'}, null, 2));
if (issues.length) process.exitCode = 1;
