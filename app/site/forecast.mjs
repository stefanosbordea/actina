(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const text = (id, value) => { $(id).textContent = value; };
  const percent = value => value === null ? '—' : `${(100 * value).toFixed(2)}%`;
  const labels = {raw_v2: 'Supplied weather, day 1', ecmwf_day2: 'ECMWF, day 2'};
  const hourLabel = hour => `${String(hour).padStart(2, '0')}:00`;
  $('forecast-reload').addEventListener('click', () => window.location.reload());
  try {
    const data = window.AKTINA_FORECAST;
    if (!data || data.schema !== 2 || data.coverage.hours !== 3566 || data.days.length !== 150 || data.metrics.length !== 8) throw Error('Incomplete validation data');
    const allRows = data.days.flatMap(day => day.rows);
    const expectedMethods = ['v2_600', 'v2_562', 'v1', 'persistence', 'raw_v2', 'ecmwf_day2', 'event_008', 'event_019'];
    if (allRows.length !== data.coverage.hours || new Set(allRows.map(row => row.time)).size !== 3566 ||
        data.metrics.some((metric, index) => metric.id !== expectedMethods[index] || metric.hours !== 3566 || metric.tp + metric.fp + metric.fn + metric.tn !== 3566) ||
        data.days.some(day => !day.rows.length || day.rows.some((row, index) => row.time.slice(0, 10) !== day.date || row.hour < 0 || row.hour > 23 || (index > 0 && row.hour !== day.rows[index - 1].hour + 1))) ||
        allRows.some(row => ['actual', 'v2', 'v2_refit', 'raw_v2', 'ecmwf_day2', 'v1', 'persistence', 'nwp_cloud'].some(key => !Number.isFinite(row[key])) || row.nwp_cloud < 0 || row.nwp_cloud > 100 || ![0, 1].includes(row.event_008) || ![0, 1].includes(row.event_019))) throw Error('Invalid validation rows');
    const days = data.days;
    let dayIndex = Math.max(0, days.findLastIndex(day => day.rows.length === 24));
    let hour = 12;
    let weather = 'raw_v2';
    let method = 'event_019';
    let geometry;
    const eventCall = row => method === 'event_008' || method === 'event_019' ? Boolean(row[method]) : row.v2 > (method === 'v2_562' ? 562 : 600);
    const curveKey = () => method === 'v2_600' || method === 'v2_562' ? 'v2' : 'v2_refit';
    const curveLabel = () => method === 'event_008' ? 'V2 refit (reference)' : curveKey() === 'v2' ? 'Original v2' : 'V2 refit';
    const selection = () => days[dayIndex].rows.find(row => row.hour === hour);
    const methodNotes = {
      event_019: '4 fewer false alarms than 008, 1 extra missed hour. Prototype validation.',
      v2_600: 'Original v2 event rule. The forecast must exceed 600 W/m².',
      v2_562: 'Threshold selected on these validation hours. More events found, with more false calls. The radiation curve is unchanged.',
      event_008: 'Separate research comparator. V2 refit is shown as a reference curve. The 008 rule was selected on validation.'
    };
    $('forecast-date').min = days[0].date;
    $('forecast-date').max = days.at(-1).date;
    text('score-hours', data.coverage.hours.toLocaleString('en-GB'));
    text('forecast-coverage', `${data.coverage.hours.toLocaleString('en-GB')} target hours across ${data.coverage.days} dates, from ${data.coverage.first.slice(0, 16)} to ${data.coverage.last.slice(0, 16)}. The first date has 5 hours and the last has 9. All are retained in the scores.`);
    $('forecast-source-link').href = `https://github.com/stefanosbordea/actina/tree/${data.source.commit}`;
    data.source.files.forEach(source => {
      const term = document.createElement('dt');
      const value = document.createElement('dd');
      term.textContent = source.path;
      value.textContent = source.sha256;
      $('forecast-source-hashes').append(term, value);
    });
    data.metrics.forEach(metric => {
      const row = document.createElement('tr');
      row.dataset.method = metric.id;
      const name = document.createElement('td');
      name.append(document.createTextNode(metric.label));
      const note = document.createElement('small');
      note.textContent = metric.note;
      name.append(note);
      row.append(name);
      [percent(metric.precision), percent(metric.recall), percent(metric.f1), metric.tp, metric.fp, metric.fn, metric.tn].forEach(value => {
        const cell = document.createElement('td');
        cell.textContent = value;
        row.append(cell);
      });
      $('forecast-metrics').append(row);
    });

    function renderPlot() {
      const rows = days[dayIndex].rows;
      const curve = curveKey();
      const width = Math.max(280, Math.round($('forecast-plot').getBoundingClientRect().width || 960));
      const height = width < 600 ? 248 : 330;
      const left = width < 600 ? 36 : 46;
      const right = width - 14;
      const top = 18;
      const bottom = height - 27;
      const values = rows.flatMap(row => [row.actual, row[curve], row[weather]]);
      const floor = Math.min(0, Math.floor(Math.min(...values) / 100) * 100);
      const ceiling = Math.max(800, Math.ceil(Math.max(...values) / 200) * 200);
      const x = value => left + (right - left) * value / 23;
      const y = value => bottom - (bottom - top) * (value - floor) / (ceiling - floor);
      geometry = {left, right, width};
      const path = key => rows.map((row, index) => `${index ? 'L' : 'M'}${x(row.hour).toFixed(2)},${y(row[key]).toFixed(2)}`).join(' ');
      const svg = [];
      for (let value = 0; value <= ceiling; value += 200) {
        svg.push(`<line class="forecast-grid" x1="${left}" y1="${y(value)}" x2="${right}" y2="${y(value)}"/><text x="${left - 9}" y="${y(value) + 4}" text-anchor="end">${value}</text>`);
      }
      [0, 6, 12, 18, 23].forEach(value => svg.push(`<text x="${x(value)}" y="${height - 5}" text-anchor="${value === 0 ? 'start' : value === 23 ? 'end' : 'middle'}">${String(value).padStart(2, '0')}</text>`));
      svg.push(`<line class="forecast-threshold" x1="${left}" y1="${y(600)}" x2="${right}" y2="${y(600)}"/>`);
      svg.push(`<path class="forecast-line line-weather" data-curve="${weather}" d="${path(weather)}"/><path class="forecast-line line-v2" data-curve="${curve}" d="${path(curve)}"/><path class="forecast-line line-actual" data-curve="actual" d="${path('actual')}"/>`);
      const row = selection();
      svg.push(`<line class="forecast-cursor" x1="${x(hour)}" x2="${x(hour)}" y1="${top}" y2="${bottom}"/>`);
      [['actual', 'actual'], [curve, 'v2'], [weather, 'weather']].forEach(([key, name]) => svg.push(`<circle class="forecast-point ${name}" cx="${x(hour)}" cy="${y(row[key])}" r="3.5"/>`));
      $('forecast-plot').innerHTML = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="forecast-chart-title forecast-chart-description"><title id="forecast-chart-title">Solar radiation on ${days[dayIndex].date}</title><desc id="forecast-chart-description">Actual weather, ${curveLabel()} and ${labels[weather]}. ${rows.length} retained target hours. Use the inspect time slider for exact values.</desc>${svg.join('')}</svg>`;
    }

    function renderEvents() {
      const rows = days[dayIndex].rows;
      [['actual-events', row => row.actual > 600], ['predicted-events', eventCall]].forEach(([id, call]) => {
        const strip = $(id);
        strip.replaceChildren();
        for (let current = 0; current < 24; current++) {
          const row = rows.find(item => item.hour === current);
          const cell = document.createElement('span');
          cell.className = 'event-hour';
          cell.dataset.missing = String(!row);
          cell.dataset.positive = String(Boolean(row && call(row)));
          cell.dataset.selected = String(current === hour);
          cell.setAttribute('aria-hidden', 'true');
          cell.title = `${hourLabel(current)} ${!row ? 'outside validation' : call(row) ? 'high solar' : 'below event threshold'}`;
          strip.append(cell);
        }
        strip.setAttribute('aria-label', `${id === 'actual-events' ? 'Actual' : 'Predicted'} high-solar times: ${rows.filter(call).map(row => hourLabel(row.hour)).join(', ') || 'none'}. Unavailable hours are dashed.`);
      });
      const row = selection();
      text('event-reading', `${hourLabel(hour)}   Actual: ${row.actual > 600 ? 'high solar' : 'below event threshold'}. Predicted: ${eventCall(row) ? 'high solar' : 'below event threshold'}. White blocks mark high-solar hours.`);
      text('event-method-note', methodNotes[method]);
      const metric = data.metrics.find(item => item.id === method);
      text('score-precision', percent(metric.precision));
      text('score-recall', percent(metric.recall));
      text('score-f1', percent(metric.f1));
      document.querySelectorAll('#forecast-metrics tr').forEach(item => item.setAttribute('aria-current', String(item.dataset.method === method)));
    }

    function render() {
      const day = days[dayIndex];
      hour = Math.max(day.rows[0].hour, Math.min(day.rows.at(-1).hour, hour));
      $('forecast-date').value = day.date;
      $('forecast-previous').disabled = dayIndex === 0;
      $('forecast-next').disabled = dayIndex === days.length - 1;
      $('forecast-hour').min = day.rows[0].hour;
      $('forecast-hour').max = day.rows.at(-1).hour;
      $('forecast-hour').value = hour;
      $('forecast-hour').setAttribute('aria-valuetext', `${hourLabel(hour)}, source clock UTC+03`);
      text('forecast-hour-label', hourLabel(hour));
      text('forecast-day-coverage', `${day.rows.length} hours, fixed UTC+03`);
      text('weather-legend', labels[weather]);
      text('reading-weather-label', labels[weather]);
      text('model-legend', curveLabel());
      text('reading-v2-label', curveLabel());
      const row = selection();
      text('reading-cloud', `${row.nwp_cloud.toFixed(0)}%`);
      [['reading-actual', 'actual'], ['reading-v2', curveKey()], ['reading-weather', weather]].forEach(([id, key]) => {
        $(id).replaceChildren(document.createTextNode(row[key].toFixed(1)));
        const unit = document.createElement('small');
        unit.textContent = 'W/m²';
        $(id).append(unit);
      });
      renderPlot();
      renderEvents();
    }
    function changeDay(index) {
      if (index < 0 || index >= days.length) return;
      dayIndex = index;
      $('forecast-date-error').hidden = true;
      render();
    }
    $('forecast-previous').addEventListener('click', () => changeDay(dayIndex - 1));
    $('forecast-next').addEventListener('click', () => changeDay(dayIndex + 1));
    $('forecast-date').addEventListener('change', event => {
      const index = days.findIndex(day => day.date === event.target.value);
      if (index < 0) {
        text('forecast-date-error', 'Choose a date between 5 December 2025 and 3 May 2026.');
        $('forecast-date-error').hidden = false;
        $('forecast-date').value = days[dayIndex].date;
        return;
      }
      changeDay(index);
    });
    $('forecast-source').addEventListener('change', event => {
      if (!Object.hasOwn(labels, event.target.value)) return;
      weather = event.target.value;
      render();
    });
    $('event-method').addEventListener('change', event => {
      if (!Object.hasOwn(methodNotes, event.target.value)) return;
      method = event.target.value;
      render();
    });
    $('forecast-hour').addEventListener('input', event => { hour = Number(event.target.value); render(); });
    $('forecast-plot').addEventListener('pointerdown', event => {
      const box = $('forecast-plot').getBoundingClientRect();
      if (!box.width) return;
      const location = (event.clientX - box.left) * geometry.width / box.width;
      hour = Math.round(23 * (location - geometry.left) / (geometry.right - geometry.left));
      render();
    });
    $('forecast-loading').hidden = true;
    $('forecast-view').hidden = false;
    document.body.dataset.state = 'ready';
    render();
    if (typeof ResizeObserver === 'function') new ResizeObserver(renderPlot).observe($('forecast-plot'));
    else window.addEventListener('resize', renderPlot);
  } catch (error) {
    $('forecast-loading').hidden = true;
    $('forecast-view').hidden = true;
    $('forecast-error').hidden = false;
    document.body.dataset.state = 'error';
    console.error('Forecast viewer:', error.message);
  }
})();
