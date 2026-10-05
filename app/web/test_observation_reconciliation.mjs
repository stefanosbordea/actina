import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {reconcileObservations} from './public/observation-reconciliation.mjs';
import {validatePilot, pilotRecord} from './public/pilot.mjs';

const sha = value => createHash('sha256').update(value).digest('hex');
const parserContext = {module: {exports: {}}, exports: {}};
vm.runInNewContext(readFileSync(new URL('./public/vendor/papaparse.min.js', import.meta.url), 'utf8'), parserContext);
const Papa = parserContext.module.exports;
const times = Array.from({length: 24}, (_, hour) => `2026-07-01T${String(hour).padStart(2, '0')}:00:00+03:00`);
const plan = {times, production: Array(24).fill(120), demand: 120, capacity: 4000, reserve: 800, initial: 2000, target: 2000,
  storage_start: Array(24).fill(2000), storage: Array(24).fill(2000), unit_capacity_m3_h: 500, identity: {kind: 'Invented test plan'}};
const mapping = {tank: 'tank-demo', production: 'unit-demo', unit_power: 'unit-demo', available_power: 'grid-demo'};
const tolerances = {tank_storage_m3: 10, production_rate_m3_h: 5, unit_load_kw: 10, power_difference_kw: 5};
function fixture() {
  const declarationBytes = readFileSync(new URL('./fixtures/pilot-synthetic-declaration.json', import.meta.url));
  const observationBytes = readFileSync(new URL('./fixtures/pilot-synthetic-observations.csv', import.meta.url));
  const declaration = JSON.parse(declarationBytes), report = validatePilot(declaration, observationBytes.toString('utf8'), Papa);
  const record = pilotRecord(declaration, report, {contract: {sha256: sha(declarationBytes)}, observations: {sha256: sha(observationBytes)}});
  return {record, plan: structuredClone(plan), mapping: {...mapping}, tolerances: {...tolerances}, review_as_of: '2026-07-01T14:00:00+03:00', specific_energy_kwh_m3: 3.4};
}
const rowAt = (result, kind, time = '2026-07-01T07:00:00.000Z') => result.rows.find(row => row.kind === kind && row.time === time);

test('real pilotRecord fixture retains provenance and identifies the 358 kW unexplained difference', () => {
  const args = fixture(), result = reconcileObservations(args), gap = rowAt(result, 'reported_power_difference');
  assert.equal(gap.difference, 358); assert.equal(gap.status, 'requires_explanation');
  assert.equal(rowAt(result, 'modeled_power').expected, 408);
  assert.equal(rowAt(result, 'tank_storage').difference, -200);
  assert.equal(result.source.kind, 'synthetic_fixture');
  assert.deepEqual(result.source.identity, args.record.identity);
  assert.equal(gap.sources[1].available_at, '2026-07-01T10:05:00+03:00');
  assert.ok(result.limitations.some(text => text.includes('not a grid violation')));
  assert.equal(Object.hasOwn(result, 'energy_kwh'), false);
  assert.equal(Object.hasOwn(result, 'water_m3'), false);
});

test('review cutoff independently excludes late values and accepts first availability exactly', () => {
  const args = fixture(); args.review_as_of = '2026-07-01T10:02:00+03:00';
  const earlier = reconcileObservations(args), gap = rowAt(earlier, 'reported_power_difference');
  assert.equal(gap.status, 'unknown'); assert.equal(gap.difference, null); assert.equal(gap.expected, null);
  assert.match(gap.reason, /not_available_at_review_time/);
  assert.equal(gap.sources.length, 1);
  assert.equal(earlier.coverage.known_observations, 3);
  args.review_as_of = '2026-07-01T10:05:00+03:00';
  const atCutoff = reconcileObservations(args);
  assert.equal(rowAt(atCutoff, 'reported_power_difference').difference, 358);
  assert.equal(atCutoff.coverage.known_observations, 4);
  assert.equal(atCutoff.original_intake_review_as_of, args.record.reviewAsOf);
});

test('15-minute points never pair nearest samples or interpolate tank inventory', () => {
  const args = fixture();
  args.record.sourceDeclaration.cadence_minutes = 15;
  args.record.sourceDeclaration.window.end = '2026-07-01T11:00:00+03:00';
  args.record.observations = args.record.observations.filter(row => row.time.startsWith('2026-07-01T10:'));
  for (const row of args.record.observations) if (['available_power_kw', 'tank_storage_m3', 'production_rate_m3_h'].includes(row.measurement)) {
    row.time = '2026-07-01T10:15:00+03:00'; row.available_at = '2026-07-01T10:16:00+03:00';
  }
  const production = args.record.observations.find(row => row.measurement === 'production_rate_m3_h'); production.value = 125;
  const result = reconcileObservations(args), later = '2026-07-01T07:15:00.000Z';
  assert.equal(rowAt(result, 'reported_power_difference').difference, null);
  assert.equal(rowAt(result, 'reported_power_difference', later).difference, null);
  const tank = rowAt(result, 'tank_storage', later);
  assert.equal(tank.observed, 1800); assert.equal(tank.expected, null); assert.equal(tank.reason, 'not_an_exact_plan_boundary');
  const rate = rowAt(result, 'production_rate', later);
  assert.equal(rate.expected, 120); assert.equal(rate.difference, 5); assert.equal(rate.status, 'within_tolerance');
});

test('missing mappings, samples and specific energy stay unknown; negative power difference grants no authority', () => {
  const args = fixture(); delete args.mapping.tank; delete args.specific_energy_kwh_m3;
  const result = reconcileObservations(args);
  assert.equal(rowAt(result, 'tank_storage').reason, 'stream_not_mapped');
  assert.equal(rowAt(result, 'modeled_power').reason, 'specific_energy_not_declared');
  assert.equal(rowAt(result, 'modeled_power').expected, null);
  const missingNoonPower = rowAt(result, 'reported_power_difference', '2026-07-01T09:00:00.000Z');
  assert.equal(missingNoonPower.status, 'unknown'); assert.equal(missingNoonPower.difference, null);
  args.record.observations.find(row => row.measurement === 'available_power_kw').value = 1500;
  const below = rowAt(reconcileObservations(args), 'reported_power_difference');
  assert.equal(below.difference, -242); assert.equal(below.status, 'within_tolerance');
});

test('exact final tank boundary is usable, but no final-hour production is invented', () => {
  const args = fixture();
  args.record.sourceDeclaration.window = {start: '2026-07-02T00:00:00+03:00', end: '2026-07-02T01:00:00+03:00'};
  args.record.observations = args.record.observations.filter(row => row.measurement === 'tank_storage_m3').slice(0, 1);
  Object.assign(args.record.observations[0], {time: '2026-07-02T00:00:00+03:00', available_at: '2026-07-02T00:01:00+03:00', value: 2000});
  args.review_as_of = '2026-07-02T01:00:00+03:00';
  const result = reconcileObservations(args);
  assert.equal(result.rows[0].expected, 2000); assert.equal(result.rows[0].plan_hour, 24);
  assert.equal(result.rows[1].expected, null); assert.equal(result.rows[1].status, 'unknown');
});

test('input immutability includes identity and plan arrays in returned records', () => {
  const args = fixture(), before = JSON.stringify(args), result = reconcileObservations(args);
  result.plan.storage[0] = 123; result.source.identity.contract.sha256 = 'changed';
  result.source.declaration.assets[0].label = 'changed'; result.mapping.tank = 'changed';
  assert.equal(JSON.stringify(args), before);
});

test('rejects ambiguous mapping, future telemetry, duplicate instants, unsupported constraints and invalid plan physics', () => {
  const edits = [
    args => { args.mapping.tank = ['tank-demo']; },
    args => { args.mapping.tank = 'unit-demo'; },
    args => { args.mapping.dispatch_permission = true; },
    args => { args.record.observations[0].available_at = '2026-07-01T09:59:00+03:00'; },
    args => { args.record.observations.push({...args.record.observations[0], time: '2026-07-01T07:00:00Z'}); },
    args => { args.record.observations[0].unit = 'litres'; },
    args => { args.record.observations[0].asset_id = ['tank-demo']; },
    args => { args.record.observations[0].value = NaN; },
    args => { args.record.observations[0].approved = true; },
    args => { args.record.status = 'BLOCKED'; },
    args => { args.record.sourceDeclaration.source_kind = 'forecast'; },
    args => { args.record.identity = {}; },
    args => { args.tolerances.unit_load_kw = null; },
    args => { args.tolerances.water_quality = 0; },
    args => { args.specific_energy_kwh_m3 = Infinity; },
    args => { args.plan.storage[0] += 1; },
    args => { args.plan.storage_start[1] -= 1; },
    args => { args.plan.unit_capacity_m3_h = 100; },
    args => { args.plan.target = 2100; },
    args => { args.plan.reserve = 2100; },
    args => { args.plan.ramp_limit = 50; },
    args => { args.review_as_of = '2026-07-01T10:02:00'; }
  ];
  for (const edit of edits) { const args = fixture(); edit(args); assert.throws(() => reconcileObservations(args), /Observation reconciliation:/); }
});
