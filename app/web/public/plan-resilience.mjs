// Fixed production replay. No optimization, forecast fitting or plant commands.
const HOUR = 3600000;
const EPS = 1e-8;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const fail = message => { throw Error(`Plan replay: ${message}`); };

function fields(value, allowed, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${label} must be an object.`);
  for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`Unsupported ${label} field: ${key}.`);
}

function number(value, label, min = 0, max = Infinity) {
  if (!finite(value) || value < min || value > max) fail(`${label} must be finite and between ${min} and ${max}.`);
  return value;
}

function timestamp(value) {
  const match = typeof value === 'string' && value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):00:00(?:\.000)?(Z|[+-]\d{2}:\d{2})$/);
  if (!match) fail('Times require explicit offsets and whole hours, with seconds.');
  const [year, month, day, hour] = match.slice(1, 5).map(Number);
  const local = Date.UTC(year, month - 1, day, hour), date = new Date(local), zone = match[5];
  if (year < 1900 || year > 2100 || date.getUTCFullYear() !== year || date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day || date.getUTCHours() !== hour) fail('Invalid calendar timestamp.');
  const zh = zone === 'Z' ? 0 : Number(zone.slice(1, 3)), zm = zone === 'Z' ? 0 : Number(zone.slice(4, 6));
  if (zh > 14 || zm > 59 || (zh === 14 && zm !== 0)) fail('Invalid timestamp offset.');
  return local - (zh * 60 + zm) * (zone.startsWith('-') ? -1 : 1) * 60000;
}

function normalize(input) {
  fields(input, ['times', 'production', 'demand', 'capacity', 'reserve', 'initial', 'target', 'scenario', 'startHour'], 'input');
  if (!Array.isArray(input.times) || input.times.length !== 24) fail('Exactly 24 hourly timestamps are required.');
  const epochs = Array.from(input.times, timestamp);
  if (epochs.some((epoch, i) => i && epoch - epochs[i - 1] !== HOUR)) fail('Only consecutive one-hour intervals are supported.');
  if (!Array.isArray(input.production) || input.production.length !== 24) fail('Exactly 24 production values are required.');
  const production = Array.from(input.production, value => number(value, 'Production'));
  const demand = Array.isArray(input.demand) ? input.demand.slice() : Array(24).fill(input.demand);
  if (demand.length !== 24) fail('Demand must be one number or 24 hourly values.');
  for (const value of demand) number(value, 'Demand');
  const capacity = number(input.capacity, 'Capacity');
  if (!capacity) fail('Capacity must be greater than zero.');
  const reserve = number(input.reserve, 'Reserve', 0, capacity), nominalInitial = number(input.initial, 'Initial storage', 0, capacity), target = number(input.target, 'Target storage', 0, capacity);
  const scenario = input.scenario ?? {};
  if (input.scenario === null) fail('Scenario must be an object.');
  fields(scenario, ['demand_multiplier', 'production_multiplier', 'initial_storage_m3', 'outage', 'restart'], 'scenario');
  const dm = number(scenario.demand_multiplier === undefined ? 1 : scenario.demand_multiplier, 'Demand multiplier'), pm = number(scenario.production_multiplier === undefined ? 1 : scenario.production_multiplier, 'Production multiplier', 0, 1);
  let start = number(input.startHour === undefined ? 0 : input.startHour, 'Start hour', 0, 24), initial = number(scenario.initial_storage_m3 === undefined ? nominalInitial : scenario.initial_storage_m3, 'Scenario initial storage', 0, capacity);
  if (!Number.isInteger(start)) fail('Start hour must be an integer.');
  let restart = null;
  if (scenario.restart !== undefined) {
    fields(scenario.restart, ['hour', 'storage_m3'], 'restart');
    const hour = number(scenario.restart.hour, 'Restart hour', 0, 24), storage = number(scenario.restart.storage_m3, 'Restart storage', 0, capacity);
    if (!Number.isInteger(hour)) fail('Restart hour must be an integer.');
    if (scenario.initial_storage_m3 !== undefined || (input.startHour !== undefined && input.startHour !== hour)) fail('Restart conflicts with an initial storage override or start hour.');
    start = hour; initial = storage; restart = {hour, storage_m3: storage};
  }
  let outage = null;
  if (scenario.outage !== undefined) {
    fields(scenario.outage, ['start_hour', 'duration_hours'], 'outage');
    const beginning = number(scenario.outage.start_hour, 'Outage start', 0, 24), duration = number(scenario.outage.duration_hours, 'Outage duration', 0, 24);
    if (beginning + duration > 24) fail('Outage extends beyond the declared horizon.');
    outage = {start_hour: beginning, duration_hours: duration};
  }
  // Reject arithmetic overflow before evaluating any state.
  for (let i = 0; i < 24; i++) if (![production[i] * pm, demand[i] * dm].every(finite)) fail('Scenario arithmetic exceeds finite numeric range.');
  if (![production.reduce((a, b) => a + b, 0), demand.reduce((a, b) => a + b, 0), demand.reduce((a, b) => a + b * dm, 0)].every(finite)) fail('Scenario totals exceed finite numeric range.');
  return {epochs, production, demand, capacity, reserve, initial, target, dm, pm, start, outage,
    scenario: {demand_multiplier: dm, production_multiplier: pm, ...(restart ? {restart} : {initial_storage_m3: initial}), ...(outage ? {outage} : {})}};
}

function segmentsFor(plan) {
  const segments = [], end = plan.outage ? plan.outage.start_hour + plan.outage.duration_hours : null;
  for (let hour = plan.start; hour < 24; hour++) {
    const boundaries = [hour, hour + 1];
    if (plan.outage) for (const value of [plan.outage.start_hour, end]) if (value > hour && value < hour + 1) boundaries.push(value);
    boundaries.sort((a, b) => a - b);
    for (let i = 1; i < boundaries.length; i++) {
      const from = boundaries[i - 1], to = boundaries[i];
      if (from === to) continue;
      const off = plan.outage && from >= plan.outage.start_hour && from < end;
      segments.push({hour, from, to, duration: to - from, production: off ? 0 : plan.production[hour] * plan.pm, demand: plan.demand[hour], requested: plan.production[hour]});
    }
  }
  return segments;
}

/** Effective binary64 rates for an independent exact comparison of supplied plans. */
export function waterServiceModel(input) {
  const plan = normalize(input);
  if(plan.production.some(value=>value>0&&plan.pm>0&&value*plan.pm===0)||plan.demand.some(value=>value>0&&plan.dm>0&&value*plan.dm===0))fail('Effective water-service rate underflows numeric precision.');
  return {start_epoch:plan.epochs[0],start_hour:plan.start,end_hour:24,initial:plan.initial,capacity:plan.capacity,reserve:plan.reserve,target:plan.target,
    segments:segmentsFor(plan).map(segment=>({from:segment.from,to:segment.to,production:segment.production,demand:segment.demand*plan.dm}))};
}

function marginsFor(plan, segments) {
  let required = plan.reserve, capacityInsufficient = false;
  for (let i = segments.length - 1; i >= 0; i--) {
    const segment = segments[i];
    required = Math.max(plan.reserve, required + (segment.demand * plan.dm - segment.production) * segment.duration);
    if (required > plan.capacity + EPS) capacityInsufficient = true;
  }
  let maximum = Infinity;
  // Every prefix is bounded by starting water; every later interval by tank capacity.
  // These interval constraints exactly include spill for piecewise-constant flows.
  if (plan.initial >= plan.reserve) for (let i = 0; i < segments.length; i++) {
    let production = 0, demand = 0;
    const starting = i === 0 ? plan.initial : plan.capacity;
    for (let j = i; j < segments.length; j++) {
      production += segments[j].production * segments[j].duration;
      demand += segments[j].demand * segments[j].duration;
      if (demand > 0) maximum = Math.min(maximum, (starting - plan.reserve + production) / demand);
    }
  }
  const at = (constraint, hour, intervalStart = plan.start) => ({constraint, hour,
    time: new Date(plan.epochs[0] + hour * HOUR).toISOString(), interval_start_hour: intervalStart});
  let jointRequired = Math.max(plan.reserve, plan.target);
  let initialLimits = [
    ...(plan.reserve >= plan.target ? [at('reserve', 24)] : []),
    ...(plan.target >= plan.reserve ? [at('terminal_target', 24)] : [])
  ];
  const capacityLimits = [];
  for (let i = segments.length - 1; i >= 0; i--) {
    const s = segments[i], next = jointRequired + (s.demand * plan.dm - s.production) * s.duration;
    if (!finite(next)) fail('Joint starting-water requirement exceeds finite numeric range.');
    const limit = at('reserve', s.from);
    if (next < plan.reserve - EPS) initialLimits = [limit];
    else if (Math.abs(next - plan.reserve) <= EPS) initialLimits.push(limit);
    jointRequired = Math.max(plan.reserve, next);
    if (jointRequired > plan.capacity) capacityLimits.push({
      ...at('storage_capacity', s.from, s.from), required_storage_m3: jointRequired
    });
  }
  let jointMaximum = Infinity, jointStatus = 'unbounded', demandLimits = [];
  const candidates = [];
  if (plan.initial < plan.reserve) {
    jointStatus = 'initial_below_reserve';
    demandLimits = [at('initial_reserve', plan.start)];
  } else if (Math.min(plan.capacity, plan.initial + segments.reduce((sum, s) => sum + s.production * s.duration, 0)) < plan.target) {
    jointStatus = 'infeasible_even_without_demand';
    demandLimits = [at('terminal_target', 24)];
  } else {
    // Upper storage clipping makes every suffix begin with at most capacity.
    // Enforce reserve at all boundaries, plus the separate terminal target.
    for (let i = 0; i < segments.length; i++) {
      let production = 0, demand = 0;
      const starting = i === 0 ? plan.initial : plan.capacity;
      for (let j = i; j < segments.length; j++) {
        production += segments[j].production * segments[j].duration;
        demand += segments[j].demand * segments[j].duration;
        if (!demand) continue;
        for (const [constraint, minimum] of [['reserve', plan.reserve], ...(j === segments.length - 1 ? [['terminal_target', plan.target]] : [])]) {
          const bound = (starting - minimum + production) / demand;
          candidates.push({bound, ...at(constraint, segments[j].to, segments[i].from)});
          jointMaximum = Math.min(jointMaximum, bound);
        }
      }
    }
    if (candidates.length && !finite(jointMaximum)) fail('Joint demand bound exceeds finite numeric range.');
    if (finite(jointMaximum)) {
      jointStatus = 'bounded';
      demandLimits = candidates.filter(c => Math.abs(c.bound - jointMaximum) <= 1e-10 * Math.max(1, Math.abs(jointMaximum)))
        .map(({bound, ...limit}) => limit);
    }
  }
  return {minimum_initial_storage_m3: capacityInsufficient ? null : required,
    minimum_initial_status: capacityInsufficient ? 'capacity_insufficient' : 'feasible',
    maximum_demand_multiplier: plan.initial < plan.reserve || maximum === Infinity ? null : maximum,
    maximum_demand_status: plan.initial < plan.reserve ? 'initial_below_reserve' : maximum === Infinity ? 'unbounded' : 'bounded',
    scope: 'Bounds require all demand to be met while retaining reserve under fixed production and outage. Terminal target is excluded. Demand multiplier is relative to the original hourly demand.',
    joint_minimum_initial_storage_m3: capacityLimits.length ? null : jointRequired,
    joint_minimum_initial_status: capacityLimits.length ? 'capacity_insufficient' : 'feasible',
    joint_minimum_initial_limits: capacityLimits.length ? capacityLimits : initialLimits,
    joint_maximum_demand_multiplier: jointStatus === 'bounded' ? jointMaximum : null,
    joint_maximum_demand_status: jointStatus,
    joint_maximum_demand_limits: demandLimits,
    joint_scope: 'All demand must be met, storage must retain reserve from the restart through hour 24, and final storage must reach target. Fixed production, production multiplier and outage. Minimum starting water uses the declared demand multiplier; maximum demand multiplier scales the original hourly demand, not the current multiplier. Null denotes the named non-bounded or infeasible state, never zero headroom. Limiting-constraint ties use 1e-8 m³ for starting water and relative 1e-10 for demand multipliers. No plant feasibility or probability claim.'};
}

/** Quantities are m³ per hour; rates remain uniform inside each supplied hour. */
export function replayPlan(input) {
  const plan = normalize(input), segments = segmentsFor(plan), rows = [], events = [];
  const timeAt = hour => new Date(plan.epochs[0] + hour * HOUR).toISOString();
  const record = (type, hour, storage) => {
    if (!events.some(event => event.type === type)) events.push({type, time: timeAt(hour), hour, storage_m3: storage});
  };
  let storage = plan.initial, minimum = storage, maximum = storage;
  if (storage < plan.reserve) record('reserve_breach', plan.start, storage);
  for (const segment of segments) {
    let row = rows.at(-1);
    if (!row || row.hour !== segment.hour) {
      row = {hour: segment.hour, time: timeAt(segment.hour), end_time: timeAt(segment.hour + 1), storage_start_m3: storage, storage_end_m3: storage,
        requested_production_m3: 0, available_production_m3: 0, demand_m3: 0, delivered_m3: 0, spill_m3: 0, unmet_m3: 0, reserve_deficit_m3: Math.max(0, plan.reserve - storage)};
      rows.push(row);
    }
    const produced = segment.production * segment.duration, demand = segment.demand * plan.dm * segment.duration, netRate = segment.production - segment.demand * plan.dm;
    const unconstrained = storage + produced - demand, spill = Math.max(0, unconstrained - plan.capacity), unmet = Math.max(0, -unconstrained);
    if (netRate < 0) {
      if (storage >= plan.reserve && unconstrained < plan.reserve - EPS) record('reserve_breach', segment.from + (storage - plan.reserve) / -netRate, plan.reserve);
      if (unconstrained < -EPS) record('stockout', segment.from + storage / -netRate, 0);
    }
    if (netRate > 0 && unconstrained > plan.capacity + EPS) record('overflow', segment.from + (plan.capacity - storage) / netRate, plan.capacity);
    storage = Math.min(plan.capacity, Math.max(0, unconstrained));
    minimum = Math.min(minimum, storage); maximum = Math.max(maximum, storage);
    row.requested_production_m3 += segment.requested * segment.duration;
    row.available_production_m3 += produced;
    row.demand_m3 += demand;
    row.delivered_m3 += demand - unmet;
    row.spill_m3 += spill; row.unmet_m3 += unmet;
    row.storage_end_m3 = storage;
    row.reserve_deficit_m3 = Math.max(row.reserve_deficit_m3, plan.reserve - storage);
  }
  const sum = key => rows.reduce((total, row) => total + row[key], 0);
  const totals = {initial_storage_m3: plan.initial, final_storage_m3: storage,
    ...Object.fromEntries(['requested_production_m3', 'available_production_m3', 'demand_m3', 'delivered_m3', 'spill_m3', 'unmet_m3'].map(key => [key, sum(key)])),
    min_storage_m3: minimum, max_storage_m3: maximum, max_reserve_deficit_m3: Math.max(0, plan.reserve - minimum), reserve_margin_m3: minimum - plan.reserve,
    terminal_deficit_m3: Math.max(0, plan.target - storage), terminal_surplus_m3: Math.max(0, storage - plan.target), terminal_deviation_m3: storage - plan.target};
  totals.mass_balance_error_m3 = totals.initial_storage_m3 + totals.available_production_m3 - totals.delivered_m3 - totals.spill_m3 - totals.final_storage_m3;
  if (!Object.values(totals).every(finite)) fail('Replay totals exceed finite numeric range.');
  events.sort((a, b) => a.hour - b.hour);
  return {schema: 1, start_hour: plan.start, end_hour: 24, rows, events, totals, margins: marginsFor(plan, segments), scenario: plan.scenario,
    assumptions: ['Fixed supplied production, with no rescheduling or recovery action. Source-plan unit-capacity validation is external to this replay.', 'Uniform hourly production and demand; outage boundaries split an hour exactly.', 'Excess water spills at capacity; demand exceeding available water is unmet. Storage is physical and bounded.', 'Restart storage and disturbances are reviewer declarations, not authenticated observations.', 'No ramp, minimum-run, water-quality, pressure, grid-permission or electrical-power feasibility assessment. No operating authority or recovered-energy claim.']};
}
