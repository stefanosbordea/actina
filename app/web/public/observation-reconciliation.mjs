// Point comparisons only: never integrate observations or infer plant authority.
import {pilotTime, validatePilotContract, pilotColumns} from './pilot.mjs';
import {replayPlan} from './plan-resilience.mjs';

const roles = {tank: 'tank_storage_m3', production: 'production_rate_m3_h', unit_power: 'unit_load_kw', available_power: 'available_power_kw'};
const HOUR = 3600000, EPS = 1e-6;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const fail = message => { throw Error(`Observation reconciliation: ${message}`); };
function fields(value, allowed, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) fail(`${label} must be an object.`);
  for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`Unsupported ${label} field: ${key}.`);
}
function instant(value, label) {
  const parsed = pilotTime(value);
  if (parsed.error) fail(`${label}: ${parsed.error}`);
  return parsed.epoch;
}
function positive(value, label, allowZero = true) {
  if (!finite(value) || (allowZero ? value < 0 : value <= 0)) fail(`${label} must be a finite ${allowZero ? 'nonnegative' : 'positive'} number.`);
  return value;
}

function checkPlan(plan) {
  fields(plan, ['times', 'production', 'storage_start', 'storage', 'demand', 'capacity', 'reserve', 'initial', 'target', 'unit_capacity_m3_h', 'identity'], 'plan');
  const unitCapacity = positive(plan.unit_capacity_m3_h, 'Unit capacity', false);
  let replay;
  try { replay = replayPlan(Object.fromEntries(['times', 'production', 'demand', 'capacity', 'reserve', 'initial', 'target'].map(key => [key, plan[key]]))); }
  catch (error) { fail(error.message); }
  if (plan.production.some(value => value > unitCapacity + EPS)) fail('Supplied plan exceeds its declared unit capacity.');
  for (const key of ['storage_start', 'storage']) {
    if (!Array.isArray(plan[key]) || plan[key].length !== 24) fail(`${key} requires 24 supplied values.`);
    for (let hour = 0; hour < 24; hour++) {
      const value = plan[key][hour], expected = replay.rows[hour][key === 'storage' ? 'storage_end_m3' : 'storage_start_m3'];
      if (!finite(value) || Math.abs(value - expected) > EPS) fail(`${key} does not match declared water balance at hour ${hour}.`);
    }
  }
  if (replay.totals.max_reserve_deficit_m3 > EPS || replay.totals.unmet_m3 > EPS || replay.totals.spill_m3 > EPS || Math.abs(replay.totals.terminal_deviation_m3) > EPS) fail('Supplied nominal plan violates declared reserve, demand, capacity or terminal inventory.');
  return instant(plan.times[0], 'Plan start');
}

function observations(record, declaration) {
  if (!Array.isArray(record.observations) || record.observations.length > 100000) fail('Observations must be an array of at most 100,000 normalized rows.');
  const streams = new Map(declaration.streams.map(stream => [`${stream.asset_id}\0${stream.measurement}`, stream])), seen = new Set();
  return Array.from(record.observations, row => {
    fields(row, pilotColumns, 'observation');
    for (const field of pilotColumns) if (!Object.hasOwn(row, field)) fail(`Observation is missing ${field}.`);
    if (typeof row.asset_id !== 'string' || typeof row.measurement !== 'string') fail('Observation asset and measurement must be unambiguous string identifiers.');
    const epoch = instant(row.time, 'Observation time'), available = instant(row.available_at, 'First availability');
    if (available < epoch) fail('An observation cannot be available before its measurement time.');
    if (epoch < declaration.start || epoch >= declaration.end || (epoch - declaration.start) % declaration.step !== 0) fail('Observation lies outside the declared window or cadence.');
    const stream = streams.get(`${row.asset_id}\0${row.measurement}`);
    if (!stream) fail('Observation references an undeclared asset or measurement.');
    if (row.unit !== stream.unit || !finite(row.value) || row.value < stream.min || row.value > stream.max) fail('Observation unit or value differs from its declared numeric contract.');
    const key = `${epoch}\0${row.asset_id}\0${row.measurement}`;
    if (seen.has(key)) fail('Duplicate observation instant for the same stream.');
    seen.add(key);
    return {...row, epoch, available, key};
  });
}

export function reconcileObservations(input) {
  fields(input, ['record', 'plan', 'mapping', 'tolerances', 'review_as_of', 'specific_energy_kwh_m3'], 'input');
  const {record, plan, mapping, tolerances} = input;
  fields(record, ['schema', 'kind', 'scope', 'sourceDeclaration', 'identity', 'reviewAsOf', 'reviewTimeBasis', 'status', 'reviewRequired', 'expectedSlots', 'knownSlots', 'streams', 'missing', 'issues', 'warnings', 'observations'], 'record');
  if (record.schema !== 1 || record.kind !== 'AquaShift observation intake review' || !['PARTIAL', 'COMPLETE'].includes(record.status) || !Array.isArray(record.issues) || record.issues.length) fail('Use a nonblocked schema-1 pilotRecord.');
  const declaration = validatePilotContract(record.sourceDeclaration);
  if (declaration.issues.length) fail(`Source declaration failed: ${declaration.issues.map(issue => issue.message).join(' ')}`);
  const cutoff = instant(input.review_as_of, 'Review cutoff');
  if (record.reviewAsOf !== null) instant(record.reviewAsOf, 'Original intake review time');
  if (!record.identity || typeof record.identity !== 'object' || Array.isArray(record.identity)) fail('Retain the input file identities.');
  for (const key of ['contract', 'observations']) if (typeof record.identity[key]?.sha256 !== 'string' || !/^[a-f0-9]{64}$/.test(record.identity[key].sha256)) fail(`Missing ${key} SHA-256 identity.`);
  fields(mapping, Object.keys(roles), 'mapping');
  for (const [role, asset] of Object.entries(mapping)) {
    if (typeof asset !== 'string' || !declaration.streams.some(stream => stream.asset_id === asset && stream.measurement === roles[role])) fail(`Mapping ${role} must name one declared asset with measurement ${roles[role]}.`);
  }
  fields(tolerances, ['tank_storage_m3', 'production_rate_m3_h', 'unit_load_kw', 'power_difference_kw'], 'tolerances');
  for (const key of ['tank_storage_m3', 'production_rate_m3_h', 'unit_load_kw', 'power_difference_kw']) positive(tolerances[key], `Tolerance ${key}`);
  const sec = input.specific_energy_kwh_m3 === undefined ? null : positive(input.specific_energy_kwh_m3, 'Specific energy', false);
  const planStart = checkPlan(plan), all = observations(record, declaration), known = all.filter(row => row.available <= cutoff);
  const supplied = new Map(all.map(row => [row.key, row])), visible = new Map(known.map(row => [row.key, row]));
  const rows = [];
  const source = (row, role) => ({role, asset_id: row.asset_id, measurement: row.measurement, time: row.time, available_at: row.available_at, value: row.value, unit: row.unit});
  const sample = (role, epoch) => {
    if (!Object.hasOwn(mapping, role)) return {row: null, reason: 'stream_not_mapped'};
    const key = `${epoch}\0${mapping[role]}\0${roles[role]}`;
    return {row: visible.get(key) ?? null, reason: visible.has(key) ? null : supplied.has(key) ? 'not_available_at_review_time' : 'no_observation_supplied'};
  };
  function comparison({epoch, kind, role, unit, expected, tolerance, reason = null, hour = null}) {
    const reading = sample(role, epoch), observed = reading.row?.value ?? null;
    const difference = observed === null || expected === null ? null : observed - expected;
    if (difference !== null && !finite(difference)) fail('Point comparison exceeds finite numeric range.');
    rows.push({time: new Date(epoch).toISOString(), kind, unit, status: difference === null ? 'unknown' : Math.abs(difference) > tolerance ? 'requires_explanation' : 'within_tolerance',
      observed, expected, difference, tolerance, plan_hour: hour,
      reason: reading.reason ?? reason, sources: reading.row ? [source(reading.row, role)] : []});
  }
  for (let epoch = declaration.start; epoch < declaration.end; epoch += declaration.step) {
    const position = (epoch - planStart) / HOUR, inPlan = position >= 0 && position < 24, hour = inPlan ? Math.floor(position) : null;
    const boundary = position >= 0 && position <= 24 && Number.isInteger(position);
    comparison({epoch, kind: 'tank_storage', role: 'tank', unit: 'm3', expected: boundary ? position === 24 ? plan.storage[23] : plan.storage_start[position] : null,
      tolerance: tolerances.tank_storage_m3, reason: boundary ? null : position < 0 || position > 24 ? 'outside_plan_horizon' : 'not_an_exact_plan_boundary', hour: boundary ? position : null});
    comparison({epoch, kind: 'production_rate', role: 'production', unit: 'm3/h', expected: inPlan ? plan.production[hour] : null,
      tolerance: tolerances.production_rate_m3_h, reason: inPlan ? null : 'outside_plan_horizon', hour});
    const expectedPower = inPlan && sec !== null ? plan.production[hour] * sec : null;
    if (expectedPower !== null && !finite(expectedPower)) fail('Declared specific energy exceeds finite modeled-power range.');
    comparison({epoch, kind: 'modeled_power', role: 'unit_power', unit: 'kW', expected: expectedPower,
      tolerance: tolerances.unit_load_kw, reason: !inPlan ? 'outside_plan_horizon' : sec === null ? 'specific_energy_not_declared' : null, hour});
    const unitPower = sample('unit_power', epoch), availablePower = sample('available_power', epoch);
    const difference = unitPower.row && availablePower.row ? unitPower.row.value - availablePower.row.value : null;
    if (difference !== null && !finite(difference)) fail('Simultaneous power difference exceeds finite numeric range.');
    rows.push({time: new Date(epoch).toISOString(), kind: 'reported_power_difference', unit: 'kW', status: difference === null ? 'unknown' : difference > tolerances.power_difference_kw ? 'requires_explanation' : 'within_tolerance',
      observed: unitPower.row?.value ?? null, expected: availablePower.row?.value ?? null, difference, tolerance: tolerances.power_difference_kw, plan_hour: null,
      reason: difference === null ? [unitPower.reason && `unit_power:${unitPower.reason}`, availablePower.reason && `available_power:${availablePower.reason}`].filter(Boolean).join('; ') : null,
      sources: [unitPower.row && source(unitPower.row, 'unit_power'), availablePower.row && source(availablePower.row, 'available_power')].filter(Boolean)});
  }
  return {schema: 1, kind: 'AquaShift point observation reconciliation', review_as_of: new Date(cutoff).toISOString(), original_intake_review_as_of: record.reviewAsOf,
    review_basis: 'Caller-declared cutoff, reapplied independently to every observation first-available time. Intake summary counts are not reused.',
    source: {kind: record.sourceDeclaration.source_kind, label: record.sourceDeclaration.source_label, declaration: structuredClone(record.sourceDeclaration), identity: structuredClone(record.identity)},
    plan: structuredClone(plan), mapping: {...mapping}, tolerances: {...tolerances}, specific_energy_kwh_m3: sec,
    coverage: {supplied_observations: all.length, known_observations: known.length, withheld_observations: all.length - known.length, comparison_rows: rows.length,
      unknown_comparisons: rows.filter(row => row.status === 'unknown').length, requires_explanation: rows.filter(row => row.status === 'requires_explanation').length}, rows,
    limitations: ['Point observations are never integrated into water or energy totals. Exact timestamps only; no nearest pairing, carrying forward or tank interpolation.',
      'Production and modeled power use the supplied uniform rate in the containing hour. Tank values use exact supplied plan boundaries only.',
      'Tolerances, specific energy, stream mappings and source labels are caller declarations, not calibrated uncertainty or verified source authority.',
      'Input file hashes are retained caller metadata. Original file bytes are not available to this function, so their hashes are not independently recomputed.',
      'The power comparison is one-sided: unit load minus reported available power above the declared tolerance requires explanation. A unit may use grid and solar power; this is not a grid violation or recovered energy.',
      'Numeric nominal-plan validation checks the declared water balance, tank bounds, unit capacity and terminal target. It does not establish actual plant feasibility, water quality or operating permission.']};
}
