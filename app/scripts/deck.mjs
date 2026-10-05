import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import os from 'node:os';

const ROOT = fileURLToPath(new URL('../', import.meta.url));
process.env.RUNTIME_NODE_MODULES ??= path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules');
process.env.RUNTIME_NODE ??= process.execPath;
process.env.RUNTIME_PYTHON ??= path.resolve(process.env.RUNTIME_NODE_MODULES, '../../python/bin/python3');
const SKILL = process.env.AQUASHIFT_PRESENTATIONS_SKILL ?? path.join(os.homedir(), '.codex/plugins/cache/openai-primary-runtime/presentations/26.904.11930/skills/presentations');
const PYTHON = process.env.RUNTIME_PYTHON;
const artifact = process.env.AQUASHIFT_ARTIFACT_TOOL_FILE ?? path.join(process.env.RUNTIME_NODE_MODULES, '@oai/artifact-tool/dist/artifact_tool.mjs');
const { Presentation, PresentationFile } = await import(pathToFileURL(artifact));
const BUILD = path.join(ROOT, 'build');
const OUTPUT = path.resolve(ROOT, process.argv[2] ?? 'delivery/AquaShift-Pafos-2026.pptx');
const { resolvePresentationFont, applyPresentationChartFont, finalizePresentation } = await import(pathToFileURL(path.join(SKILL, 'container_tools/artifact_tool_utils.mjs')));
const FAMILY = resolvePresentationFont({ fontFamily: 'Arial' });
const C = { navy: '#101010', teal: '#1A1A1A', aqua: '#DADADA', gold: '#555555', gray: '#737373', bg: '#FAFAFA', ink: '#141414', light: '#DDDDDD', white: '#FFFFFF' };
const data = JSON.parse(await fs.readFile(path.join(BUILD, 'deck-data.json'), 'utf8'));
const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
const records = [];
const n = value => new Intl.NumberFormat('en', { maximumFractionDigits: 0 }).format(value);
const fixed = (value, digits = 1) => Number(value).toFixed(digits);

function text(slide, content, left, top, width, height, size = 30, options = {}) {
  const shape = slide.shapes.add({ geometry: 'textbox', name: options.name ?? `text-${slide.shapes.items?.length ?? 0}`, position: { left, top, width, height }, fill: 'none', line: { fill: 'none', width: 0 } });
  shape.text = content;
  shape.text.style = { typeface: FAMILY, fontSize: size, bold: !!options.bold, color: options.color ?? C.ink, autoFit: 'none', alignment: options.align ?? 'left', verticalAlignment: 'top', ...options.style };
  return shape;
}
function add(title, seconds, speaker, note, sources = [], dark = false) {
  const slide = presentation.slides.add();
  const index = records.length + 1;
  slide.background.fill = dark ? C.navy : C.bg;
  if (title) text(slide, title, 64, 42, 1152, 92, 48, { bold: true, color: dark ? C.white : C.navy, name: 'slide-title' });
  text(slide, `${String(index).padStart(2, '0')} / 12`, 1120, 670, 96, 24, 18, { color: dark ? C.aqua : C.gray, align: 'right', name: 'slide-number' });
  const cues = index === 6 ? '\n\nPresenter cues (not spoken): 0-20 s: Overview, 1 July, tank 4,000 m³, inspect hour 13. 20-45 s: Scenarios, compare 500 and 8,000 m³; point to equal water and assumed tariffs. 45-65 s: Evaluation, MAE 8.81 versus 7.64. 65-85 s: Alerts & Sites, switch the synthetic anomaly off and on. 85-90 s: return to Overview. Fallback: play AquaShift-Concept-and-Prototype.mp4 instead of the live sequence; do not play both.' : index === 9 ? '\n\nPresenter cue (not spoken): Open delivery/AquaShift-Business-Model-Canvas.pdf and keep its one-page nine-block canvas visible while presenting this slide. Return to slide 10 afterwards. Allow the switch within this slide slot.' : '';
  const preparation = index === 1 ? '\n\nPreparation note (not spoken): AI tools assisted implementation, drafting and review. These artifacts are a starting point for the team to check and rehearse.' : '';
  const full = `SLIDE ${index}: ${title || 'AquaShift'}\nTiming: ${seconds} seconds. Presenter: ${speaker}.${preparation}\n\nSpoken text:\n${note}${cues}\n\nSources (not spoken):\n${sources.join('\n')}`;
  slide.speakerNotes.textFrame.setText(full);
  records.push({ index, title: title || 'AquaShift', seconds, speaker, spoken: note, sources, note: full });
  return slide;
}
function body(slide, heading, copy, left, top, width = 530, color = C.ink) {
  text(slide, heading, left, top, width, 50, 32, { bold: true, color });
  text(slide, copy, left, top + 64, width, 210, 30, { color });
}
function chart(slide, kind, config) {
  const result = slide.charts.add(kind, {
    chartFill: 'none', chartLine: { fill: 'none', width: 0 }, plotAreaFill: 'none', plotAreaLine: { fill: 'none', width: 0 },
    xAxis: { textStyle: { typeface: FAMILY, fontSize: 22, fill: C.gray }, line: { fill: C.light, width: 1 }, majorGridlines: null },
    yAxis: { min: 0, textStyle: { typeface: FAMILY, fontSize: 22, fill: C.gray }, line: { fill: 'none', width: 0 }, majorGridlines: { fill: C.light, width: 1 } },
    legend: { position: 'bottom', overlay: false, textStyle: { typeface: FAMILY, fontSize: 22, fill: C.ink } },
    ...config,
    series: config.series.map(series => ({ valuesFormatCode: '0.0', ...series, values: series.values.map(value => Number(Number(value).toFixed(6))) })),
  });
  applyPresentationChartFont(result, { fontFamily: FAMILY });
  return result;
}
const sourcePitch = 'AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.';
const sourceEval = 'results/metrics.json; results/independent-review.json. Open-Meteo ECMWF IFS historical reconstruction. Training targets before 1 July; test July to September 2026. Nominal previous-day 18:00 cutoff; original publication vintages uncertified.';
const sourceScenario = 'model/scheduler.py; build/deck-data.json, 15 July. Unit 500 m³/h, tank 4,000 m³, demand 120 m³/h, energy 3.4 kWh/m³, reserve 800 m³. Assumed prices €101/MWh at hours 10-16, €183 at 17-22, €130 otherwise. Uniform hourly flows; real ramp/minimum-run/maintenance constraints absent.';

// 1
{
  const s = add('', 45, 'Στέφανος Μπορτέας', `AquaShift starts with a simple idea: use solar power that would otherwise be curtailed to make drinking water, then store that water for later. Loucas proposed the core idea; Stefanos developed the roadmap. We are testing how it could work with a desalination unit, a tank and a useful planning tool. The draft already lets us compare schedules and inspect the forecast evidence. Recovering curtailed solar will still need a plant with spare capacity, usable storage and permission from the grid operator. Today we will show the concept, the prototype and the evidence we need for a pilot in Paphos.`, [sourcePitch, 'Team contribution credit: Loucas proposed the core idea; Stefanos developed the roadmap.'], true);
  text(s, 'AquaShift', 64, 68, 700, 60, 34, { bold: true, color: C.aqua });
  text(s, 'Desalination with\notherwise curtailed solar', 64, 178, 1140, 235, 76, { bold: true, color: C.white });
  text(s, 'Store water for later use', 68, 446, 1100, 70, 36, { color: C.aqua });
  text(s, 'Original concept and philosophy: Loucas Louka', 68, 545, 1110, 49, 28, { color: C.white });
  text(s, 'Starting point for team review. Actual curtailment use remains unproven.\nPafos 2.0 University category, October 2026', 68, 614, 1110, 68, 23, { color: C.aqua });
}
// 2
{
  const s = add('Paphos needs water resilience', 65, 'Andreas Nikolaides', `Paphos has good reasons to plan its water supply carefully. Cyprus Mail reported that its three main dams were around nine percent full in January 2026, using Water Development Department figures. By September, conditions had improved: Asprokremmos was reported at 37.6 percent. The January number on this slide is dated context, rather than today's reservoir level. On the electricity side, a CyprusGrid industry estimate put curtailed distributed renewable generation at roughly 306 gigawatt-hours across Cyprus in 2025. That national estimate cannot tell us how much a particular plant could use. It does show why flexible demand deserves investigation. A desalination operator needs to produce enough water every day. If some of that production can move into otherwise curtailed solar hours, a tank could help carry the supply into later demand.`, [
    'Cyprus Mail, 14 January 2026, reports WDD figures: https://cyprus-mail.com/2026/01/14/paphos-water-supply-at-amid-critically-low-dam-levels',
    'Cyprus Mail, 23 September 2026, reports WDD/CNA: https://cyprus-mail.com/2026/09/23/pomos-has-highest-water-level-in-paphos-reservoirs',
    'pv magazine, 13 January 2026, citing CyprusGrid industry analysis: https://www.pv-magazine.com/2026/01/13/cyprus-solar-curtailment-hits-47-in-2025/',
    'Cyprus Mail guest analysis, 19 March 2026: https://cyprus-mail.com/2026/03/19/why-cyprus-wastes-nearly-half-its-solar-energy-and-what-battery-storage-could-fix',
  ]);
  text(s, '9%', 64, 185, 430, 115, 92, { bold: true, color: C.teal });
  text(s, 'Three main Paphos dams\nJanuary 2026', 68, 310, 470, 90, 30);
  text(s, '306 GWh', 650, 185, 566, 115, 92, { bold: true, color: C.teal });
  text(s, 'Estimated distributed renewable\ncurtailment in Cyprus, 2025', 654, 310, 550, 105, 30);
  text(s, 'Water conditions improved in 2026. Flexibility still needs spare plant capacity and storage.', 68, 510, 1120, 112, 32, { bold: true, color: C.navy });
  text(s, 'Dated context, not current reservoir readings. Industry estimate, not plant-level surplus.', 68, 631, 1080, 29, 19, { color: C.gray });
}
// 3
{
  const s = add('Grid and Sites', 55, 'Στέφανος Μπορτέας', `Stefanos's roadmap develops the idea into Grid and Sites. Grid helps a water operator compare production schedules for a desalination unit and its tank. Sites helps a hotel or garden operator review an irrigation budget and unusual overnight meter readings. We propose starting with a small site because it gives us a manageable place to collect data and work with an operator. Grid would need more work on operating limits, electricity arrangements and procurement. Both parts currently give advice. They send no command to a plant or irrigation controller. The operator can inspect the inputs, compare the suggestion with a baseline and decide whether the recommendation makes sense.`, [sourcePitch]);
  body(s, 'AquaShift Grid', 'Plan desalination around prices and storage limits\n\nProspective users: water authorities and plant operators', 64, 185);
  body(s, 'AquaShift Sites', 'Estimate irrigation need and flag unusual night flow\n\nProspective users: hotels, parks and gardens', 654, 185);
  text(s, 'Sites: the first pilot hypothesis\nGrid: the larger infrastructure path', 68, 520, 1100, 106, 34, { bold: true, color: C.teal });
}
// 4
{
  const s = add('A working planning loop', 70, 'Loucas Louka', `The planning loop starts with saved historical weather for Paphos. We keep its source and timestamps, estimate the following day's solar radiation, then compare the prediction with simple controls. The weather is a gridded reconstruction, so this test cannot establish how an operational forecast would have performed at the time. Radiation tells us about sunny hours; an actual curtailment signal has to come from the grid. Historical EAC reports now give the workspace dated grid context. The planner uses assumed hourly electricity prices and limits on production and storage. The forecast orders production within hours that have the same price. The dashboard then shows the plan, the tank trajectory and the evidence behind them. Saved rows can be exported for review. If the scheduler has no usable forecast, it retains the flat baseline. If production capacity cannot meet demand, it reports that the scenario is infeasible.`, [sourceEval, sourceScenario, 'Implementation: model/train.py, eval/evaluate.py, model/scheduler.py, model/sites.py; web/public. Grid context: data/eac_curtailment_days.json, 62 July/August EAC daily reports; main report fields only, not plant allocation.']);
  const rows = [
    ['01', 'Weather and timestamps', 'Historical Paphos data, with the source retained'],
    ['02', 'Forecast and evaluation', 'Chronological holdout with a strong persistence control'],
    ['03', 'Storage-constrained planning', 'Illustrative tariffs and hard water-balance limits'],
    ['04', 'Operator advice', 'Dashboard, downloadable schedule and explicit failures'],
  ];
  rows.forEach(([number, heading, copy], i) => {
    const y = 164 + i * 113;
    text(s, number, 66, y, 88, 74, 48, { bold: true, color: C.teal });
    text(s, heading, 170, y, 1020, 48, 32, { bold: true });
    text(s, copy, 170, y + 51, 1020, 42, 27, { color: C.gray });
  });
}
// 5
{
  const g = data.grid;
  const s = add('Same water and energy, different hours', 80, 'Στέφανος Μπορτέας', `This example uses 15 July. Both plans make 2,880 cubic metres of water and use 9,792 kilowatt-hours. The tank starts and finishes with 2,000 cubic metres. That prevents a cheaper plan from borrowing water from the following day. With the assumed hourly prices, the flat plan costs about 1,320 euros and the shifted plan about 989 euros: a 25.1 percent scenario reduction. The reduction comes from cheaper production hours and enough storage to use them. We checked the contribution of forecasting across all 92 test days. The reference model, strong persistence, climatology and a price-only plan produced exactly the same water, energy and tariff cost. Added AI cost benefit was zero euros. Equal energy at a constant carbon factor also gives zero modeled carbon saving. A real pilot must measure whether the changed production uses solar that would otherwise be curtailed before we can claim that benefit.`, [sourceScenario, 'Attribution source: results/independent-review.json. Four forecast strategies have equal 92-day cost, water and energy.']);
  chart(s, 'bar', { position: { left: 56, top: 174, width: 780, height: 390 }, categories: data.grid_frame.hour.map(hour => String(hour)), series: [{ name: 'Flat schedule', values: data.grid_frame.baseline_m3, fill: C.gray }, { name: 'AquaShift', values: data.grid_frame.scheduled_m3, fill: C.teal }], barOptions: { direction: 'column', grouping: 'clustered', gapWidth: 80 }, hasLegend: true, yAxis: { min: 0, max: 550, majorUnit: 100, title: 'Production (m³/hour)', textStyle: { typeface: FAMILY, fontSize: 20, fill: C.gray }, majorGridlines: { fill: C.light, width: 1 } } });
  text(s, `${fixed(g.cost_saving_percent)}%`, 890, 174, 310, 95, 68, { bold: true, color: C.teal });
  text(s, 'Illustrative tariff reduction', 890, 278, 320, 90, 27);
  text(s, `${n(g.water_produced_m3)} m³\n${n(g.energy_kwh)} kWh`, 890, 391, 320, 110, 34, { bold: true });
  text(s, '15 July 2026. Equal water, energy and terminal storage. Added AI cost saving: €0. No measured CO₂ benefit.', 68, 578, 1130, 72, 24, { color: C.gray });
}
// 6
{
  const s = add('The demo and its fallback', 120, 'Loucas Louka', `We will spend ninety seconds in the workspace. Start with one saved day, then compare tank sizes. The water total stays fixed while the production plan changes. We will check the forecast comparison and switch the simulated meter anomaly off and on. If the browser fails, the ninety-second film shows the concept and the working draft.`, [sourceScenario, 'Workspace: https://aquashift-pafos-2026.vercel.app. Fallback: delivery/AquaShift-Concept-and-Prototype.mp4. The July 1 demo date differs from the July 15 numerical example on slides 5 and 8.']);
  text(s, 'A date, a tank size, a visible outcome', 64, 174, 1130, 78, 42, { bold: true, color: C.teal });
  const steps = [
    'Production schedule and tank trajectory',
    'Smaller tank, less flexibility',
    'Forecast errors against the strong baseline',
    'Synthetic leak on, then off',
  ];
  steps.forEach((value, i) => text(s, `${i + 1}. ${value}`, 68, 280 + i * 63, 1080, 56, 31));
  text(s, 'Insufficient capacity gives a clear infeasible result\nOffline backup: video and exported schedule', 68, 559, 1100, 96, 29, { bold: true, color: C.navy });
}
// 7
{
  const m = data.metrics.all;
  const worse = (m.model.mae / m.persistence.mae - 1) * 100;
  const s = add('The stronger control wins on MAE', 100, 'Loucas Louka', `We evaluated an independent reference while waiting for Stefanos's model handoff. The test covers 2,208 hours over 92 days, from July through September. For the control, we assume same-hour readings through six p.m. are available at the previous day's issue time. We have not verified publication delays or the original data vintages. The rule uses the preceding day through six p.m., and the day before that for later hours. On mean absolute error, the reference scores 8.81 watts per square metre; stronger persistence scores 7.64. The reference is about 15.4 percent worse on that measure. Its lower root mean square error suggests fewer large errors, so the measures need to be read together. The paired-day interval for the MAE difference is about plus 0.18 to plus 2.07. Sunny-hour precision is close: 98.20 percent for the model and 98.36 for persistence. Those flags describe radiation, not measured surplus electricity. Added AI forecasting value remains unproven. Next we should freeze Stefanos's model and Loucas's prediction experiments and compare them with this control, without tuning on the test quarter.`, [sourceEval, 'Strong baseline nominal rule: day−1 same local hour for target 00–18, day−2 for 19–23. Paired-day bootstrap 2,000 repeats, seed 20261002. Seasonal dependence remains.']);
  chart(s, 'bar', { position: { left: 56, top: 174, width: 760, height: 408 }, categories: ['MAE', 'RMSE'], series: [{ name: 'Reference model', values: [m.model.mae, m.model.rmse], fill: C.teal }, { name: 'Latest-safe persistence', values: [m.persistence.mae, m.persistence.rmse], fill: C.gray }], barOptions: { direction: 'column', grouping: 'clustered', gapWidth: 120 }, hasLegend: true, dataLabels: { showValue: true, position: 'outEnd', textStyle: { typeface: FAMILY, fontSize: 23, fill: C.ink }, }, yAxis: { min: 0, max: 24, majorUnit: 6, numberFormatCode: '0.0', title: 'Error (W/m²)', textStyle: { typeface: FAMILY, fontSize: 21, fill: C.gray }, majorGridlines: { fill: C.light, width: 1 } } });
  text(s, `${fixed(worse)}%`, 870, 190, 345, 110, 72, { bold: true, color: C.gold });
  text(s, 'Higher MAE than persistence', 873, 303, 322, 92, 30);
  text(s, 'Added AI benefit\nremains unproven', 873, 454, 338, 110, 33, { bold: true, color: C.navy });
  text(s, '2,208 held-out hours, July–September 2026. Historical weather reconstruction.', 68, 615, 1100, 42, 24, { color: C.gray });
}
// 8
{
  const irrigation = data.sites;
  const s = add('Sites: irrigation and an overnight fixture', 70, 'Loucas Louka', `Sites applies the same approach to a garden and a meter. For 15 July, the saved weather gives evapotranspiration of about 6.32 millimetres. With an assumed 5,000-square-metre garden, crop coefficient and irrigation efficiency, the suggested amount is about 26 cubic metres. A six-millimetre timer would apply 30. The 13.3 percent difference is a scenario comparison; a hotter day or a different timer can change its direction. We also generate normal meter history and keep the query day out of training. Adding 0.3 cubic metres per hour over four night hours gives four flagged fixture hours, compared with none in the matched no-leak control. That tests the review workflow. Field detection accuracy still needs real meter histories, faults and seasonal patterns. In a pilot, the operator should help choose and review the alert threshold.`, ['Source: model/sites.py and build/deck-data.json. ET0 and rainfall sum over 15 July 2026 local time. Area 5,000 m², crop coefficient 0.70, efficiency 0.85, effective rain 80%, assumed soil reserve 0 mm, timer 6 mm/day.', 'Meter history and query are synthetic. IsolationForest trains only on 28 generated normal days. Injected event: 0.3 m³/h in hours 01–04, 1.2 m³ total. Fixture labels never enter fitting.']);
  chart(s, 'bar', { position: { left: 64, top: 188, width: 650, height: 390 }, categories: ['Fixed timer', 'Weather scenario'], series: [{ name: 'Applied water', values: [irrigation.timer_m3, irrigation.recommended_m3], fill: C.teal, points: [{ idx: 0, fill: C.gray }, { idx: 1, fill: C.teal }] }], barOptions: { direction: 'column', gapWidth: 110 }, hasLegend: false, dataLabels: { showValue: true, position: 'outEnd', textStyle: { typeface: FAMILY, fontSize: 24, fill: C.ink } }, yAxis: { min: 0, max: 36, majorUnit: 9, title: 'Water (m³)', textStyle: { typeface: FAMILY, fontSize: 22, fill: C.gray }, majorGridlines: { fill: C.light, width: 1 } } });
  text(s, '4 / 4', 808, 183, 390, 100, 70, { bold: true, color: C.teal });
  text(s, 'Injected leak hours flagged', 811, 295, 373, 88, 29);
  text(s, '0', 808, 410, 390, 80, 66, { bold: true, color: C.teal });
  text(s, 'No-leak control alerts', 811, 501, 373, 88, 29);
  text(s, 'Retrospective weather calculation and synthetic meter fixture. Field performance remains unvalidated.', 68, 611, 1130, 54, 24, { color: C.gray });
}
// 9
{
  const s = add('The business model hypotheses', 80, 'Cleopas Cleopa', `I'll show our one-page business model canvas now. Our first customer segment is a hotel or municipal garden with a usable meter. The value proposition is practical water advice whose benefit we can measure. Direct operator contacts and irrigation installers are the proposed channels. Customer relationships would start with a hands-on pilot and regular review. The revenue hypothesis is a monthly Sites fee of 99 to 299 euros or a share of verified savings; Grid could later use a licence or the proposed twenty-percent savings share. We still need to test those prices, and we have no signed customer or revenue. Our resources are the team's skills, meter access and weather data. The activities are evaluating forecasts, reviewing plans and supporting the site. Partners would include the site operator, an installer and a water or plant operator for Grid. The main costs are team time, meter integration and support. Andreas and Cleopas will test these assumptions in customer interviews.`, [sourcePitch, 'delivery/AquaShift-Business-Model-Canvas.pdf: all nine canvas blocks presented alongside slide 9.']);
  body(s, 'Sites', 'First customer hypothesis: a hotel or garden operator\n\nProposed price: €99–299 per site each month', 64, 183);
  body(s, 'Grid', 'Later customer hypothesis: a water or plant operator\n\nProposed revenue: licence or 20% of verified savings', 654, 183);
  text(s, 'Customer interviews and a measured pilot precede pricing decisions', 68, 528, 1100, 104, 35, { bold: true, color: C.teal });
  text(s, 'No signed customer or revenue. Prices and channels remain proposals.', 68, 634, 1100, 27, 22, { color: C.gray });
}
// 10
{
  const s = add('Safety, privacy and AI disclosure', 55, 'Στέφανος Μπορτέας', `An operator must approve any action in a real pilot. The model checks water balance, storage limits and production capacity, but equipment also has ramp rates, maintenance needs, salinity limits and other constraints. Those need to be added with the plant operator. The scheduler retains a flat baseline when the forecast is missing and blocks an infeasible plan. For site data, we would agree access, purpose, retention and deletion with the owner, keep private readings separate and record approvals. AI tools assisted the coding, drafting and review of this starting point. We will disclose that assistance, credit the software we used and have the team review the submission. The draft has not undergone field safety testing or a legal compliance assessment.`, [sourceScenario, sourcePitch, 'Competition source: supplied Official rules.pdf. AI assistance includes OpenAI Codex for implementation, evaluation review, artifact preparation and editing. Team members must review and confirm the final submission and tool disclosure.']);
  body(s, 'Water supply', 'Operator approval before action\n\nHard modeled limits and explicit fallback\n\nField equipment constraints still required', 64, 184);
  body(s, 'Site data and responsibility', 'Agreed meter access and retention\n\nLogged recommendations and approvals\n\nAI assistance and upstream tools declared', 654, 184);
  text(s, 'Advice mode today. Field validation before deployment.', 68, 555, 1100, 82, 36, { bold: true, color: C.teal });
}
// 11
{
  const s = add('A 30 / 60 / 90 day pilot path', 55, 'Andreas Nikolaides', `We propose three pilot stages. In the first thirty days, agree one site, a data contact and a measurement plan. Check the meter units, missing data, operating limits and who approves actions. Continue only with a usable baseline and an agreed scope. By sixty days, run suggestions in shadow mode. Compare the simple control, Stefanos's model and Loucas's prediction experiments on fresh data, and record false alerts and operator feedback. If prediction adds no value, simplify it. By ninety days, consider a small controlled trial with the operator's approval. Compare equal water supply, storage, costs and any measured renewable displacement. The business team will use the results to test payment and support costs. If a plant has no spare capacity, Sites remains a smaller pilot option.`, [sourcePitch, 'Proposed pilot stages; site approval and fresh measurements required.']);
  const columns = [
    ['30 days', 'Site and baseline', 'Verified meter data\nAgreed operating limits\nNamed site approver', 'Go: usable data and agreed scope'],
    ['60 days', 'Shadow advice', 'Frozen forecast comparisons\nOperator review\nFalse-alert monitoring', 'Go: repeatable value over controls'],
    ['90 days', 'Controlled pilot', 'Approved limited actions\nMatched outcome comparison\nMeasured cost and water', 'Go: safe, practical benefit'],
  ];
  columns.forEach(([label, heading, copy, gate], i) => {
    const x = 64 + i * 390;
    text(s, label, x, 177, 360, 73, 50, { bold: true, color: C.teal });
    text(s, heading, x, 270, 360, 52, 31, { bold: true });
    text(s, copy, x, 344, 360, 172, 28);
    text(s, gate, x, 542, 360, 100, 25, { bold: true, color: C.navy });
  });
}
// 12
{
  const s = add('The team and the pilot ask', 35, 'Cleopas Cleopa', `Loucas proposed the core idea and will work on evaluation, the dashboard and prediction experiments. Stefanos developed the roadmap and leads the model and scheduler work. Andreas Nikolaides and Cleopas Cleopa are business students working on the business case and pitch. Our ask is one Paphos pilot site and one data contact. A hotel garden could start Sites; a plant or water operator could help test Grid. We would agree the baseline, begin in advice mode and measure the result. Thank you.`, [sourcePitch, 'Team roles confirmed by Loucas. Greek name retained as supplied; no overall team lead assigned.'], true);
  text(s, 'One Paphos pilot site\nOne data contact', 64, 164, 1140, 157, 60, { bold: true, color: C.aqua });
  text(s, 'Technical', 68, 365, 525, 42, 26, { bold: true, color: C.aqua });
  text(s, 'Στέφανος Μπορτέας\nRoadmap expansion, primary model and scheduler\n\nLoucas Louka\nOriginal concept and philosophy\nEvaluation, dashboard and prediction experiments', 68, 414, 570, 218, 23, { color: C.white });
  text(s, 'Business', 680, 365, 525, 42, 26, { bold: true, color: C.aqua });
  text(s, 'Andreas Nikolaides\nCleopas Cleopa\n\nBusiness case and pitch', 680, 414, 515, 191, 27, { color: C.white });
  text(s, 'AI-assisted draft for team review. Actual curtailment use remains unproven.', 68, 641, 1100, 31, 21, { color: C.aqua });
}

if (records.length !== 12 || records.reduce((sum, record) => sum + record.seconds, 0) !== 830) throw new Error('Slide count or speaking duration mismatch');
await fs.mkdir(path.join(BUILD, 'deck-previews'), { recursive: true });
await fs.mkdir(path.dirname(OUTPUT), { recursive: true });
const candidate = path.join(BUILD, `AquaShift-candidate-${Date.now()}.pptx`);
await (await PresentationFile.exportPptx(presentation)).save(candidate);
const previewSlides = process.argv.includes('--changed-only') ? [0, 11] : presentation.slides.items.map((_, index) => index);
for (const i of previewSlides) {
  const slide = presentation.slides.items[i];
  const blob = await presentation.export({ slide, format: 'png', scale: 1 });
  await fs.writeFile(path.join(BUILD, 'deck-previews', `slide-${String(i + 1).padStart(2, '0')}.png`), new Uint8Array(await blob.arrayBuffer()));
  const layout = await slide.export({ format: 'layout' });
  await fs.writeFile(path.join(BUILD, 'deck-previews', `slide-${String(i + 1).padStart(2, '0')}.layout.json`), await layout.text());
}
const report = await finalizePresentation({
  workspaceDir: ROOT,
  candidatePath: candidate,
  finalPath: OUTPUT,
  pythonExecutable: PYTHON,
  integrityValidatorPath: path.join(SKILL, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(SKILL, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '12192000,6858000', '--validate-bullet-geometry', '--validate-heading-fit'],
  explicitTotalSlideCount: 12,
  requiredNativeChartOwnerSlides: [5, 7, 8],
  requiredNativeTableOwnerSlides: [],
  materializeLiteralChartWorkbooks: true,
  fontPolicy: { basis: 'design', families: [FAMILY] },
  verifyArtifactToolImport: true,
  receiptPath: path.join(BUILD, `${path.basename(path.dirname(OUTPUT))}-${path.basename(OUTPUT)}.validation.json`),
});
await fs.writeFile(path.join(ROOT, 'delivery/AquaShift-Speaker-Notes.md'), '# AquaShift speaker notes\n\nTarget 13 minutes 50 seconds, including a 90-second live demo or video fallback. This leaves 1 minute 10 seconds within the 15-minute limit. Read the spoken text; cues and sources are for preparation. Presenter assignments can be adjusted by the team.\n\n' + records.map(record => `## ${record.index}. ${record.title}\n\n${record.note}`).join('\n\n'));
await fs.writeFile(path.join(BUILD, 'deck-content.json'), JSON.stringify(records, null, 2));
console.log(JSON.stringify({ output: OUTPUT, slides: records.length, speakingSeconds: 830, nativeCharts: [5, 7, 8], validation: report }));
