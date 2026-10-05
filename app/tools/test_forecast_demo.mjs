import {strict as assert} from 'node:assert';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {JSDOM} from '../web/node_modules/jsdom/lib/api.js';
const read = name => readFileSync(new URL('../site/' + name, import.meta.url), 'utf8');
function boot(change) {
  const dom = new JSDOM(read('forecast.html'), {url: 'http://localhost/forecast.html', runScripts: 'outside-only', pretendToBeVisual: true});
  dom.window.eval(read('forecast-data.js'));
  if (change) change(dom.window.AKTINA_FORECAST);
  dom.window.eval(read('forecast.mjs'));
  return dom;
}
function withPage(fn) {
  const dom = boot();
  try { fn(dom.window.document, dom.window); } finally { dom.window.close(); }
}
function change(d, w, id, value, type = 'change') {
  d.getElementById(id).value = value;
  d.getElementById(id).dispatchEvent(new w.Event(type));
}
test('019 is the default, with its matching refit curve and all validation scores', () => withPage((d, w) => {
  assert.equal(d.body.dataset.state, 'ready');
  assert.equal(d.getElementById('forecast-view').hidden, false);
  assert.equal(d.getElementById('event-method').value, 'event_019');
  assert.equal(d.getElementById('forecast-source').value, 'raw_v2');
  assert.equal(d.getElementById('forecast-date').value, '2026-05-02');
  assert.equal(d.getElementById('score-f1').textContent, '91.06%');
  assert.equal(d.getElementById('score-precision').textContent, '94.08%');
  assert.equal(d.getElementById('score-recall').textContent, '88.24%');
  assert.equal(d.querySelectorAll('[data-curve]').length, 3);
  assert.equal(d.querySelectorAll('#forecast-metrics tr').length, 8);
  assert.equal(d.querySelector('#forecast-metrics tr[aria-current=true]').dataset.method, 'event_019');
  assert.equal(d.querySelectorAll('[data-curve=v2_refit]').length, 1);
  assert.equal(d.querySelectorAll('[data-curve=v2]').length, 0);
  assert.equal(d.getElementById('model-legend').textContent, 'Forecast');
  assert.match(d.getElementById('event-method-note').textContent, /4 fewer false alarms than the research comparison, 1 extra missed hour/);
  const day = w.AKTINA_FORECAST.days.find(item => item.date === d.getElementById('forecast-date').value);
  assert.equal(d.querySelectorAll('#predicted-events [data-positive=true]').length, day.rows.filter(row => row.event_019).length);
  assert.equal(d.getElementById('forecast-provenance').open, false);
  assert.match(d.getElementById('forecast-coverage').textContent, /3,566/);
  assert.match(d.getElementById('forecast-provenance').textContent, /does not establish superiority on new data/);
}));
test('the tuned threshold changes only event calls and global scores, not a curve', () => withPage((d, w) => {
  const refit = d.querySelector('[data-curve=v2_refit]').getAttribute('d');
  change(d, w, 'event-method', 'v2_600');
  const curve = d.querySelector('[data-curve=v2]').getAttribute('d');
  assert.notEqual(curve, refit);
  assert.equal(d.getElementById('model-legend').textContent, 'Original forecast');
  assert.equal(d.getElementById('score-f1').textContent, '88.36%');
  change(d, w, 'event-method', 'v2_562');
  assert.equal(d.getElementById('score-f1').textContent, '89.13%');
  assert.equal(d.getElementById('score-precision').textContent, '84.91%');
  assert.equal(d.getElementById('score-recall').textContent, '93.79%');
  assert.equal(d.querySelector('[data-curve=v2]').getAttribute('d'), curve);
  assert.match(d.getElementById('event-method-note').textContent, /More high-solar hours found, with more false alarms/);
  const day = w.AKTINA_FORECAST.days.find(item => item.date === d.getElementById('forecast-date').value);
  assert.equal(d.querySelectorAll('#predicted-events [data-positive=true]').length, day.rows.filter(row => row.v2 > 562).length);
  change(d, w, 'event-method', 'event_019');
  assert.equal(d.querySelector('[data-curve=v2_refit]').getAttribute('d'), refit);
  assert.equal(d.getElementById('score-f1').textContent, '91.06%');
}));
test('008 stays binary and labels the refit as a reference, even after original v2', () => withPage((d, w) => {
  const curve = d.querySelector('[data-curve=v2_refit]').getAttribute('d');
  change(d, w, 'event-method', 'v2_600');
  change(d, w, 'event-method', 'event_008');
  assert.equal(d.getElementById('score-f1').textContent, '90.64%');
  assert.equal(d.querySelector('[data-curve=v2_refit]').getAttribute('d'), curve);
  assert.equal(d.getElementById('model-legend').textContent, 'Reference forecast');
  assert.equal(d.querySelectorAll('[data-curve=event_008]').length, 0);
  assert.match(d.getElementById('event-method-note').textContent, /Event calls only/);
  const day = w.AKTINA_FORECAST.days.find(item => item.date === d.getElementById('forecast-date').value);
  assert.equal(d.querySelectorAll('#predicted-events [data-positive=true]').length, day.rows.filter(row => row.event_008).length);
}));
test('both partial boundary days retain their actual hours without changing scores', () => withPage((d, w) => {
  change(d, w, 'forecast-date', '2025-12-05');
  assert.equal(d.getElementById('forecast-hour').min, '19');
  assert.equal(d.getElementById('forecast-hour').max, '23');
  assert.equal(d.getElementById('forecast-hour').value, '19');
  assert.equal(d.getElementById('forecast-previous').disabled, true);
  assert.equal(d.querySelectorAll('#actual-events [data-missing=true]').length, 19);
  assert.match(d.getElementById('forecast-day-coverage').textContent, /5 hours/);
  change(d, w, 'forecast-date', '2026-05-03');
  assert.equal(d.getElementById('forecast-hour').min, '0');
  assert.equal(d.getElementById('forecast-hour').max, '8');
  assert.equal(d.getElementById('forecast-next').disabled, true);
  assert.equal(d.querySelectorAll('#actual-events [data-missing=true]').length, 15);
  assert.equal(d.getElementById('score-f1').textContent, '91.06%');
  assert.match(d.getElementById('forecast-day-coverage').textContent, /9 hours/);
}));
test('weather selection and hour inspection display exact joined values including cloud', () => withPage((d, w) => {
  change(d, w, 'forecast-source', 'ecmwf_day2');
  change(d, w, 'forecast-hour', '11', 'input');
  const row = w.AKTINA_FORECAST.days.find(item => item.date === d.getElementById('forecast-date').value).rows.find(item => item.hour === 11);
  assert.equal(d.querySelectorAll('[data-curve=raw_v2]').length, 0);
  assert.equal(d.querySelectorAll('[data-curve=ecmwf_day2]').length, 1);
  assert.equal(d.getElementById('reading-weather').firstChild.textContent, row.ecmwf_day2.toFixed(1));
  assert.equal(d.getElementById('reading-v2').firstChild.textContent, row.v2_refit.toFixed(1));
  assert.equal(d.getElementById('reading-cloud').textContent, `${row.nwp_cloud.toFixed(0)}%`);
  assert.equal(d.getElementById('forecast-hour').getAttribute('aria-valuetext'), '11:00, source clock UTC+03');
  assert.match(d.getElementById('reading-weather-label').textContent, /ECMWF/);
}));
test('invalid dates are rejected and next/previous controls restore the expected day', () => withPage((d, w) => {
  const original = d.getElementById('forecast-date').value;
  change(d, w, 'forecast-date', '2026-08-01');
  assert.equal(d.getElementById('forecast-date').value, original);
  assert.equal(d.getElementById('forecast-date-error').hidden, false);
  d.getElementById('forecast-next').click();
  assert.equal(d.getElementById('forecast-date').value, '2026-05-03');
  assert.equal(d.getElementById('forecast-date-error').hidden, true);
  d.getElementById('forecast-previous').click();
  assert.equal(d.getElementById('forecast-date').value, original);
}));
test('malformed or incomplete data fail closed instead of publishing partial scores', () => {
  for (const damage of [data => data.days.shift(), data => data.days[0].rows[0].nwp_cloud = null, data => data.days[0].rows[0].v2_refit = null, data => data.days[0].rows[0].event_019 = 2, data => data.metrics[0].tp = 999]) {
    const dom = boot(damage);
    try {
      assert.equal(dom.window.document.body.dataset.state, 'error');
      assert.equal(dom.window.document.getElementById('forecast-error').hidden, false);
      assert.equal(dom.window.document.getElementById('forecast-view').hidden, true);
    } finally { dom.window.close(); }
  }
});
test('home links the standalone view without changing the supplied plan entry point', () => {
  const html = read('index.html');
  assert.match(html, /href="\.\/forecast\.html">Forecasts/);
  assert.match(html, /src="\.\/data\.js"/);
  assert.match(html, /src="\.\/site\.mjs"/);
});
test('public labels keep attribution and code handoff details out of every forecast view', () => withPage((d, w) => {
  assert.deepEqual([...d.querySelectorAll('#event-method option')].map(option => option.textContent),
    ['Current forecast', 'Original forecast', 'Higher sensitivity', 'Research comparison']);
  assert.deepEqual([...d.querySelectorAll('#forecast-metrics tr td:first-child')].map(cell => cell.textContent),
    ['Original forecast', 'Higher sensitivity', 'Earlier forecast', 'Previous day', 'Supplied weather, day 1', 'ECMWF, day 2', 'Research comparison', 'Current forecast']);
  for (const method of ['event_019', 'v2_600', 'v2_562', 'event_008']) {
    change(d, w, 'event-method', method);
    assert.doesNotMatch(d.body.textContent, /Stefanos|Loukas|Loucas|GitHub|\.csv|\.py|sha256|logistic|refit|\bv[12]\b|\b008\b|\b019\b/i);
    assert.equal(d.querySelectorAll('a[href*="github.com"], code, #forecast-source-hashes').length, 0);
  }
  assert.match(d.getElementById('forecast-provenance').textContent, /18\.700675 W\/m²/);
  assert.match(d.getElementById('forecast-provenance').textContent, /18\.697343 W\/m²/);
}));
