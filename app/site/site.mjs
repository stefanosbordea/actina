const $ = (id) => document.getElementById(id);
const number = (value, digits = 0) => new Intl.NumberFormat('en-GB', { maximumFractionDigits: digits }).format(value);
const money = (value) => new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'EUR' }).format(value);
const dates = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const dateLabel = (value) => dates.format(new Date(`${value}T12:00:00Z`));
const hourLabel = (hour) => `${String(hour).padStart(2, '0')}:00–${String(hour + 1).padStart(2, '0')}:00`;
const fields = ['actual', 'model_forecast', 'forecast', 'demand', 'flat', 'aktina', 'tank'];
let data, dayIndex = 0, hour = 12;
let layouts = [];

function validate(input) {
  if (!input || !Array.isArray(input.days) || !input.days.length) throw new Error('The schedule data is missing. Restore data.js beside this page and reload.');
  for (const key of ['capacity', 'reserve', 'energy', 'threshold', 'normal_price', 'surplus_price']) {
    if (!Number.isFinite(input.assumptions?.[key]) || input.assumptions[key] < 0) throw new Error('The schedule assumptions could not be read. Restore the original data file.');
  }
  if (input.assumptions.capacity <= input.assumptions.reserve) throw new Error('The declared tank capacity must exceed its reserve.');
  const seen = new Set();
  for (const day of input.days) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(day.date) || seen.has(day.date) || !Number.isFinite(day.start_tank) || day.rows?.length !== 24) throw new Error('The schedule contains an incomplete or repeated day. Restore the original data file.');
    seen.add(day.date);
    day.rows.forEach((row, index) => {
      if (typeof row.time !== 'string' || row.time.slice(0, 10) !== day.date || Number(row.time.slice(11, 13)) !== index || [...fields, 'baseline'].some((key) => !Number.isFinite(row[key]))) throw new Error('An hourly value is missing or invalid. Restore the original data file.');
    });
  }
  return input;
}

function sourceDetails() {
  const a = data.assumptions;
  const forecastStatus = data.source?.schedule_forecast_status;
  $('schedule-status').textContent = forecastStatus === 'matches_persistence'
    ? 'Schedule forecast matches yesterday’s weather; model-to-plan connection awaiting confirmation.'
    : forecastStatus === 'matches_model'
      ? 'The supplied plan’s forecast matches the LightGBM output.'
      : 'The supplied plan’s forecast source is awaiting confirmation.';
  $('forecast-provenance').textContent = forecastStatus === 'matches_persistence'
    ? 'The sun chart shows the LightGBM predictions. The supplied schedule’s forecast column matches yesterday’s radiation. This does not establish which forecast generated the plan. Production, tank levels and costs are shown unchanged; the model-to-plan connection is awaiting confirmation.'
    : forecastStatus === 'matches_model'
      ? 'The supplied schedule’s forecast column matches the LightGBM predictions. Production and tank levels are shown unchanged from the supplied schedule.'
      : 'The sun chart shows the LightGBM predictions. The supplied schedule’s forecast column has not been confirmed to match those predictions. Production and tank levels are shown unchanged.';
  $('assumptions').innerHTML = [
    ['Tank capacity', `${number(a.capacity)} m³`], ['Minimum tank level', `${number(a.reserve)} m³`],
    ['Plant electricity', `${number(a.energy, 2)} kWh/m³`], ['Lower-price condition', `Actual radiation > ${number(a.threshold)} W/m²`],
    ['Electricity price, lower / normal', `€${number(a.surplus_price)} / €${number(a.normal_price)} per MWh`],
  ].map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join('');
  $('source-commit').textContent = data.source?.commit || 'Not supplied';
  $('source-hash').textContent = data.source?.csv_sha256 || 'Not supplied';
  if (data.source?.repository) {
    const repository = String(data.source.repository);
    const url = new URL(repository.startsWith('https://') ? repository : `https://github.com/${repository}`);
    if (url.protocol === 'https:' && url.hostname === 'github.com') {
      $('source-repository').href = url.href;
      $('source-repository').textContent = url.pathname.replace(/^\//, '');
    }
  }
}

function renderDay() {
  const day = data.days[dayIndex], rows = day.rows, a = data.assumptions;
  $('day').value = day.date;
  $('previous-day').disabled = dayIndex === 0;
  $('next-day').disabled = dayIndex === data.days.length - 1;
  $('date-error').hidden = true;
  $('day-description').textContent = `${dateLabel(day.date)}. LightGBM forecast and supplied schedule.`;
  document.querySelectorAll('[data-date]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.date === day.date));
    button.disabled = !data.days.some((candidate) => candidate.date === button.dataset.date);
  });
  const sum = (field) => rows.reduce((total, row) => total + row[field], 0);
  const cost = (field) => rows.reduce((total, row) => total + row[field] * a.energy / 1000 * (row.actual > a.threshold ? a.surplus_price : a.normal_price), 0);
  const displayDifference = (value) => Math.abs(value) < 1e-7 ? 0 : value;
  const flatCost = cost('flat'), aktinaCost = cost('aktina'), difference = displayDifference(flatCost - aktinaCost);
  const flatWater = sum('flat'), aktinaWater = sum('aktina'), ending = rows.at(-1).tank;
  const productionDifference = displayDifference(aktinaWater - flatWater), tankChange = displayDifference(ending - day.start_tank);
  $('flat-cost').textContent = money(flatCost);
  $('aktina-cost').textContent = money(aktinaCost);
  $('difference-label').textContent = difference > 0 ? 'Lower daily cost' : difference < 0 ? 'Higher daily cost' : 'Cost difference';
  $('cost-difference').textContent = money(Math.abs(difference));
  $('cost-percent').textContent = flatCost > 0 ? `${number(Math.abs(difference / flatCost * 100), 1)}%` : 'No flat cost baseline';
  const surplus = rows.filter((row) => row.actual > a.threshold).length;
  $('surplus-summary').textContent = `${surplus} ${surplus === 1 ? 'hour' : 'hours'} above ${number(a.threshold)} W/m²`;
  const error = (field) => rows.reduce((total, row) => total + Math.abs(row[field] - row.actual), 0) / rows.length;
  $('forecast-error').textContent = `Average absolute error over 24 hours: LightGBM ${number(error('model_forecast'))} W/m²; yesterday’s weather ${number(error('baseline'))} W/m².`;
  const changeText = (value) => `${value > 0 ? '+' : ''}${number(value, 1)} m³`;
  $('comparison-note').textContent = productionDifference === 0 && tankChange === 0
    ? 'Same water production and ending storage.'
    : `Production difference ${changeText(productionDifference)}. Change in stored water ${changeText(tankChange)}. Read these alongside the daily cost difference.`;
  $('water-demand').textContent = `${number(sum('demand'), 1)} m³`;
  $('water-production').textContent = `${number(flatWater, 1)} / ${number(aktinaWater, 1)} m³`;
  $('water-storage').textContent = `${number(day.start_tank, 1)} / ${number(ending, 1)} m³`;
  $('table-date').textContent = dateLabel(day.date);
  $('hourly-rows').innerHTML = rows.map((row, index) => `<tr data-hour="${index}"><td>${String(index).padStart(2, '0')}:00</td>${fields.map((field) => `<td>${number(row[field], 2)}</td>`).join('')}</tr>`).join('');
  drawCharts();
}

function drawCharts() {
  if (!data || $('day-review').hidden) return;
  const day = data.days[dayIndex], rows = day.rows, a = data.assumptions;
  layouts = [];
  const charts = [
    { id: 'sun-chart', type: 'sun', max: Math.max(1200, ...rows.flatMap((row) => [row.actual, row.model_forecast])), min: Math.min(0, ...rows.flatMap((row) => [row.actual, row.model_forecast])), ticks: [0, a.threshold, 1200], label: 'Actual and LightGBM forecast solar radiation in watts per square metre. Shaded hours have actual radiation above the lower-price threshold.' },
    { id: 'production-chart', type: 'production', max: Math.max(450, ...rows.flatMap((row) => [row.flat, row.aktina])) * 1.08, min: 0, ticks: [0, 200, 400], label: 'Hourly water production in cubic metres: flat plan and Aktina schedule.' },
    { id: 'tank-chart', type: 'tank', max: Math.max(a.capacity, day.start_tank, ...rows.map((row) => row.tank)) * 1.09, min: Math.min(0, day.start_tank, ...rows.map((row) => row.tank)), ticks: [0, a.reserve, a.capacity], label: 'Stored water in cubic metres at each hour’s end, with the minimum and capacity marked.' },
  ];
  for (const chart of charts) {
    const element = $(chart.id), width = Math.max(240, element.getBoundingClientRect().width || 700);
    const mobile = width < 500, height = mobile ? 168 : 190;
    const left = mobile ? 38 : 48, right = 10, top = 16, bottom = 27;
    const plotWidth = width - left - right, plotHeight = height - top - bottom;
    const x = (value) => left + value / 24 * plotWidth;
    const y = (value) => top + (chart.max - value) / (chart.max - chart.min) * plotHeight;
    const line = (values) => values.map(([t, value], index) => `${index ? 'L' : 'M'}${x(t).toFixed(2)},${y(value).toFixed(2)}`).join(' ');
    let content = chart.ticks.map((value) => `<line class="grid" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text x="${left - 8}" y="${y(value) + 4}" text-anchor="end">${number(value)}</text>`).join('');
    content += [0, 6, 12, 18, 24].map((value) => `<text x="${x(value)}" y="${height - 6}" text-anchor="${value === 0 ? 'start' : value === 24 ? 'end' : 'middle'}">${String(value).padStart(2, '0')}:00</text>`).join('');
    content += `<rect class="hour-highlight" y="${top}" width="${plotWidth / 24}" height="${plotHeight}"/>`;
    if (chart.type === 'sun') {
      content += rows.map((row, index) => row.actual > a.threshold ? `<rect class="surplus-fill" x="${x(index)}" y="${top}" width="${plotWidth / 24}" height="${plotHeight}"/>` : '').join('');
      const actual = rows.map((row, index) => [index + .5, row.actual]);
      content += `<path class="solar-fill" d="${line(actual)} L${x(23.5)},${y(0)} L${x(.5)},${y(0)} Z"/>`;
      content += `<path class="actual-line" d="${line(actual)}"/><path class="forecast-line" d="${line(rows.map((row, index) => [index + .5, row.model_forecast]))}"/>`;
      content += `<line class="threshold" x1="${left}" x2="${width - right}" y1="${y(a.threshold)}" y2="${y(a.threshold)}"/><text class="threshold-label" x="${width - right}" y="${y(a.threshold) - 7}" text-anchor="end">Lower-price threshold</text>`;
    } else if (chart.type === 'production') {
      const barWidth = plotWidth / 24 * .34, gap = plotWidth / 24 * .05;
      content += rows.map((row, index) => `<rect class="flat-bar" x="${x(index + .5) - gap - barWidth}" y="${y(row.flat)}" width="${barWidth}" height="${y(0) - y(row.flat)}"/><rect class="aktina-bar" x="${x(index + .5) + gap}" y="${y(row.aktina)}" width="${barWidth}" height="${y(0) - y(row.aktina)}"/>`).join('');
    } else {
      const values = [[0, day.start_tank], ...rows.map((row, index) => [index + 1, row.tank])];
      content += `<path class="tank-fill" d="${line(values)} L${x(24)},${y(0)} L${x(0)},${y(0)} Z"/><path class="tank-line" d="${line(values)}"/>`;
      content += [[a.reserve, 'Minimum'], [a.capacity, 'Capacity']].map(([value, label]) => `<line class="threshold" x1="${left}" x2="${width - right}" y1="${y(value)}" y2="${y(value)}"/><text class="threshold-label" x="${width - right}" y="${y(value) - 7}" text-anchor="end">${label}</text>`).join('');
      content += '<circle class="selected-dot" r="4"/>';
    }
    content += `<line class="crosshair" y1="${top}" y2="${height - bottom}"/><rect class="hit-area" x="${left}" y="${top}" width="${plotWidth}" height="${plotHeight}"/>`;
    element.innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${chart.label}"><title>${chart.label}</title>${content}</svg>`;
    const inspect = (event) => {
      const bounds = element.getBoundingClientRect();
      const time = ((event.clientX - bounds.left) / bounds.width * width - left) / plotWidth * 24;
      const value = chart.type === 'tank' ? Math.round(time) - 1 : Math.floor(time);
      setHour(Math.max(0, Math.min(23, value)));
    };
    element.querySelector('.hit-area').addEventListener('pointermove', (event) => { if (event.pointerType !== 'touch') inspect(event); });
    element.querySelector('.hit-area').addEventListener('click', inspect);
    layouts.push({ element, chart, x, y });
  }
  setHour(hour);
}

function setHour(value) {
  hour = value;
  $('hour').value = String(hour);
  $('hour-label').textContent = hourLabel(hour);
  $('hour').setAttribute('aria-valuetext', hourLabel(hour));
  const row = data.days[dayIndex].rows[hour];
  $('sun-reading').innerHTML = `${number(row.actual, 1)} W/m²<span>Forecast ${number(row.model_forecast, 1)}</span>`;
  $('production-reading').innerHTML = `${number(row.aktina, 1)} m³<span>Flat ${number(row.flat, 1)}</span>`;
  $('tank-reading').innerHTML = `${number(row.tank, 1)} m³<span>At ${String(hour + 1).padStart(2, '0')}:00</span>`;
  for (const { element, chart, x, y } of layouts) {
    const cursor = x(chart.type === 'tank' ? hour + 1 : hour + .5);
    const crosshair = element.querySelector('.crosshair');
    crosshair.setAttribute('x1', cursor);
    crosshair.setAttribute('x2', cursor);
    element.querySelector('.hour-highlight').setAttribute('x', x(hour));
    const dot = element.querySelector('.selected-dot');
    if (dot) { dot.setAttribute('cx', cursor); dot.setAttribute('cy', y(row.tank)); }
  }
  document.querySelectorAll('#hourly-rows tr').forEach((row, index) => { row.dataset.active = String(index === hour); });
}

function chooseDay(date) {
  const index = data.days.findIndex((day) => day.date === date);
  if (index < 0) {
    $('date-error').textContent = 'There is no complete schedule for this day. Choose another date or use the previous and next buttons.';
    $('date-error').hidden = false;
    $('day').value = data.days[dayIndex].date;
    return;
  }
  dayIndex = index;
  renderDay();
}

$('reload').addEventListener('click', () => location.reload());
try {
  data = validate(window.AKTINA_DATA);
  const initial = data.days.findIndex((day) => day.date === '2026-07-03');
  dayIndex = initial < 0 ? 0 : initial;
  $('day').min = data.days[0].date;
  $('day').max = data.days.at(-1).date;
  $('day').addEventListener('change', (event) => chooseDay(event.target.value));
  $('previous-day').addEventListener('click', () => { if (dayIndex > 0) chooseDay(data.days[dayIndex - 1].date); });
  $('next-day').addEventListener('click', () => { if (dayIndex < data.days.length - 1) chooseDay(data.days[dayIndex + 1].date); });
  document.querySelectorAll('[data-date]').forEach((button) => button.addEventListener('click', () => chooseDay(button.dataset.date)));
  $('hour').addEventListener('input', (event) => setHour(Number(event.target.value)));
  document.querySelector('a[href="#about"]').addEventListener('click', () => { $('about').open = true; });
  const revealAbout = () => {
    if (location.hash === '#about') {
      $('about').open = true;
      $('about').scrollIntoView({ block: 'start' });
    }
  };
  window.addEventListener('hashchange', revealAbout);
  sourceDetails();
  $('day-review').hidden = false;
  renderDay();
  $('boot').hidden = true;
  document.body.dataset.state = 'ready';
  revealAbout();
  let resizeFrame;
  const resize = new ResizeObserver(() => { cancelAnimationFrame(resizeFrame); resizeFrame = requestAnimationFrame(drawCharts); });
  resize.observe($('sun-chart'));
} catch (error) {
  $('boot').hidden = true;
  $('day-review').hidden = true;
  $('load-error').hidden = false;
  $('error-message').textContent = error.message;
  document.body.dataset.state = 'error';
}
