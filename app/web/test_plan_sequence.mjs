import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {replaySequence} from './public/plan-sequence.mjs';
import {replayPlan} from './public/plan-resilience.mjs';

const HOUR = 3600000, START = Date.parse('2026-07-01T00:00:00Z');
const at = hour => new Date(START + hour * HOUR).toISOString();
const block = (index, overrides = {}) => ({times: Array.from({length: 24}, (_, hour) => at(index * 24 + hour)), production: Array(24).fill(120), demand: 120, ...overrides});
const input = (overrides = {}) => ({blocks: [block(0), block(1)], capacity: 4000, reserve: 800, initial: 2000, target: 2000, unitCapacity: 500, ...overrides});
const near = (actual, expected, tolerance = 1e-6) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);
function balances(result) {
  const states = [result.totals, ...result.blocks.map(block => block.totals), ...result.rows.map(row => ({...row, initial_storage_m3: row.storage_start_m3, final_storage_m3: row.storage_end_m3}))];
  for (const state of states) {
    near(state.initial_storage_m3 + state.available_production_m3, state.final_storage_m3 + state.delivered_m3 + state.spill_m3);
    near(state.demand_m3, state.delivered_m3 + state.unmet_m3);
  }
  near(result.totals.max_abs_accounting_residual_m3, 0);
  result.blocks.slice(1).forEach((block, index) => assert.equal(block.initial_storage_m3, result.blocks[index].totals.final_storage_m3));
}

test('continuous budget integrates all 92 days with one initial stock and one final target',()=>{
 const result=replaySequence(input({blocks:Array.from({length:92},(_,i)=>block(i)),scenario:{demand_multiplier:1.1}})),b=result.water_budget;
 assert.equal(b.status,'additional_production_necessary');
 for(const [key,value]of Object.entries({horizon_duration_hours:2208,starting_storage_m3:2000,terminal_target_m3:2000,effective_production_m3:264960,demand_m3:291456,unavoidable_unserved_m3:24496,production_required_for_demand_and_target_m3:291456,additional_production_required_m3:26496}))assert.deepEqual(b[key],{value,exact:{numerator:String(value),denominator:'1'}},key);
 assert.equal(result.totals.unmet_m3,b.unavoidable_unserved_m3.value);assert.equal(result.blocks.some(b=>Object.hasOwn(b,'water_budget')),false);
});

test('continuous budget counts effective production through a fractional midnight interruption',()=>{
 const args=input({blocks:[block(0,{production:Array(24).fill(100)}),block(1,{production:Array(24).fill(100)})],scenario:{production_multiplier:.5},outages:[{start:at(23.5),end:at(24.5)}]}),before=JSON.stringify(args),b=replaySequence(args).water_budget;
 for(const [key,value]of Object.entries({effective_production_m3:2350,demand_m3:5760,unavoidable_unserved_m3:1410,additional_production_required_m3:3410}))assert.deepEqual(b[key].exact,{numerator:String(value),denominator:'1'},key);
 assert.equal(JSON.stringify(args),before);
});

test('one block matches daily replay and output never exposes daily margins as sequence guarantees', () => {
  const args = input({blocks: [block(0)], scenario: {demand_multiplier: 1.1}}), result = replaySequence(args);
  const daily = replayPlan({...args.blocks[0], capacity: args.capacity, reserve: args.reserve, initial: args.initial, target: args.target, scenario: args.scenario});
  const {max_abs_accounting_residual_m3, ...totals} = result.totals;
  assert.deepEqual(totals, daily.totals);
  assert.deepEqual(result.rows.map(({block_index, sequence_hour, ...row}) => row), daily.rows);
  assert.deepEqual(result.blocks[0].inputs, args.blocks[0]);
  assert.equal(Object.hasOwn(result, 'margins'), false); assert.equal(Object.hasOwn(result.blocks[0], 'margins'), false);
  balances(result);
});

test('all retained nominal plans carry their actual end inventory and reproduce every hourly source value', () => {
  const data = JSON.parse(readFileSync(new URL('./public/data.json', import.meta.url), 'utf8'));
  for (const capacity of data.tanks) {
    const args = input({capacity, reserve: capacity * .2, initial: capacity * .5, target: capacity * .5,
      blocks: data.days.map(day => ({times: day.times, production: day.schedules[String(capacity)].production, demand: data.demand}))});
    const before = JSON.stringify(args), result = replaySequence(args);
    result.rows.forEach((row, index) => near(row.storage_end_m3, data.days[Math.floor(index / 24)].schedules[String(capacity)].storage[index % 24]));
    assert.equal(result.rows.length, 92 * 24); assert.equal(result.blocks.length, 92);
    near(result.totals.unmet_m3, 0); near(result.totals.terminal_deficit_m3, 0);
    assert.equal(JSON.stringify(args), before); balances(result);
  }
});

test('persistent +10% demand depletes flat inventory across midnight without hidden replenishment', () => {
  const result = replaySequence(input({blocks: Array.from({length: 8}, (_, index) => block(index)), scenario: {demand_multiplier: 1.1}}));
  result.rows.forEach((row, index) => near(row.storage_end_m3, Math.max(0, 2000 - 12 * (index + 1))));
  near(result.totals.unmet_m3, 304); near(result.totals.initial_storage_m3, 2000);
  near(result.totals.terminal_deficit_m3, 2000);
  near(result.events.find(event => event.type === 'reserve_breach').sequence_hour, 100);
  const event = result.events.find(event => event.type === 'stockout');
  assert.equal(event.block_index, 6); near(event.sequence_hour, 2000 / 12); assert.equal(event.time, '2026-07-07T22:40:00.000Z');
  balances(result);
});

test('stockout before midnight and refill next day preserve cumulative service loss', () => {
  const result = replaySequence(input({capacity: 100, reserve: 20, initial: 10, target: 10, blocks: [block(0, {production: Array(24).fill(0), demand: 10}), block(1, {production: Array(24).fill(20), demand: 10})]}));
  near(result.blocks[0].totals.unmet_m3, 230); near(result.blocks[1].initial_storage_m3, 0);
  near(result.totals.final_storage_m3, 100); near(result.totals.unmet_m3, 230); near(result.totals.spill_m3, 140);
  assert.equal(result.events.filter(event => event.type === 'stockout').length, 1);
  near(result.events.find(event => event.type === 'stockout').sequence_hour, 1); balances(result);
});

test('spill before midnight cannot fund later demand after the tank has emptied', () => {
  const production = Array(24).fill(0); production[23] = 200;
  const result = replaySequence(input({capacity: 100, reserve: 0, initial: 0, target: 0,
    blocks: [block(0, {production, demand: 0}), block(1, {production: Array(24).fill(0), demand: 10})]}));
  near(result.blocks[0].totals.spill_m3, 100); near(result.blocks[1].initial_storage_m3, 100);
  near(result.totals.unmet_m3, 140); near(result.events.find(event => event.type === 'stockout').sequence_hour, 34); balances(result);
});

test('zero and full initial inventory, zero rates, and changed final targets do not alter physics', () => {
  for (const initial of [0, 4000]) {
    const args = input({initial, blocks: [block(0, {production: Array(24).fill(0), demand: 0}), block(1, {production: Array(24).fill(0), demand: 0})]});
    const lower = replaySequence({...args, target: 0}), higher = replaySequence({...args, target: 4000});
    assert.deepEqual(lower.rows, higher.rows); assert.deepEqual(lower.events, higher.events);
    near(higher.totals.final_storage_m3, initial); near(higher.totals.terminal_deficit_m3, 4000 - initial);
    near(lower.totals.unmet_m3, 0); balances(lower); balances(higher);
  }
});

test('exact reserve, zero and capacity contacts are not positive-duration violations', () => {
  for (const [initial, production, demand, forbidden] of [[240, 0, 10, 'stockout'], [340, 0, 10, 'reserve_breach'], [160, 10, 0, 'overflow']]) {
    const args = input({capacity: 400, reserve: 100, initial, target: 100, blocks: [block(0, {production: Array(24).fill(production), demand})]});
    const contact = replaySequence(args);
    assert.equal(contact.events.some(event => event.type === forbidden), false);
    const continued = replaySequence({...args, blocks: [...args.blocks, block(1, {production: Array(24).fill(production), demand})]});
    const event = continued.events.find(event => event.type === forbidden);
    near(event.sequence_hour, 24); assert.equal(event.block_index, 1); balances(contact); balances(continued);
  }
});

test('absolute fractional outage crossing midnight removes exactly two half hours', () => {
  const args = input({outages: [{start: at(23.5), end: at(24.5)}]}), result = replaySequence(args);
  near(result.rows[23].available_production_m3, 60); near(result.rows[24].available_production_m3, 60);
  near(result.rows[22].available_production_m3, 120); near(result.rows[25].available_production_m3, 120);
  near(result.totals.final_storage_m3, 1880);
  assert.deepEqual(result.blocks.map(block => block.scenario.outage), [{start_hour: 23.5, duration_hours: .5}, {start_hour: 0, duration_hours: .5}]);
  assert.equal(result.blocks[1].scenario.initial_storage_m3, result.blocks[0].totals.final_storage_m3); balances(result);
});

test('whole-block and adjacent outages respect half-open boundaries without reordering caller input', () => {
  const outages = [{start: at(36), end: at(48)}, {start: at(24), end: at(36)}], before = JSON.stringify(outages);
  const result = replaySequence(input({outages}));
  near(result.blocks[0].totals.available_production_m3, 2880); near(result.blocks[1].totals.available_production_m3, 0);
  assert.equal(JSON.stringify(outages), before); assert.deepEqual(result.outages, outages); balances(result);
});

test('minute-aligned outage endings at midnight avoid floating point false overrun', () => {
  for (let minute = 1; minute < 60; minute++) {
    const result = replaySequence(input({outages: [{start: at(23 + minute / 60), end: at(24)}]}));
    near(result.blocks[0].totals.available_production_m3, 2880 - 120 * (1 - minute / 60));
    near(result.blocks[1].totals.available_production_m3, 2880); balances(result);
  }
});

test('explicit offset changes can repeat local labels while identifying consecutive instants', () => {
  const times = Array.from({length: 24}, (_, hour) => {
    if (hour === 0) return '2026-10-25T03:00:00+03:00';
    return `2026-10-${hour < 22 ? '25' : '26'}T${String((hour + 2) % 24).padStart(2, '0')}:00:00+02:00`;
  });
  const result = replaySequence(input({blocks: [block(0, {times})]}));
  assert.equal(result.rows[0].time, '2026-10-25T00:00:00.000Z'); assert.equal(result.rows[1].time, '2026-10-25T01:00:00.000Z');
  assert.equal(times[0].slice(11, 19), times[1].slice(11, 19)); balances(result);
});

test('missing, duplicate, reordered, offset-free and malformed times reject the whole sequence', () => {
  const cases = [args => args.blocks.splice(0, 1, block(1)), args => args.blocks[1].times[0] = at(23), args => args.blocks.reverse(), args => args.blocks[0].times.splice(12, 1),
    args => args.blocks[0].times[1] = args.blocks[0].times[0], args => args.blocks[0].times[0] = '2026-07-01T00:00:00', args => args.blocks[0].times[0] = '2026-02-30T00:00:00Z',
    args => args.blocks[0].times[0] = '2026-07-01T00:00:00+14:01', args => args.blocks[0].times[0] = '2026-07-01T00:01:00Z', args => delete args.blocks[1], args => args.blocks[0].times.push(at(24))];
  for (const mutate of cases) {const args = input(); mutate(args); assert.throws(() => replaySequence(args), /Continuous review:/);}
});

test('unknown fields and per-block reset or override attempts are rejected, even at zero', () => {
  const cases = [args => args.startHour = 0, args => args.restart = {hour: 0, storage_m3: 0}, args => args.blocks[1].initial = 2000,
    args => args.blocks[0].startHour = 0, args => args.blocks[0].scenario = {}, args => args.scenario = {initial_storage_m3: 2000}, args => args.scenario = {restart: {hour: 0, storage_m3: 0}},
    args => args.scenario = {outage: {start_hour: 0, duration_hours: 1}}, args => args.scenario = null, args => args.scenario = new Date(), args => args.scenario = {[Symbol('unknown')]: 1}];
  for (const mutate of cases) {const args = input(); mutate(args); assert.throws(() => replaySequence(args), /Continuous review:/);}
});

test('over-capacity source production is rejected before derating, and missing/invalid numbers never become zero', () => {
  const cases = [args => {args.blocks[0].production[0] = 501; args.scenario = {production_multiplier: 0};}, args => delete args.blocks[0].production[0],
    args => args.blocks[0].production[0] = -1, args => args.blocks[0].demand = null, args => args.blocks[0].demand = '120', args => args.blocks[0].demand = Array(23).fill(120),
    args => args.blocks[0].demand = Array(24).fill(Infinity), args => args.capacity = 0, args => args.initial = 4001, args => args.target = NaN, args => args.reserve = -1,
    args => args.scenario = {production_multiplier: 1.1}, args => args.scenario = {demand_multiplier: -1}, args => args.unitCapacity = undefined];
  for (const mutate of cases) {const args = input(); mutate(args); assert.throws(() => replaySequence(args), /Continuous review:/);}
});

test('out-of-period, empty, overlapping, disjoint and malformed outages are never silently merged or ignored', () => {
  const cases = [[{start: at(-.5), end: at(.5)}], [{start: at(47), end: at(49)}], [{start: at(12), end: at(12)}], [{start: at(13), end: at(12)}],
    [{start: at(12), end: at(14)}, {start: at(13), end: at(15)}], [{start: at(12), end: at(13)}, {start: at(14), end: at(15)}],
    [{start: at(12), end: at(13), restart: true}], [{start: '2026-07-01T12:00:00', end: at(13)}], [null], null];
  for (const outages of cases) assert.throws(() => replaySequence(input({outages})), /Continuous review:/);
});

test('366-block bound, numeric overflow and immutable caller arrays remain enforced', () => {
  assert.throws(() => replaySequence(input({blocks: []})), /1–366/);
  const full = replaySequence(input({blocks: Array.from({length: 366}, (_, i) => block(i))}));
  assert.equal(full.rows.length, 366 * 24); near(full.totals.final_storage_m3, 2000); balances(full);
  assert.throws(() => replaySequence(input({blocks: Array.from({length: 367}, (_, i) => block(i))})), /1–366/);
  const large = input({initial: 0, target: 0, reserve: 0, unitCapacity: 1e306, blocks: Array.from({length: 8}, (_, i) => block(i, {production: Array(24).fill(1e306), demand: 1e306}))});
  assert.throws(() => replaySequence(large), /finite numeric range/);
  const args = input({blocks: [block(0, {demand: Array(24).fill(120)}), block(1)], outages: [{start: at(12), end: at(14)}], scenario: {production_multiplier: .9}});
  const freeze = value => {if (value && typeof value === 'object') {Object.values(value).forEach(freeze); Object.freeze(value);} return value;};
  const before = JSON.stringify(args); freeze(args); const result = replaySequence(args);
  result.blocks[0].inputs.production[0] = 0; result.blocks[0].inputs.demand[0] = 0; result.blocks[0].inputs.times[0] = 'changed'; result.outages[0].start = 'changed';
  assert.equal(JSON.stringify(args), before);
});

test('finite but numerically unresolved accounting rejects instead of certifying unchanged inventory', () => {
  const args = input({capacity: 1e20, initial: 1e20, target: 1e20, reserve: 0, blocks: [block(0, {production: Array(24).fill(0), demand: 1})]});
  assert.throws(() => replaySequence(args), /accounting residual exceeds/);
});

test('sub-threshold deficits remain numeric even when event precision suppresses the label', () => {
  const result = replaySequence(input({capacity: 1, reserve: 0, initial: 0, target: 0, blocks: [block(0, {production: Array(24).fill(0), demand: 1e-10})]}));
  assert.equal(result.events.some(event => event.type === 'stockout'), false);
  assert.ok(result.totals.unmet_m3 > 0); near(result.totals.unmet_m3, 24e-10, 1e-20);
  assert.match(result.assumptions.join(' '), /threshold/); balances(result);
});
