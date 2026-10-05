import test from 'node:test';
import assert from 'node:assert/strict';
import {PROTOCOL, disturbance, generateTruth, observationsFor, knownObservations, evaluateWarnings, scoreMethod} from './study_warning_methods.mjs';
const times = Array.from({length: 24}, (_, hour) => `2026-07-15T${String(hour).padStart(2, '0')}:00:00+03:00`);
const plan = changes => ({times, production: Array(24).fill(100), demand: 100, capacity: 1000, reserve: 200, initial: 500, target: 500, ...changes});
const reading = (hour, value, available = hour, other = {}) => ({id: `r${hour}`, asset_id: 'synthetic-tank', observed_hour: hour, available_hour: available, storage_m3: value, ...other});
const truth = (p, changes) => generateTruth(p, {...disturbance('nominal', 'development', 1, p.capacity), initial_m3: p.initial, ...changes});

test('protocol fixes time, severity blocks and useful lead before execution', () => {
  assert.equal(PROTOCOL.horizon_hours, 4);
  assert.equal(PROTOCOL.useful_lead_hours, .5);
  assert.equal(PROTOCOL.review_hours, .25);
  const a = disturbance('demand_step', 'development', 5, 1000), b = disturbance('demand_step', 'heldout', 5, 1000);
  assert(a.demand_multiplier < b.demand_multiplier);
  assert.equal(PROTOCOL.alarm_budget, null);
});

test('independent truth conserves physical water with spill and shortage', () => {
  const p = plan({production: Array.from({length: 24}, (_, i) => i < 12 ? 500 : 0), demand: 200, capacity: 300, initial: 150, reserve: 60});
  const result = truth(p);
  assert(result.totals.spill_m3 > 0);
  assert(result.totals.unmet_m3 > 0);
  assert(Math.abs(result.totals.balance_error_m3) < 1e-6);
  assert(result.values.every(value => value >= 0 && value <= 300));
});

test('reserve tangency and refill are not strict violations; crossing times are exact', () => {
  const p = plan({production: Array.from({length: 24}, (_, i) => i < 3 ? 0 : 200)});
  assert.equal(truth(p).events.length, 0);
  const crossing = truth(plan({production: Array.from({length: 24}, (_, i) => i < 4 ? 0 : 200)}));
  assert(Math.abs(crossing.events[0].start_hour - 3) < 1e-9);
  assert(Math.abs(crossing.events[0].end_hour - 5) < 1e-9);
});

test('future observation, future availability, wrong asset and late revision remain unavailable', () => {
  const data = [reading(0, 500), reading(1, 450, 3), reading(2, 400, 1), reading(1, 470, 1, {asset_id: 'other'}), reading(0, 480, 2)];
  assert.deepEqual(knownObservations(data, 1).map(row => row.storage_m3), [500]);
  assert.deepEqual(knownObservations(data, 2).map(row => row.storage_m3), [480]);
  assert.deepEqual(knownObservations(data, 3).map(row => row.storage_m3), [480, 450]);
  assert.deepEqual(knownObservations(data, 3, false), []);
});

test('future outcomes cannot change warnings at an earlier cutoff', () => {
  const p = plan(), past = [reading(0, 500), reading(1, 400)], snapshot = JSON.stringify(p);
  const a = evaluateWarnings(p, [...past, reading(2, 20, 2)], 1.5);
  const b = evaluateWarnings(p, [...past, reading(2, 999, 20)], 1.5);
  assert.deepEqual(a, b);
  assert.equal(JSON.stringify(p), snapshot);
});

test('old readings are advanced only through explicit method assumptions; age expires', () => {
  const p = plan({production: Array(24).fill(0)}), data = [reading(0, 500)];
  const outputs = evaluateWarnings(p, data, 2);
  assert.equal(outputs.current_level.alarm, false);
  assert.equal(outputs.current_level.age_hours, 2);
  assert.equal(outputs.observation_anchored_plan.alarm, true);
  assert.equal(outputs.observation_anchored_plan.predicted_crossing_hour, 3);
  const stale = evaluateWarnings(p, data, 2.25);
  for (const method of PROTOCOL.methods.slice(1)) assert.equal(stale[method].reason, 'stale_reading');
  assert.equal(stale.plan_only.abstain, undefined);
});

test('invalid mapping abstains for observation methods while immutable plan-only control remains', () => {
  const outputs = evaluateWarnings(plan(), [reading(0, 500)], 0, {mappingValid: false});
  for (const method of PROTOCOL.methods.slice(1)) assert.equal(outputs[method].reason, 'invalid_mapping');
  assert.equal(outputs.plan_only.reason, 'no_predicted_crossing');
});

test('trend uses two distinct known readings and cannot bridge a long gap', () => {
  const p = plan(), outputs = evaluateWarnings(p, [reading(0, 500), reading(1, 400)], 1);
  assert.equal(outputs.two_reading_trend.predicted_crossing_hour, 3);
  assert.equal(outputs.two_reading_trend.alarm, true);
  assert.equal(outputs.observation_anchored_plan.alarm, false);
  assert.equal(evaluateWarnings(p, [reading(0, 500), reading(4, 400)], 4).two_reading_trend.reason, 'insufficient_recent_history');
});

test('bias outside tank bounds is preserved as invalid rather than silently clipped', () => {
  const p = plan({initial: 1000});
  let generated;
  for (let seed = 1; seed < 100000; seed++) {
    generated = observationsFor(truth(p), p, 'biased_quantized', seed);
    if (generated.bias_m3 > 0) break;
  }
  assert(generated.observations[0].storage_m3 > p.capacity);
  assert.equal(generated.observations[0].quality, 'invalid_physical_range');
  assert.equal(knownObservations(generated.observations, 0).length, 0);
});

test('event at cutoff is detection, not early warning; each event credited once', () => {
  const outcome = {events: [{start_hour: 2, end_hour: 3, initial: false}]};
  const cutoffs = [0, .25, .5, 2, 2.25], decisions = cutoffs.map(() => ({alarm: true}));
  const scored = scoreMethod(outcome, cutoffs, decisions);
  assert.equal(scored.events, 1);
  assert.equal(scored.events_with_useful_lead, 1);
  assert.deepEqual(scored.leads_hours, [2]);
  assert.equal(scored.active_detections, 2);
  assert.equal(scored.alarm_episodes, 1);
});

test('a later event cannot vindicate an alarm outside its horizon; false episodes remain visible', () => {
  const outcome = {events: [{start_hour: 6, end_hour: 7, initial: false}]};
  const scored = scoreMethod(outcome, [0, .25, .5, .75], [{alarm: true}, {alarm: true}, {alarm: false}, {alarm: true}]);
  assert.equal(scored.false_predictive_cutoffs, 3);
  assert.equal(scored.false_alarm_episodes, 2);
  assert.equal(scored.missed_events, 1);
});

test('one cutoff cannot credit two events and short-lead alarms still count as misses', () => {
  const outcome = {events: [{start_hour: 1, end_hour: 1.1, initial: false}, {start_hour: 2, end_hour: 3, initial: false}]};
  const scored = scoreMethod(outcome, [.75], [{alarm: true}]);
  assert.equal(scored.events_with_any_early_alarm, 1);
  assert.equal(scored.events_with_useful_lead, 0);
  assert.deepEqual(scored.leads_hours, [.25, null]);
  assert.equal(scored.missed_events, 2);
});

test('initial unsafe state is separate and never credited as an upcoming event', () => {
  const outcome = {events: [{start_hour: 0, end_hour: 2, initial: true}]};
  const scored = scoreMethod(outcome, [0, .25], [{alarm: true}, {alarm: true}]);
  assert.equal(scored.initial_unsafe, 1);
  assert.equal(scored.events, 0);
  assert.equal(scored.active_detections, 2);
});
