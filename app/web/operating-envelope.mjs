// Frozen contract: results/operating-envelope/PROTOCOL.md. No inferred unit states or limits.
const MAX_RECORDS = 26352;
const SCALE = 1n << 1074n;
const LIMITS = {
  maximum_rate: 'maximum_rate_m3_h',
  minimum_production_rate: 'minimum_production_rate_m3_h',
  ramp_up: 'ramp_up_m3_h2',
  ramp_down: 'ramp_down_m3_h2',
  minimum_online: 'minimum_online_hours',
  minimum_offline: 'minimum_offline_hours',
};

function object(value, keys, required, path) {
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw new TypeError(`${path} must be an object`);
  for (const key of Reflect.ownKeys(value)) if (!keys.includes(key)) throw new TypeError(`${path}: unknown field ${String(key)}`);
  for (const key of required) if (!Object.hasOwn(value, key)) throw new TypeError(`${path}/${key} is required`);
}
function number(value, path) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) throw new TypeError(`${path} must be finite and nonnegative`);
}
function state(value, path) {
  if (value !== 'online' && value !== 'offline') throw new TypeError(`${path} must be online or offline`);
}
function records(value, minimum, path) {
  if (!Array.isArray(value) || value.length < minimum || value.length > MAX_RECORDS) throw new TypeError(`${path} must contain ${minimum}–${MAX_RECORDS} records`);
}
function partition(values, horizon, keys, path, validate) {
  records(values, 1, path);
  let next = horizon.start_hour;
  for (const [i, value] of values.entries()) {
    object(value, keys, keys, `${path}/${i}`);
    number(value.from_hour, `${path}/${i}/from_hour`);
    number(value.to_hour, `${path}/${i}/to_hour`);
    if (value.from_hour !== next || value.to_hour <= value.from_hour) throw new TypeError(`${path}/${i} must continue a positive-duration partition`);
    validate(value, `${path}/${i}`);
    next = value.to_hour;
  }
  if (next !== horizon.end_hour) throw new TypeError(`${path} must end at the horizon end`);
}
function validate(input) {
  object(input, ['schema', 'kind', 'unit_id', 'rate_basis', 'horizon', 'trajectory', 'states', 'initial_state', 'limits'], ['schema', 'kind', 'unit_id', 'rate_basis', 'horizon'], 'input');
  if (input.schema !== 1 || input.kind !== 'supplied_unit_operating_envelope') throw new TypeError('Unsupported operating-envelope schema or kind');
  if (typeof input.unit_id !== 'string' || !input.unit_id.trim()) throw new TypeError('unit_id must be nonempty');
  if (input.rate_basis !== 'net_product_water') throw new TypeError('rate_basis must be net_product_water');
  const { horizon, trajectory, states, initial_state: initial, limits } = input;
  object(horizon, ['start_hour', 'end_hour'], ['start_hour', 'end_hour'], '/horizon');
  number(horizon.start_hour, '/horizon/start_hour');
  number(horizon.end_hour, '/horizon/end_hour');
  if (horizon.end_hour <= horizon.start_hour) throw new TypeError('Horizon must have positive duration');
  if (limits != null) {
    object(limits, Object.values(LIMITS), [], '/limits');
    for (const [key, value] of Object.entries(limits)) if (value !== null) number(value, `/limits/${key}`);
    if (limits.minimum_production_rate_m3_h != null && limits.maximum_rate_m3_h != null &&
        limits.minimum_production_rate_m3_h > limits.maximum_rate_m3_h) throw new TypeError('Production minimum exceeds maximum rate');
  }
  if (trajectory != null) {
    if (trajectory.representation === 'continuous_piecewise_linear') {
      object(trajectory, ['representation', 'points'], ['representation', 'points'], '/trajectory');
      records(trajectory.points, 2, '/trajectory/points');
      let previous = -Infinity;
      for (const [i, point] of trajectory.points.entries()) {
        object(point, ['hour', 'rate_m3_h'], ['hour', 'rate_m3_h'], `/trajectory/points/${i}`);
        number(point.hour, `/trajectory/points/${i}/hour`);
        number(point.rate_m3_h, `/trajectory/points/${i}/rate_m3_h`);
        if (point.hour <= previous) throw new TypeError('Trajectory hours must strictly increase');
        previous = point.hour;
      }
      if (trajectory.points[0].hour !== horizon.start_hour || trajectory.points.at(-1).hour !== horizon.end_hour) throw new TypeError('Trajectory must cover the exact horizon');
    } else if (trajectory.representation === 'interval_mean') {
      object(trajectory, ['representation', 'intervals'], ['representation', 'intervals'], '/trajectory');
      partition(trajectory.intervals, horizon, ['from_hour', 'to_hour', 'rate_m3_h'], '/trajectory/intervals', (row, path) => number(row.rate_m3_h, `${path}/rate_m3_h`));
    } else throw new TypeError('Unsupported trajectory representation');
  }
  if (states != null) partition(states, horizon, ['from_hour', 'to_hour', 'state', 'producing'], '/states', (row, path) => {
    state(row.state, `${path}/state`);
    if (![true, false, null].includes(row.producing)) throw new TypeError(`${path}/producing must be boolean or null`);
    if (row.state === 'offline' && row.producing === true) throw new TypeError(`${path}: offline cannot be producing`);
  });
  if (initial != null) {
    object(initial, ['state', 'age_hours'], ['state', 'age_hours'], '/initial_state');
    state(initial.state, '/initial_state/state');
    if (initial.age_hours !== null) number(initial.age_hours, '/initial_state/age_hours');
  }
}

// Finite binary64 inputs are integral multiples of 2^-1074. Cross-products keep comparisons exact.
function ticks(value) {
  const view = new DataView(new ArrayBuffer(8));
  view.setFloat64(0, value);
  const bits = view.getBigUint64(0), exponent = Number((bits >> 52n) & 2047n), fraction = bits & ((1n << 52n) - 1n);
  return exponent ? ((1n << 52n) | fraction) << BigInt(exponent - 1) : fraction;
}
function quantity(n, d = SCALE) {
  let a = n < 0n ? -n : n, b = d;
  while (b) [a, b] = [b, a % b];
  n /= a; d /= a;
  if (!n) return { value: 0, exact: { numerator: '0', denominator: '1' } };
  const unsigned = n < 0n ? -n : n;
  let exponent = unsigned.toString(2).length - d.toString(2).length;
  if (exponent >= 0 ? unsigned < (d << BigInt(exponent)) : (unsigned << BigInt(-exponent)) < d) exponent--;
  let value = null;
  if (exponent <= 1023 && exponent >= -1075) {
    const shift = exponent < -1022 ? 1074 : 52 - exponent;
    const numerator = shift >= 0 ? unsigned << BigInt(shift) : unsigned;
    const denominator = shift >= 0 ? d : d << BigInt(-shift);
    let rounded = numerator / denominator;
    const remainder = numerator % denominator;
    if (2n * remainder > denominator || (2n * remainder === denominator && (rounded & 1n))) rounded++;
    const display = Number(rounded) * (exponent < -1022 ? Number.MIN_VALUE : 2 ** (exponent - 52));
    if (Number.isFinite(display) && display !== 0) value = n < 0n ? -display : display;
  }
  return { value, exact: { numerator: String(n), denominator: String(d) } };
}

export function evaluateOperatingEnvelope(input) {
  validate(input);
  const limits = Object.fromEntries(Object.entries(LIMITS).map(([check, key]) => [check, input.limits?.[key] == null ? null : ticks(input.limits[key])]));
  const checks = Object.fromEntries(Object.keys(LIMITS).map(key => [key, { status: limits[key] === null ? 'unknown' : 'met', reasons: limits[key] === null ? ['Limit not supplied.'] : [], violations: [] }]));
  const tail_obligations = [];
  function unknown(key, reason) {
    if (checks[key].status !== 'violated') checks[key].status = 'unknown';
    if (!checks[key].reasons.includes(reason)) checks[key].reasons.push(reason);
  }
  function violation(key, kind, from, to, observed, difference, sources) {
    checks[key].status = 'violated';
    checks[key].violations.push({ kind, from_hour: quantity(from), to_hour: quantity(to), observed,
      limit: quantity(limits[key]), excess_or_shortfall: difference, sources: [...sources, `/limits/${LIMITS[key]}`] });
  }
  const states = input.states?.map((row, i) => ({ ...row, from: ticks(row.from_hour), to: ticks(row.to_hour), source: `/states/${i}` }));
  const trajectory = input.trajectory;
  const points = trajectory?.representation === 'continuous_piecewise_linear' ? trajectory.points.map((row, i) => ({ time: ticks(row.hour), rate: ticks(row.rate_m3_h), source: `/trajectory/points/${i}` })) : null;
  const means = trajectory?.representation === 'interval_mean' ? trajectory.intervals.map((row, i) => ({ from: ticks(row.from_hour), to: ticks(row.to_hour), rate: ticks(row.rate_m3_h), source: `/trajectory/intervals/${i}` })) : null;
  for (const key of ['maximum_rate', 'ramp_up', 'ramp_down']) {
    if (limits[key] === null) continue;
    if (!points) unknown(key, means ? 'Interval means cannot certify a continuous rate bound.' : 'Continuous trajectory not supplied.');
  }
  if (limits.maximum_rate !== null) {
    for (const point of points ?? []) if (point.rate > limits.maximum_rate) violation('maximum_rate', 'point_rate', point.time, point.time, quantity(point.rate), quantity(point.rate - limits.maximum_rate), [point.source]);
    for (const mean of means ?? []) if (mean.rate > limits.maximum_rate) violation('maximum_rate', 'interval_mean_bound', mean.from, mean.to, quantity(mean.rate), quantity(mean.rate - limits.maximum_rate), [mean.source]);
  }
  for (let i = 0; points && i < points.length - 1; i++) {
    const a = points[i], b = points[i + 1], delta = b.rate - a.rate, duration = b.time - a.time;
    const key = delta < 0n ? 'ramp_down' : 'ramp_up', magnitude = delta < 0n ? -delta : delta;
    if (limits[key] !== null && magnitude * SCALE > limits[key] * duration) {
      violation(key, 'segment_slope', a.time, b.time, quantity(magnitude, duration), quantity(magnitude * SCALE - limits[key] * duration, duration * SCALE), [a.source, b.source]);
    }
  }

  const minimum = limits.minimum_production_rate;
  if (minimum !== null) {
    if (!states) unknown('minimum_production_rate', 'Production applicability not supplied.');
    else if (states.every(row => row.state === 'offline' || row.producing === false)) checks.minimum_production_rate.status = 'not_applicable';
    else {
      if (states.some(row => row.state === 'online' && row.producing === null)) unknown('minimum_production_rate', 'Production applicability is unknown for part of the horizon.');
      if (!points) unknown('minimum_production_rate', means ? 'Interval means cannot certify pointwise production rates.' : 'Continuous trajectory not supplied.');
      if (points) {
        let segment = 0;
        const at = (time, i) => {
          const a = points[i], b = points[i + 1];
          if (time === a.time) return { n: a.rate, d: SCALE, time, sources: [a.source] };
          if (time === b.time) return { n: b.rate, d: SCALE, time, sources: [b.source] };
          const duration = b.time - a.time;
          return { n: a.rate * duration + (b.rate - a.rate) * (time - a.time), d: duration * SCALE, time, sources: [a.source, b.source] };
        };
        for (const row of states) {
          while (segment < points.length - 2 && points[segment + 1].time <= row.from) segment++;
          if (row.producing !== true) continue;
          let lowest = at(row.from, segment);
          const consider = candidate => { if (candidate.n * lowest.d < lowest.n * candidate.d) lowest = candidate; };
          while (points[segment + 1].time < row.to) { consider(at(points[segment + 1].time, segment)); segment++; }
          consider(at(row.to, segment));
          if (lowest.n * SCALE < minimum * lowest.d) violation('minimum_production_rate', 'productive_rate', lowest.time, lowest.time, quantity(lowest.n, lowest.d), quantity(minimum * lowest.d - lowest.n * SCALE, lowest.d * SCALE), [row.source, ...lowest.sources]);
        }
      }
      if (means) {
        let index = 0;
        for (const mean of means) {
          while (states[index].to <= mean.from) index++;
          let j = index, productive = true;
          const sources = [mean.source];
          while (j < states.length && states[j].from < mean.to) {
            productive &&= states[j].producing === true;
            sources.push(states[j].source);
            if (states[j].to >= mean.to) break;
            j++;
          }
          index = j;
          if (productive && mean.rate < minimum) violation('minimum_production_rate', 'interval_mean_bound', mean.from, mean.to, quantity(mean.rate), quantity(minimum - mean.rate), sources);
        }
      }
    }
  }

  if (!states) {
    for (const key of ['minimum_online', 'minimum_offline']) if (limits[key] !== null) unknown(key, 'Unit-state history not supplied.');
  } else {
    const applicable = { online: false, offline: false };
    const runs = [];
    for (const row of states) {
      const last = runs.at(-1);
      if (last?.state === row.state) { last.to = row.to; last.sources.push(row.source); }
      else runs.push({ state: row.state, from: row.from, to: row.to, sources: [row.source] });
    }
    function duration(run, elapsed, known, completed, sources) {
      const key = `minimum_${run.state}`, limit = limits[key];
      applicable[run.state] = true;
      if (limit === null || elapsed >= limit) return;
      if (completed && known) violation(key, 'completed_duration', run.to - elapsed, run.to, quantity(elapsed), quantity(limit - elapsed), sources);
      else {
        unknown(key, completed ? 'Initial run age is needed to assess a completed duration.' : 'Continuation beyond the supplied horizon remains unresolved.');
        if (!completed) tail_obligations.push({ state: run.state, at_hour: quantity(run.to), remaining_min_hours: quantity(known ? limit - elapsed : 0n), remaining_max_hours: quantity(limit - elapsed) });
      }
    }
    const initial = input.initial_state, first = runs[0];
    if (!initial) {
      const opposite = first.state === 'online' ? 'offline' : 'online', key = `minimum_${opposite}`;
      applicable[opposite] = true;
      if (limits[key] !== null && limits[key] > 0n) unknown(key, 'Possible opposite-state transition at the horizon start has no supplied age.');
    } else if (initial.state !== first.state) {
      duration({ state: initial.state, to: first.from }, initial.age_hours === null ? 0n : ticks(initial.age_hours), initial.age_hours !== null, true, ['/initial_state', first.sources[0]]);
    }
    for (const [i, run] of runs.entries()) {
      const carried = i === 0 && initial?.state === run.state;
      const known = i > 0 || (initial != null && (!carried || initial.age_hours !== null));
      const age = carried && initial.age_hours !== null ? ticks(initial.age_hours) : 0n;
      const sources = i === 0 && initial ? ['/initial_state', ...run.sources] : [...run.sources];
      if (i < runs.length - 1) sources.push(runs[i + 1].sources[0]);
      duration(run, run.to - run.from + age, known, i < runs.length - 1, sources);
    }
    for (const name of ['online', 'offline']) if (!applicable[name] && limits[`minimum_${name}`] !== null) checks[`minimum_${name}`].status = 'not_applicable';
  }
  const statuses = Object.values(checks).map(check => check.status);
  const status = statuses.includes('violated') ? 'violated' : statuses.includes('unknown') || tail_obligations.length ? 'unknown' : 'met';
  return { schema: 1, kind: 'supplied_unit_operating_envelope_review', status,
    decision: { met: 'checked_limits_met', violated: 'revise_trace', unknown: 'supply_evidence' }[status], checks, tail_obligations,
    scope: ['Declared single-unit checks only.', 'Evidence and limits are caller-declared, not authenticated.', 'No plant authorization.',
      'Pressure, water quality, flushing consumption and electrical behavior are not assessed.', 'No forecast or schedule generation.', 'No electricity or solar-benefit claim.'] };
}
