import {createHash} from 'node:crypto';
import {readFileSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve, relative} from 'node:path';
import {performance} from 'node:perf_hooks';
import {replayPlan} from './public/plan-resilience.mjs';

export const PROTOCOL = Object.freeze({
  version: 1, review_hours: .25, horizon_hours: 4, useful_lead_hours: .5, epsilon_m3: 1e-6,
  maximum_observation_age_hours: 2, maximum_trend_gap_hours: 2, observation_hours: 1,
  truth_step_hours: 1 / 60, date_indices: [0, 7, 14, 21, 31, 38, 45, 52, 62, 69, 76, 83],
  methods: ['plan_only', 'current_level', 'two_reading_trend', 'observation_anchored_plan'],
  families: ['nominal', 'initial_shortfall', 'demand_step', 'production_outage', 'demand_burst_recovery', 'evening_demand_step'],
  telemetry: ['timely', 'delay_90_minutes', 'gap_and_invalid_mapping', 'biased_quantized'],
  blocks: ['development', 'heldout'], seed: 74123, bootstrap_seed: 99831, bootstrap_replicates: 1000,
  alarm_budget: null,
  interpretation: 'Predeclared comparisons and trade-offs only; no superiority threshold or field-benefit claim.'
});
const EPS = PROTOCOL.epsilon_m3, HOUR = 3600000;
const hash = value => createHash('sha256').update(typeof value === 'string' || Buffer.isBuffer(value) ? value : JSON.stringify(value)).digest('hex');
const clamp = (value, capacity) => Math.max(0, Math.min(capacity, value));
const rng = seed => () => ((seed = Math.imul(seed, 1664525) + 1013904223 >>> 0) / 4294967296);
const emptyCounts = () => ({cutoffs: 0, safe_cutoffs: 0, active_event_cutoffs: 0, excluded_end_cutoffs: 16, abstentions: 0,
  safe_abstentions: 0, no_reading_cutoffs: 0, stale_reading_cutoffs: 0, invalid_mapping_cutoffs: 0, insufficient_history_cutoffs: 0, alarms: 0, predictive_alarms: 0, true_predictive_cutoffs: 0, false_predictive_cutoffs: 0,
  active_detections: 0, active_abstentions: 0, alarm_episodes: 0, false_alarm_episodes: 0, mixed_alarm_episodes: 0,
  events: 0, events_with_any_early_alarm: 0, events_with_useful_lead: 0, missed_events: 0, initial_unsafe: 0,
  eligible_observation_uses: 0, maximum_used_observation_age_hours: 0, leads_hours: []});

export function disturbance(family, block, seed, capacity) {
  const random = rng(seed), u = random(), held = block === 'heldout';
  const result = {family, initial_m3: capacity * .5, demand_multiplier: 1, production_multiplier: 1, start_hour: 0, end_hour: 24};
  if (family === 'initial_shortfall') result.initial_m3 -= capacity * (held ? .12 + .06 * u : .05 + .05 * u);
  else if (family === 'demand_step') Object.assign(result, {start_hour: 6, demand_multiplier: 1 + (held ? .2 + .12 * u : .08 + .08 * u)});
  else if (family === 'production_outage') Object.assign(result, {start_hour: held ? 11 : 10, end_hour: (held ? 11 : 10) + (held ? 2 + Math.floor(u * 5) / 4 : 1 + Math.floor(u * 3) / 4), production_multiplier: 0});
  else if (family === 'demand_burst_recovery') Object.assign(result, {start_hour: 6, end_hour: 9, demand_multiplier: 1 + (held ? .5 + .3 * u : .2 + .2 * u)});
  else if (family === 'evening_demand_step') Object.assign(result, {start_hour: 17, demand_multiplier: 1 + (held ? .8 + .2 * u : .4 + .2 * u)});
  else if (family !== 'nominal') throw Error('Unknown disturbance family.');
  return result;
}

// Independent truth implementation: minute volumes, physical bounds, explicit balance.
// Disturbance boundaries are minute-aligned; the warning functions never receive them.
export function generateTruth(plan, hidden) {
  const values = [hidden.initial_m3], events = [];
  let storage = hidden.initial_m3, produced = 0, demanded = 0, delivered = 0, spill = 0, unmet = 0;
  let active = storage < plan.reserve - EPS;
  if (active) events.push({start_hour: 0, end_hour: null, initial: true});
  for (let minute = 0; minute < 1440; minute++) {
    const time = minute / 60, hour = Math.floor(time), changed = time >= hidden.start_hour && time < hidden.end_hour;
    const p = plan.production[hour] * (changed ? hidden.production_multiplier : 1) / 60;
    const d = plan.demand * (changed ? hidden.demand_multiplier : 1) / 60;
    const raw = storage + p - d, discarded = Math.max(0, raw - plan.capacity), shortage = Math.max(0, -raw);
    const next = Math.max(0, Math.min(plan.capacity, raw));
    const below = next < plan.reserve - EPS;
    if (!active && below) {
      const rate = (p - d) * 60;
      events.push({start_hour: time + Math.max(0, (plan.reserve - storage) / rate), end_hour: null, initial: false});
      active = true;
    } else if (active && next >= plan.reserve - EPS) {
      const rate = (p - d) * 60;
      events.at(-1).end_hour = time + Math.max(0, (plan.reserve - storage) / rate);
      active = false;
    }
    produced += p; demanded += d; delivered += d - shortage; spill += discarded; unmet += shortage;
    storage = next; values.push(storage);
  }
  const error = hidden.initial_m3 + produced - delivered - spill - storage;
  if (Math.abs(error) > EPS || values.some(value => value < -EPS || value > plan.capacity + EPS)) throw Error('Independent truth balance failed.');
  return {values, events, totals: {produced_m3: produced, requested_m3: demanded, delivered_m3: delivered, spill_m3: spill,
    unmet_m3: unmet, initial_m3: hidden.initial_m3, final_m3: storage, minimum_m3: Math.min(...values), balance_error_m3: error}};
}

export function observationsFor(truth, plan, telemetry, seed) {
  const random = rng(seed), bias = (random() < .5 ? -1 : 1) * plan.capacity * .025;
  const observations = [];
  for (let hour = 0; hour <= 24; hour++) {
    if (telemetry === 'gap_and_invalid_mapping' && hour >= 8 && hour <= 14) continue;
    const exact = truth.values[hour * 60];
    observations.push({id: `tank-${hour}`, asset_id: 'synthetic-tank', observed_hour: hour,
      available_hour: hour + (telemetry === 'delay_90_minutes' ? 1.5 : 0),
      storage_m3: telemetry === 'biased_quantized' ? Math.round((exact + bias) / 5) * 5 : exact});
    const reading = observations.at(-1);
    reading.quality = reading.storage_m3 < 0 || reading.storage_m3 > plan.capacity ? 'invalid_physical_range' : 'valid';
  }
  return {observations, bias_m3: telemetry === 'biased_quantized' ? bias : 0, quantization_m3: telemetry === 'biased_quantized' ? 5 : 0};
}

export function knownObservations(observations, cutoff, mappingValid = true) {
  if (!mappingValid) return [];
  const byTime = new Map();
  for (const reading of observations) {
    if (reading.asset_id !== 'synthetic-tank' || (reading.quality && reading.quality !== 'valid') || reading.observed_hour > cutoff || reading.available_hour > cutoff || reading.available_hour < reading.observed_hour) continue;
    if (!byTime.has(reading.observed_hour) || byTime.get(reading.observed_hour).available_hour < reading.available_hour) byTime.set(reading.observed_hour, reading);
  }
  return [...byTime.values()].sort((a, b) => a.observed_hour - b.observed_hour);
}

function forecastPath(plan, reading) {
  const start = reading?.observed_hour ?? 0, initial = reading?.storage_m3 ?? plan.initial;
  const replay = replayPlan({...plan, scenario: {restart: {hour: start, storage_m3: initial}}});
  return replay.rows.map(row => ({hour: row.hour, start: row.storage_start_m3, end: row.storage_end_m3,
    rate: plan.production[row.hour] - plan.demand}));
}

function pathAlarm(path, plan, cutoff) {
  const row = path.find(row => row.hour === Math.floor(cutoff));
  if (!row) return {alarm: false, reason: 'no_remaining_plan'};
  const now = clamp(row.start + row.rate * (cutoff - row.hour), plan.capacity);
  if (now < plan.reserve - EPS) return {alarm: true, reason: 'projected_current_violation'};
  for (const segment of path) {
    if (segment.rate >= 0 || segment.end >= plan.reserve - EPS || segment.start < plan.reserve - EPS) continue;
    const crossing = segment.hour + (plan.reserve - segment.start) / segment.rate;
    if (crossing > cutoff + 1e-9 && crossing <= cutoff + PROTOCOL.horizon_hours + 1e-9) return {alarm: true, reason: 'predicted_crossing', predicted_crossing_hour: crossing};
    // At the boundary the strict violation begins immediately after this cutoff.
    if (Math.abs(crossing - cutoff) <= 1e-9) return {alarm: true, reason: 'projected_current_violation'};
  }
  return {alarm: false, reason: 'no_predicted_crossing'};
}

export function evaluateWarnings(plan, observations, cutoff, {mappingValid = true, cache = new Map()} = {}) {
  const known = knownObservations(observations, cutoff, mappingValid), latest = known.at(-1);
  const usable = latest && cutoff - latest.observed_hour <= PROTOCOL.maximum_observation_age_hours + 1e-9;
  const status = !mappingValid ? 'invalid_mapping' : !latest ? 'no_known_reading' : !usable ? 'stale_reading' : null;
  if (!cache.has('plan')) cache.set('plan', forecastPath(plan));
  const outputs = {plan_only: {...pathAlarm(cache.get('plan'), plan, cutoff), age_hours: null}};
  for (const method of PROTOCOL.methods.slice(1)) outputs[method] = {alarm: false, abstain: true, reason: status, age_hours: null};
  if (!usable) return outputs;
  const common = {age_hours: cutoff - latest.observed_hour, reading_id: latest.id, reading_observed_hour: latest.observed_hour, reading_available_hour: latest.available_hour};
  outputs.current_level = {...common, alarm: latest.storage_m3 < plan.reserve - EPS, reason: 'latest_measured_level'};
  const cacheKey = JSON.stringify([latest.observed_hour, latest.storage_m3]);
  if (!cache.has(cacheKey)) cache.set(cacheKey, forecastPath(plan, latest));
  outputs.observation_anchored_plan = {...common, ...pathAlarm(cache.get(cacheKey), plan, cutoff)};
  const previous = known.at(-2), gap = previous ? latest.observed_hour - previous.observed_hour : null;
  if (!previous || gap > PROTOCOL.maximum_trend_gap_hours + 1e-9) outputs.two_reading_trend.reason = 'insufficient_recent_history';
  else {
    const slope = (latest.storage_m3 - previous.storage_m3) / gap;
    const current = clamp(latest.storage_m3 + slope * (cutoff - latest.observed_hour), plan.capacity);
    const crossing = slope < 0 ? cutoff + (plan.reserve - current) / slope : null;
    outputs.two_reading_trend = {...common, previous_observed_hour: previous.observed_hour, previous_available_hour: previous.available_hour,
      alarm: current < plan.reserve - EPS || (slope < 0 && crossing >= cutoff - 1e-9 && crossing <= cutoff + PROTOCOL.horizon_hours + 1e-9),
      reason: current < plan.reserve - EPS ? 'trend_current_violation' : 'two_reading_linear_trend', predicted_crossing_hour: crossing};
  }
  return outputs;
}

export function scoreMethod(truth, cutoffs, decisions) {
  const counts = emptyCounts(), events = truth.events.filter(event => !event.initial), leads = Array(events.length).fill(null);
  let episode = null;
  const closeEpisode = () => {
    if (!episode) return;
    counts.alarm_episodes++;
    if (episode.false && !episode.true && !episode.active) counts.false_alarm_episodes++;
    if (episode.false && (episode.true || episode.active)) counts.mixed_alarm_episodes++;
    episode = null;
  };
  for (let index = 0; index < cutoffs.length; index++) {
    const cutoff = cutoffs[index], decision = decisions[index];
    const active = truth.events.some(event => event.start_hour <= cutoff + 1e-9 && (event.end_hour === null || cutoff < event.end_hour - 1e-9));
    counts.cutoffs++; counts[active ? 'active_event_cutoffs' : 'safe_cutoffs']++;
    if (decision.age_hours !== null && decision.age_hours !== undefined) {
      counts.eligible_observation_uses++; counts.maximum_used_observation_age_hours = Math.max(counts.maximum_used_observation_age_hours, decision.age_hours);
    }
    if (decision.abstain) {
      counts.abstentions++; counts[active ? 'active_abstentions' : 'safe_abstentions']++;
      const reasonKey = {no_known_reading: 'no_reading_cutoffs', stale_reading: 'stale_reading_cutoffs', invalid_mapping: 'invalid_mapping_cutoffs', insufficient_recent_history: 'insufficient_history_cutoffs'}[decision.reason];
      if (reasonKey) counts[reasonKey]++;
    }
    if (!decision.alarm) { closeEpisode(); continue; }
    counts.alarms++; episode ??= {true: 0, false: 0, active: 0};
    if (active) { counts.active_detections++; episode.active++; continue; }
    counts.predictive_alarms++;
    const next = events.findIndex(event => event.start_hour > cutoff + 1e-9 && event.start_hour <= cutoff + PROTOCOL.horizon_hours + 1e-9);
    if (next < 0) { counts.false_predictive_cutoffs++; episode.false++; }
    else {
      counts.true_predictive_cutoffs++; episode.true++;
      if (leads[next] === null) leads[next] = events[next].start_hour - cutoff;
    }
  }
  closeEpisode();
  counts.events = events.length; counts.initial_unsafe = truth.events.filter(event => event.initial).length;
  counts.events_with_any_early_alarm = leads.filter(value => value !== null).length;
  counts.events_with_useful_lead = leads.filter(value => value !== null && value >= PROTOCOL.useful_lead_hours - 1e-9).length;
  counts.missed_events = events.length - counts.events_with_useful_lead;
  counts.leads_hours = leads;
  return counts;
}

function aggregate(rows) {
  const result = emptyCounts();
  for (const row of rows) for (const key of Object.keys(result)) {
    if (key === 'leads_hours') result[key].push(...row[key].filter(value => value !== null));
    else if (key === 'maximum_used_observation_age_hours') result[key] = Math.max(result[key], row[key]);
    else result[key] += row[key];
  }
  // emptyCounts carries the per-case end-window exclusion default.
  result.excluded_end_cutoffs -= 16;
  result.cases = rows.length;
  result.useful_event_recall = result.events ? result.events_with_useful_lead / result.events : null;
  result.false_predictive_cutoff_fraction = result.safe_cutoffs ? result.false_predictive_cutoffs / result.safe_cutoffs : null;
  result.false_predictive_fraction_when_evaluable = result.safe_cutoffs > result.safe_abstentions ? result.false_predictive_cutoffs / (result.safe_cutoffs - result.safe_abstentions) : null;
  result.alert_fraction = result.cutoffs ? result.alarms / result.cutoffs : null;
  result.false_alarm_episodes_per_case = result.cases ? result.false_alarm_episodes / result.cases : null;
  const leads = result.leads_hours.sort((a, b) => a - b);
  result.lead_hours = leads.length ? {count: leads.length, minimum: leads[0], median: (leads[Math.floor((leads.length - 1) / 2)] + leads[Math.floor(leads.length / 2)]) / 2, maximum: leads.at(-1)} : null;
  delete result.leads_hours;
  return result;
}

function pairedBootstrap(cases, method, dates) {
  const byDate = dates.map(date => cases.filter(row => row.date === date));
  const difference = blocks => {
    const samples = blocks.flat(), a = aggregate(samples.map(row => row.methods.observation_anchored_plan)), b = aggregate(samples.map(row => row.methods[method]));
    return {useful_recall_difference: a.useful_event_recall === null ? null : a.useful_event_recall - b.useful_event_recall,
      false_predictive_fraction_difference: a.false_predictive_cutoff_fraction - b.false_predictive_cutoff_fraction};
  };
  const random = rng(PROTOCOL.bootstrap_seed), draws = Array.from({length: PROTOCOL.bootstrap_replicates}, () => difference(Array.from({length: dates.length}, () => byDate[Math.floor(random() * dates.length)])));
  const point = difference(byDate), result = {};
  for (const key of Object.keys(point)) {
    const values = draws.map(row => row[key]).filter(value => value !== null).sort((a, b) => a - b);
    result[key] = {estimate: point[key], percentile_95: values.length ? [values[Math.floor(values.length * .025)], values[Math.min(values.length - 1, Math.floor(values.length * .975))]] : null};
  }
  return result;
}

export function runStudy() {
  const root = fileURLToPath(new URL('../', import.meta.url)), args = process.argv.slice(2);
  if (args.length !== 2 || args[0] !== '--output') throw Error('Usage: node web/study_warning_methods.mjs --output results/new-warning-study.json');
  const output = resolve(args[1]), started = new Date().toISOString(), clock = performance.now();
  const sources = ['web/public/data.json', 'web/public/manifest.json', 'web/public/plan-resilience.mjs', 'web/study_warning_methods.mjs', 'web/test_warning_methods.mjs'];
  const bytes = Object.fromEntries(sources.map(path => [path, readFileSync(resolve(root, path))]));
  const hashes = Object.fromEntries(sources.map(path => [path, hash(bytes[path])]));
  const data = JSON.parse(bytes[sources[0]]), manifest = JSON.parse(bytes[sources[1]]);
  if (hashes[sources[0]] !== manifest.data_sha256 || data.days.length !== 92 || data.demand !== 120) throw Error('Retained data identity does not match.');
  const cases = [], truthCases = [], cutoffs = Array.from({length: 81}, (_, i) => i / 4);
  let nominalError = 0, balanceError = 0, informationViolations = 0;
  const dates = PROTOCOL.date_indices.map(index => data.days[index].date);
  for (const dateIndex of PROTOCOL.date_indices) for (const tank of data.tanks) for (const family of PROTOCOL.families) for (const block of PROTOCOL.blocks) {
    const day = data.days[dateIndex], schedule = day.schedules[String(tank)];
    const plan = {times: day.times, production: schedule.production, demand: data.demand, capacity: tank, reserve: tank * .2, initial: tank * .5, target: tank * .5};
    const planHash = hash(plan), seed = Number.parseInt(hash([PROTOCOL.seed, day.date, tank, family, block]).slice(0, 8), 16);
    const hidden = disturbance(family, block, seed, tank), truth = generateTruth(plan, hidden);
    balanceError = Math.max(balanceError, Math.abs(truth.totals.balance_error_m3));
    if (family === 'nominal') for (let hour = 1; hour <= 24; hour++) nominalError = Math.max(nominalError, Math.abs(truth.values[hour * 60] - schedule.storage[hour - 1]));
    const truthIndex = truthCases.length;
    truthCases.push({date: day.date, timeline_origin: day.times[0], date_index: dateIndex, tank_m3: tank, family, block, seed, plan_sha256: planHash,
      hidden_disturbance: hidden, truth_values_sha256: hash(truth.values), events: truth.events, totals: truth.totals});
    for (const telemetry of PROTOCOL.telemetry) {
      const observations = observationsFor(truth, plan, telemetry, seed + 1), cache = new Map();
      const decisions = cutoffs.map(cutoff => evaluateWarnings(plan, observations.observations, cutoff,
        {cache, mappingValid: !(telemetry === 'gap_and_invalid_mapping' && cutoff >= 16 && cutoff < 18)}));
      for (let i = 0; i < decisions.length; i++) for (const decision of Object.values(decisions[i])) {
        if (decision.reading_observed_hour > cutoffs[i] || decision.reading_available_hour > cutoffs[i] || decision.previous_observed_hour > cutoffs[i] || decision.previous_available_hour > cutoffs[i]) informationViolations++;
      }
      if (hash(plan) !== planHash) throw Error('Evaluator changed its immutable plan.');
      cases.push({truth_index: truthIndex, date: day.date, tank_m3: tank, family, block, telemetry,
        observations_sha256: hash(observations.observations), reading_count: observations.observations.length, after_record_available_readings: observations.observations.filter(row => row.available_hour > 24).length, invalid_physical_readings: observations.observations.filter(row => row.quality !== 'valid').length, bias_m3: observations.bias_m3, quantization_m3: observations.quantization_m3,
        methods: Object.fromEntries(PROTOCOL.methods.map(method => [method, scoreMethod(truth, cutoffs, decisions.map(row => row[method]))]))});
    }
  }
  if (nominalError > EPS || informationViolations || cases.length !== 2880) throw Error('Study acceptance check failed.');
  const summary = [];
  for (const block of PROTOCOL.blocks) for (const telemetry of PROTOCOL.telemetry) for (const family of ['all', ...PROTOCOL.families]) {
    const selected = cases.filter(row => row.block === block && row.telemetry === telemetry && (family === 'all' || row.family === family));
    summary.push({block, telemetry, family, methods: Object.fromEntries(PROTOCOL.methods.map(method => [method, aggregate(selected.map(row => row.methods[method]))]))});
  }
  const paired = PROTOCOL.blocks.map(block => ({block, uncertainty_unit: 'Resampled date blocks retain all tanks, families and telemetry for that date; 12 dates, not independent sensor samples.',
    comparisons: Object.fromEntries(PROTOCOL.methods.slice(0, 3).map(method => [method, pairedBootstrap(cases.filter(row => row.block === block), method, dates)]))}));
  for (const path of sources) if (hash(readFileSync(resolve(root, path))) !== hashes[path]) throw Error(`Input changed while running: ${path}`);
  const methodColumns = Object.keys(emptyCounts()), methodRows = [];
  for (const [caseIndex, row] of cases.entries()) for (const [methodIndex, method] of PROTOCOL.methods.entries()) methodRows.push([caseIndex, methodIndex, ...methodColumns.map(key => row.methods[method][key])]);
  const report = {schema: 1, kind: 'Synthetic fixed-plan warning comparison', status: 'completed',
    execution: {started_at: started, completed_at: new Date().toISOString(), elapsed_ms: performance.now() - clock,
      command: [process.execPath, ...process.argv.slice(1)], reproduce_from_repository_root: `node web/study_warning_methods.mjs --output ${relative(root, output)}`, node: process.version},
    input_sha256: hashes, protocol_sha256: hash(PROTOCOL), protocol: PROTOCOL,
    design: {case_count: cases.length, independent_truth_trajectories: truthCases.length, method_case_count: methodRows.length,
      reviewed_cutoffs: cases.length * cutoffs.length, dates, tanks: data.tanks, cutoffs_hours: cutoffs,
      time_basis: 'All observation/availability/event times are elapsed hours from each truth case timeline_origin, an ISO timestamp with explicit UTC offset. Absolute time is origin plus elapsed 3600000ms. These retained July–September days are 24-hour timelines; no general civil-day/DST support is claimed.',
      methods: {plan_only: 'Original 50%-full initial inventory and immutable plan; no observations.',
        current_level: 'Latest eligible measured inventory, never silently advanced; alarms below reserve; age limit applies.',
        two_reading_trend: 'Two latest distinct eligible hourly observations, gap <=2h; linear rate continued through reading age and 4h horizon, bounded to [0, capacity]. This deliberately simple comparator can miss known planned production changes.',
        observation_anchored_plan: 'Restart unchanged nominal production and demand at the latest eligible hourly inventory observation; explicitly propagate through reading age to cutoff, then examine next 4h. No hidden disturbance parameters enter.'},
      event_matching: 'Strict below-reserve excursions, exact crossing within truth minute segment, recovery at reserve; no hysteresis or merging of distinct recovered excursions. A crossing at cutoff is active detection, never early warning. For each safe cutoff, alarm matches only the first future crossing within 4h. Each event receives only its first matched warning and is useful at >=30min issue-to-crossing lead. An alarm cannot match multiple events at a cutoff.',
      burden: 'Adjacent alarm cutoffs form episodes; an episode is false only if all its alarms are false predictive alarms. Mixed episodes are reported separately so an early false alert is not erased by later detection. Raw false predictive cutoff count is primary burden; active detections excluded from predictive scoring.',
      exclusions: 'Reviews0..20h include full 4h outcome horizon; 20:15..24:00 (16 cutoffs per case) are explicitly unscored. Events in the final4h remain eligible if earlier warnings predict them. Initial unsafe cases are separate, never credited as future events.',
      telemetry: 'Hourly observations include separate observation and first-available times.90min-delay data arrive later; gap omits hours 8..14; that profile also invalidates tank mapping at cutoffs 16..18. Bias is predeclared ±2.5% capacity then 5m3 quantization, with no claimed calibration accuracy; readings outside physical bounds are retained but ineligible, never clipped. Observed value is never moved to its availability time.',
      split: 'Parameter blocks are predeclared disjoint severity ranges for each disturbed family. No fitting, threshold tuning or model selection uses either block. Nominal controls are repeated in both blocks. Dates are deterministically sampled from retained dates before scoring. Heldout is a synthetic parameter stress test, not unseen real-world generalization.'},
    acceptance: {inputs_unchanged: true, information_cutoff_violations: informationViolations, maximum_truth_balance_error_m3: balanceError,
      maximum_nominal_hourly_difference_from_retained_m3: nominalError, all_cases_reported: true},
    summary, paired_date_block_bootstrap: paired,
    limitations: ['All observations and disturbances are synthetic; events and assumed rates are not calibrated to a Pafos plant.',
      'No intervention, new forecast, retraining, schedule optimization, plant control, cost saving, energy recovery or scientific novelty is established. Stefanos retains forecasting and scheduling.',
      'The anchored method assumes future nominal demand and planned production despite hidden changes; it can miss sudden outages and continued demand shocks. Passing accounting checks does not establish operational safety.',
      'Two-reading extrapolation is intentionally simple and sensitive to noise, delay and planned production changes. It is not a comprehensive industrial alarm-system baseline.',
      'Different tank sizes also start with different water inventories. Days reset independently. Scenario/telemetry frequencies are artificial, not estimated probabilities.',
      'Thresholds, 4h horizon and 30min useful lead are engineering proposals, not operator-agreed response times. No alarm budget was selected; results report trade-offs, not a winner.',
      'Date-block bootstrap intervals describe this small constructed ensemble and retain paired dependence; they do not express field uncertainty or independent replication across tank/shock variants.',
      'Only simple storage accounting is represented; ramps, minimum run times, flushing, pressure, salinity, quality and actual grid constraints are absent.'],
    truth_cases: truthCases, observation_cases: cases.map(({methods, ...row}) => row),
    method_case_outputs: {columns: ['case_index', 'method_index', ...methodColumns], rows: methodRows}};
  const encoded = JSON.stringify(report) + '\n';
  writeFileSync(output, encoded, {flag: 'wx'});
  console.log(JSON.stringify({output, bytes: Buffer.byteLength(encoded), cases: cases.length, truth_trajectories: truthCases.length,
    methods: methodRows.length, acceptance: report.acceptance, elapsed_ms: report.execution.elapsed_ms}));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) runStudy();
