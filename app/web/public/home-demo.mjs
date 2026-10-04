import {replayPlan} from './plan-resilience.mjs';
import {homeReference} from './home-reference.mjs';

export const demoScenarios = {
 original: {},
 demand: {demand_multiplier: 1.1},
 outage: {outage: {start_hour: 12, duration_hours: 2}}
};
export function replayDemo(name) {
 if (!Object.hasOwn(demoScenarios, name)) throw Error('Unknown reference scenario.');
 return replayPlan({...homeReference.input, scenario: demoScenarios[name]});
}

export function setupHomeDemo({document, onOpen}) {
 const $ = id => document.getElementById(id), window = document.defaultView;
 const format = value => value.toLocaleString('en-GB', {maximumFractionDigits: 1});
 const original = replayDemo('original'), inventory = result => [result.totals.initial_storage_m3, ...result.rows.map(row => row.storage_end_m3)];
 let selected = 'original', current = original, width = 0;
 const chart = $('home-demo-chart'), inputs = [...document.querySelectorAll('[name="home-demo-case"]')];
 const menu = $('home-menu');
 const motionPreference = window.matchMedia?.('(prefers-reduced-motion: reduce)');
 const diagram = $('home-flow-diagram'), motionToggle = $('home-flow-toggle');
 const motionKey = 'aktina.diagram-motion';
 let motionChoice = null;
 try {
  const saved = window.localStorage.getItem(motionKey);
  if (saved === 'play' || saved === 'pause') motionChoice = saved;
 } catch { /* Playback still works when storage is unavailable. */ }
 function updateMotion() {
  const paused = motionChoice === 'pause' || (motionChoice === null && (motionPreference?.matches ?? false));
  const source = `solar-water.svg${paused ? '#still' : motionChoice === 'play' ? '#play' : ''}`;
  if (diagram.getAttribute('src') !== source) diagram.setAttribute('src', source);
  motionToggle.hidden = false;
  motionToggle.setAttribute('aria-label', paused ? 'Play diagram animation' : 'Pause diagram animation');
  motionToggle.title = motionToggle.getAttribute('aria-label');
  motionToggle.querySelector('path').setAttribute('d', paused ? 'm7 4 9 6-9 6Z' : 'M7 5v10M13 5v10');
 }
 motionToggle.addEventListener('click', () => {
  motionChoice = diagram.getAttribute('src').endsWith('#still') ? 'play' : 'pause';
  try { window.localStorage.setItem(motionKey, motionChoice); } catch { /* Keep the choice for this visit. */ }
  updateMotion();
 });
 motionPreference?.addEventListener('change', updateMotion);
 window.addEventListener('pageshow', updateMotion);
 updateMotion();
 menu.addEventListener('click', event => { if (event.target.closest('a')) menu.open = false; });
 document.addEventListener('keydown', event => { if (event.key === 'Escape' && menu.open) { event.preventDefault(); menu.open = false; menu.querySelector('summary').focus(); } });
 function draw() {
  const measured = chart.getBoundingClientRect().width;
  if (measured > 0) width = measured;
  const W = width || 680, H = 230, L = 48, R = 12, T = 18, B = 30;
  const x = h => L + (W - L - R) * h / 24, y = value => T + (H - T - B) * (1 - value / homeReference.input.capacity);
  const points = result => inventory(result).map((value, hour) => `${x(hour)},${y(value)}`).join(' ');
  chart.innerHTML = `<svg viewBox="0 0 ${W} ${H}" aria-hidden="true"><g class="home-demo-grid">${[0, 2000, 4000].map(value => `<line x1="${L}" x2="${W-R}" y1="${y(value)}" y2="${y(value)}"/><text x="${L-9}" y="${y(value)+4}" text-anchor="end">${format(value)}</text>`).join('')}${[0, 6, 12, 18, 24].map(hour => `<text x="${x(hour)}" y="${H-6}" text-anchor="${hour === 0 ? 'start' : hour === 24 ? 'end' : 'middle'}">${String(hour).padStart(2,'0')}:00</text>`).join('')}</g><path class="home-demo-reserve-line" d="M${L} ${y(800)}H${W-R}"/><polyline class="home-demo-reference-line" points="${points(original)}"/><polyline class="home-demo-water-line" points="${points(current)}"/></svg>`;
 }
 function render() {
  current = replayDemo(selected);
  const t = current.totals, deficit = t.max_reserve_deficit_m3;
  $('home-demo-outcome').textContent = t.unmet_m3 > 0 ? 'Water demand unmet' : deficit > 0 ? 'Reserve breached' : 'Reserve holds';
  $('home-demo-minimum').textContent = `${format(t.min_storage_m3)} m³`;
  $('home-demo-detail').textContent = selected === 'original' ? 'Demand and end-of-day target met.' : `${selected === 'outage' ? 'Outage 12:00–14:00. ' : ''}${format(deficit)} m³ below reserve. ${format(t.terminal_deficit_m3)} m³ below the end-of-day target.`;
  $('home-demo').dataset.finding = String(deficit > 0 || t.unmet_m3 > 0);
  chart.setAttribute('aria-label', `${$('home-demo-outcome').textContent}. Lowest inventory ${format(t.min_storage_m3)} cubic metres. Reserve 800 cubic metres. Hourly values are available below.`);
  const baseline = inventory(original);
  $('home-demo-values').innerHTML = inventory(current).map((value,hour) => `<tr><th scope="row">${String(hour).padStart(2,'0')}:00</th><td>${format(baseline[hour])}</td><td>${format(value)}</td></tr>`).join('');
  draw();
 }
 $('home-demo-source').textContent = `Source: ${homeReference.source.file}, ${homeReference.source.path}. SHA-256 ${homeReference.source.sha256}.`;
 for (const input of inputs) input.addEventListener('change', () => { if (input.checked) { selected = input.value; render(); } });
 $('home-demo-open').addEventListener('click', async () => {
  const button = $('home-demo-open'); button.disabled = true; $('home-demo-error').hidden = true; menu.open = false;
  try { await onOpen(selected); }
  catch { $('home-demo-error').textContent = 'The full review could not open. Return here and try again.'; $('home-demo-error').hidden = false; }
  finally { button.disabled = false; }
 });
 render();
 if (window.ResizeObserver) new window.ResizeObserver(entries => { const next = entries[0].contentRect.width; if (next > 0 && Math.abs(next-width) > .5) draw(); }).observe(chart);
 else window.addEventListener('resize', draw);
 return {render};
}
