import {replayPlan, waterServiceModel} from './plan-resilience.mjs';
import {waterProductionBudget, storageRequirements} from './paired-water-service.mjs';
import {pilotTime} from './pilot.mjs';

const HOUR = 3600000;
const flows = ['requested_production_m3', 'available_production_m3', 'demand_m3', 'delivered_m3', 'spill_m3', 'unmet_m3'];
const fail = message => { throw Error(`Continuous review: ${message}`); };
const finite = value => typeof value === 'number' && Number.isFinite(value);
function fields(value, allowed, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value) || ![Object.prototype, null].includes(Object.getPrototypeOf(value))) fail(`${label} must be an object.`);
  for (const key of Reflect.ownKeys(value)) if (!allowed.includes(key)) fail(`Unsupported ${label} field: ${String(key)}.`);
}
function number(value, label, max = Infinity) {
  if (!finite(value) || value < 0 || value > max) fail(`${label} must be finite and between 0 and ${max}.`);
  return value;
}
function time(value, label, wholeHour = false) {
  const parsed = pilotTime(value);
  if (parsed.error) fail(`${label}: ${parsed.error}`);
  if (wholeHour && !/^\d{4}-\d{2}-\d{2}T\d{2}:00:00(?:\.000)?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) fail(`${label} must be a whole local hour.`);
  return parsed.epoch;
}
function sum(values) {
  let total = 0, correction = 0;
  for (const value of values) {
    const next = total + value;
    correction += Math.abs(total) >= Math.abs(value) ? (total - next) + value : (value - next) + total;
    total = next;
  }
  const result = total + correction;
  if (!finite(result)) fail('Accounting exceeds finite numeric range.');
  return result;
}
const balance = value => sum([value.initial_storage_m3, value.available_production_m3, -value.final_storage_m3, -value.delivered_m3, -value.spill_m3]);

/** Replay supplied 24-hour blocks in order, carrying water once across the entire period. */
export function replaySequence(input) {
  fields(input, ['blocks', 'capacity', 'reserve', 'initial', 'target', 'unitCapacity', 'scenario', 'outages'], 'input');
  if (!Array.isArray(input.blocks) || !input.blocks.length || input.blocks.length > 366) fail('Supply 1–366 complete 24-hour blocks.');
  const capacity = number(input.capacity, 'Capacity'), unitCapacity = number(input.unitCapacity, 'Unit capacity');
  if (!capacity) fail('Capacity must be greater than zero.');
  const reserve = number(input.reserve, 'Reserve', capacity), initial = number(input.initial, 'Initial water', capacity), target = number(input.target, 'Final target', capacity);
  const scenario = input.scenario === undefined ? {} : input.scenario;
  fields(scenario, ['demand_multiplier', 'production_multiplier'], 'scenario');
  const demand_multiplier = number(scenario.demand_multiplier === undefined ? 1 : scenario.demand_multiplier, 'Demand multiplier');
  const production_multiplier = number(scenario.production_multiplier === undefined ? 1 : scenario.production_multiplier, 'Production multiplier', 1);
  let nextTime;
  const supplied = Array.from(input.blocks, (block, index) => {
    fields(block, ['times', 'production', 'demand'], `block ${index + 1}`);
    if (!Array.isArray(block.times) || block.times.length !== 24 || !Array.isArray(block.production) || block.production.length !== 24) fail(`Block ${index + 1} requires exactly 24 times and production values.`);
    const epochs = Array.from(block.times, (value, hour) => time(value, `Block ${index + 1}, hour ${hour}`, true));
    for (const epoch of epochs) {
      if (nextTime !== undefined && epoch !== nextTime) fail('All blocks must contain consecutive one-hour instants, in supplied order. Missing, repeated or overlapping hours are unsupported.');
      nextTime = epoch + HOUR;
    }
    const production = Array.from(block.production, value => number(value, 'Supplied production', unitCapacity));
    const demand = Array.isArray(block.demand) ? Array.from(block.demand) : block.demand;
    if (Array.isArray(demand) && demand.length !== 24) fail('Block demand must be one number or 24 hourly values.');
    for (const value of Array.isArray(demand) ? demand : [demand]) number(value, 'Demand');
    return {start: epochs[0], end: epochs[0] + 24 * HOUR, inputs: {times: block.times.slice(), production, demand}};
  });
  const start = supplied[0].start, end = supplied.at(-1).end;
  if (input.outages !== undefined && !Array.isArray(input.outages)) fail('Outages must be an array.');
  const outages = Array.from(input.outages ?? [], (outage, index) => {
    fields(outage, ['start', 'end'], `outage ${index + 1}`);
    const from = time(outage.start, 'Outage start'), to = time(outage.end, 'Outage end');
    if (to <= from || from < start || to > end) fail('Each outage must have positive duration and lie entirely within the supplied period.');
    return {start: from, end: to};
  }).sort((a, b) => a.start - b.start);
  const joined = [];
  for (const outage of outages) {
    const previous = joined.at(-1);
    if (previous && outage.start < previous.end) fail('Overlapping outages are unsupported.');
    if (previous && outage.start === previous.end) previous.end = outage.end;
    else joined.push({...outage});
  }
  for (const block of supplied) {
    const intersections = joined.filter(outage => outage.start < block.end && outage.end > block.start);
    if (intersections.length > 1) fail('Multiple disjoint outages within one block are unsupported.');
    if (intersections.length) {
      const from = Math.max(block.start, intersections[0].start), to = Math.min(block.end, intersections[0].end);
      const start_hour = (from - block.start) / HOUR;
      block.outage = {start_hour, duration_hours: to === block.end ? 24 - start_hour : (to - from) / HOUR};
    }
  }
  const rows = [], blocks = [], events = [], budgetSegments = [];
  let storage = initial, maxResidual = 0;
  const account = value => {
    maxResidual = Math.max(maxResidual, Math.abs(balance(value)), Math.abs(sum([value.demand_m3, -value.delivered_m3, -value.unmet_m3])));
    if (maxResidual > 1e-6) fail('Water or service accounting residual exceeds the supported 0.000001 m³ tolerance.');
  };
  supplied.forEach((block, block_index) => {
    const dailyInput = {...block.inputs, capacity, reserve, initial: storage, target,
      scenario: {demand_multiplier, production_multiplier, ...(block.outage ? {outage: block.outage} : {})}};
    const result = replayPlan(dailyInput);
    for (const segment of waterServiceModel(dailyInput).segments) budgetSegments.push({...segment, from: segment.from + block_index * 24, to: segment.to + block_index * 24});
    const tagged = event => ({...event, block_index, sequence_hour: block_index * 24 + event.hour});
    blocks.push({block_index, inputs: block.inputs, initial_storage_m3: storage, totals: result.totals, events: result.events.map(tagged), scenario: result.scenario});
    for (const event of result.events) if (!events.some(prior => prior.type === event.type)) events.push(tagged(event));
    for (const row of result.rows) {
      rows.push({...row, block_index, sequence_hour: block_index * 24 + row.hour});
      account({...row, initial_storage_m3: row.storage_start_m3, final_storage_m3: row.storage_end_m3});
    }
    account(result.totals);
    storage = result.totals.final_storage_m3;
  });
  const minimum = Math.min(...blocks.map(block => block.totals.min_storage_m3)), maximum = Math.max(...blocks.map(block => block.totals.max_storage_m3));
  const totals = {initial_storage_m3: initial, final_storage_m3: storage,
    ...Object.fromEntries(flows.map(key => [key, sum(blocks.map(block => block.totals[key]))])),
    min_storage_m3: minimum, max_storage_m3: maximum, max_reserve_deficit_m3: Math.max(0, reserve - minimum), reserve_margin_m3: minimum - reserve,
    terminal_deficit_m3: Math.max(0, target - storage), terminal_surplus_m3: Math.max(0, storage - target), terminal_deviation_m3: storage - target};
  totals.mass_balance_error_m3 = balance(totals);
  account(totals);
  totals.max_abs_accounting_residual_m3 = maxResidual;
  if (!Object.values(totals).every(finite)) fail('Totals exceed finite numeric range.');
  const waterModel = {start_epoch: start, start_hour: 0, end_hour: supplied.length * 24, initial, capacity, reserve, target, segments: budgetSegments};
  const water_budget = waterProductionBudget(waterModel), storage_requirements = storageRequirements(waterModel);
  return {schema: 1, start_time: new Date(start).toISOString(), end_time: new Date(end).toISOString(), rows, blocks, events, totals, water_budget, storage_requirements,
    scenario: {demand_multiplier, production_multiplier}, outages: (input.outages ?? []).map(outage => ({...outage})),
    accounting_scope: 'Maximum absolute residual covers hourly, block and whole-period water and service balances; hourly rows include split outage segments.',
    assumptions: ['Fixed supplied production; no forecast fitting, rescheduling or operating commands.', 'One initial inventory, carried continuously; the final target never resets water.', 'Complete consecutive 24 elapsed-hour blocks; uniform hourly rates, with absolute outage boundaries split by the daily replay.', 'Accounting residuals above 0.000001 m³ reject the review. Event labels inherit the daily replay’s 0.00000001 m³ threshold; smaller deficits remain in totals. Serialized event times have millisecond precision.', 'Declared unit capacity is checked before production derating. No ramp, minimum-run, water-quality, pressure, electrical or grid-permission assessment.', 'Historical supplied plans; issue-time availability and prospective validity are unknown. No recovered-solar, emissions or cost claim.']};
}
