import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {replayPlan} from './public/plan-resilience.mjs';

const times = Array.from({length: 24}, (_, hour) => `2026-07-15T${String(hour).padStart(2, '0')}:00:00+03:00`);
const input = (overrides = {}) => ({times, production: Array(24).fill(120), demand: 120, capacity: 4000, reserve: 800, initial: 2000, target: 2000, ...overrides});
const near = (actual, expected, tolerance = 1e-7) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
const conservation = result => {
  near(result.totals.mass_balance_error_m3, 0);
  for (const row of result.rows) {
    near(row.storage_start_m3 + row.available_production_m3 - row.delivered_m3 - row.spill_m3, row.storage_end_m3);
    near(row.delivered_m3 + row.unmet_m3, row.demand_m3);
  }
};

test('zero-shock replay reproduces every retained hourly plan without modifying inputs', () => {
  const data = JSON.parse(readFileSync(new URL('./public/data.json', import.meta.url), 'utf8'));
  for (const day of data.days) for (const capacity of data.tanks) {
    const plan = day.schedules[String(capacity)], args = {times: day.times, production: plan.production, demand: data.demand, capacity, reserve: capacity * .2, initial: capacity * .5, target: capacity * .5};
    const before = JSON.stringify(args), result = replayPlan(args);
    result.rows.forEach((row, hour) => near(row.storage_end_m3, plan.storage[hour]));
    near(result.totals.available_production_m3, plan.totals.water_produced_m3);
    near(result.totals.terminal_deviation_m3, 0);
    near(result.totals.unmet_m3, 0); near(result.totals.spill_m3, 0);
    assert.deepEqual(result.events, []); conservation(result);
    assert.equal(JSON.stringify(args), before);
  }
});

test('July 15 demand +10% exposes the hand-worked 10:00 reserve deficit', () => {
  const production = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 120, 260, 500, 500, 500, 500, 500, 0, 0, 0, 0, 0, 0, 0];
  const result = replayPlan(input({production, scenario: {demand_multiplier: 1.1}}));
  near(result.rows[9].storage_end_m3, 680);
  near(result.rows[9].reserve_deficit_m3, 120);
  near(result.rows[10].storage_end_m3, 668);
  near(result.totals.terminal_deficit_m3, 288);
  near(result.totals.unmet_m3, 0);
  near(result.events[0].hour, 1200 / 132);
  assert.equal(result.events[0].type, 'reserve_breach');
  near(result.margins.maximum_demand_multiplier, 1);
  near(result.margins.minimum_initial_storage_m3, 2132);
  conservation(result);
});

test('fractional outage is end-exclusive and crosses reserve at the exact boundary time', () => {
  const result = replayPlan(input({initial: 850, target: 850, scenario: {outage: {start_hour: .5, duration_hours: 1}}}));
  near(result.rows[0].available_production_m3, 60);
  near(result.rows[1].available_production_m3, 60);
  near(result.rows[2].available_production_m3, 120);
  near(result.events[0].hour, .5 + 50 / 120);
  assert.equal(result.events[0].time, '2026-07-14T21:55:00.000Z');
  near(result.totals.final_storage_m3, 730); conservation(result);
  const idle = input({production: [0, ...Array(23).fill(120)]});
  assert.deepEqual(replayPlan({...idle, scenario: {outage: {start_hour: 0, duration_hours: 1}}}).totals, replayPlan(idle).totals);
});

test('overflow and shortage preserve mass rather than accumulating impossible storage', () => {
  const result = replayPlan(input({production: [100, ...Array(23).fill(0)], demand: 20, capacity: 100, reserve: 10, initial: 90, target: 50}));
  near(result.rows[0].storage_end_m3, 100); near(result.rows[0].spill_m3, 70);
  near(result.totals.unmet_m3, 360); near(result.totals.delivered_m3, 120);
  near(result.events.find(event => event.type === 'overflow').hour, .125);
  near(result.events.find(event => event.type === 'reserve_breach').hour, 5.5);
  near(result.events.find(event => event.type === 'stockout').hour, 6);
  assert.equal(result.margins.minimum_initial_status, 'capacity_insufficient');
  assert.equal(result.margins.minimum_initial_storage_m3, null);
  near(result.margins.maximum_demand_multiplier, 90 / 460);
  conservation(result);
});

test('restart reviews only the remaining horizon and includes initial reserve deficit', () => {
  const result = replayPlan(input({startHour: 12, scenario: {initial_storage_m3: 700, demand_multiplier: 1.1}}));
  assert.equal(result.rows.length, 12); assert.equal(result.rows[0].hour, 12);
  near(result.totals.demand_m3, 1584); near(result.totals.available_production_m3, 1440);
  near(result.totals.final_storage_m3, 556); near(result.events[0].hour, 12);
  near(result.totals.reserve_margin_m3, -244);
  assert.equal(result.margins.maximum_demand_status, 'initial_below_reserve');
  assert.equal(result.margins.maximum_demand_multiplier, null);
  const restarted = replayPlan(input({scenario: {restart: {hour: 12, storage_m3: 700}, demand_multiplier: 1.1}}));
  assert.deepEqual(restarted.totals, result.totals);
  assert.deepEqual(replayPlan(input({scenario: restarted.scenario})).totals, restarted.totals);
  conservation(result);
});

test('demand and starting-water bounds distinguish reserve support from terminal target', () => {
  const args = input({production: Array(24).fill(0), initial: 3200, target: 3200, demand: 100});
  const result = replayPlan(args);
  near(result.margins.maximum_demand_multiplier, 1);
  near(result.margins.minimum_initial_storage_m3, 3200);
  near(result.totals.reserve_margin_m3, 0); near(result.totals.terminal_deficit_m3, 2400);
  const above = replayPlan({...args, scenario: {demand_multiplier: 1.0001}});
  assert.ok(above.totals.reserve_margin_m3 < 0);
  assert.equal(replayPlan(input({demand: 0})).margins.maximum_demand_status, 'unbounded');
  const finished = replayPlan(input({startHour: 24}));
  assert.equal(finished.rows.length, 0); near(finished.totals.final_storage_m3, 2000);
  assert.equal(finished.margins.maximum_demand_status, 'unbounded');
});

test('nested scenario input remains unchanged and matching shocks preserve direct plan comparison', () => {
  const scenario = Object.freeze({initial_storage_m3: 2100, demand_multiplier: 1.1, production_multiplier: .9, outage: Object.freeze({start_hour: 12.5, duration_hours: .75})});
  const args = input({scenario, production: Object.freeze(Array(24).fill(120)), times: Object.freeze([...times])});
  const before = JSON.stringify(args), reference = replayPlan(args), duplicate = replayPlan(args);
  assert.deepEqual(reference, duplicate);
  assert.equal(JSON.stringify(args), before);
  conservation(reference);
});

test('bounded demand frontier agrees with direct replays across varied spill and outage patterns', () => {
  for (let seed = 1; seed <= 16; seed++) {
    const args = input({capacity: 1000, reserve: 100, initial: 200 + seed * 25, target: 500,
      production: Array.from({length: 24}, (_, h) => ((h * 79 + seed * 137) % 7) * 60),
      demand: Array.from({length: 24}, (_, h) => 40 + (h * 17 + seed * 13) % 100),
      scenario: {production_multiplier: .8, outage: {start_hour: seed / 2, duration_hours: 1.5}}});
    const result = replayPlan(args), boundary = result.margins.maximum_demand_multiplier;
    assert.ok(Number.isFinite(boundary));
    const at = replayPlan({...args, scenario: {...args.scenario, demand_multiplier: boundary}});
    assert.ok(at.totals.reserve_margin_m3 >= -1e-7); near(at.totals.unmet_m3, 0);
    const above = replayPlan({...args, scenario: {...args.scenario, demand_multiplier: boundary + .0001}});
    assert.ok(above.totals.reserve_margin_m3 < -1e-7 || above.totals.unmet_m3 > 0);
    if (result.margins.minimum_initial_status === 'feasible') {
      const atInitial = replayPlan({...args, scenario: {...args.scenario, initial_storage_m3: result.margins.minimum_initial_storage_m3}});
      assert.ok(atInitial.totals.reserve_margin_m3 >= -1e-7); near(atInitial.totals.unmet_m3, 0);
    }
    conservation(result);
  }
});

test('strict contract rejects unsupported fields, time intervals, bounds and nonfinite inputs', () => {
  const cases = [input({extra: 1}), input({times: times.slice(1)}), input({production: [1]}), input({demand: [1]}),
    input({capacity: 0}), input({reserve: 4001}), input({initial: -1}), input({target: Infinity}), input({demand: NaN}),
    input({production: Array(24).fill(Number.MAX_VALUE)}), input({scenario: {demand_multiplier: Number.MAX_VALUE}}),
    input({scenario: {unknown: 1}}), input({scenario: null}), input({scenario: {production_multiplier: 1.01}}),
    input({scenario: {demand_multiplier: null}}), input({scenario: {production_multiplier: null}}), input({scenario: {initial_storage_m3: null}}), input({startHour: null}),
    input({times: Array(24)}), input({production: Array(24)}), input({demand: Array(24)}),
    input({scenario: {outage: {start_hour: 23, duration_hours: 2}}}), input({scenario: {outage: {start_hour: 2}}}),
    input({startHour: 1.5}), input({scenario: {restart: {hour: 3, storage_m3: 5000}}}),
    input({scenario: {initial_storage_m3: 900, restart: {hour: 3, storage_m3: 900}}}),
    input({startHour: 4, scenario: {restart: {hour: 3, storage_m3: 900}}}),
    input({times: times.map((time, i) => i === 1 ? times[0] : time)}),
    input({times: times.map(time => time.replace('T00:00:00', 'T00:30:00'))}),
    input({times: times.map(time => time.replace('2026-07-15', '2026-02-30'))}),
    input({times: times.map(time => time.replace('+03:00', '+14:01'))})];
  for (const value of cases) assert.throws(() => replayPlan(value), /Plan replay:/);
});
