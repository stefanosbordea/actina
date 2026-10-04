import {strict as assert} from 'node:assert';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {JSDOM} from '../web/node_modules/jsdom/lib/api.js';
const read = name => readFileSync(new URL('../site/' + name, import.meta.url), 'utf8');
function boot({missing=false}={}) {
  const dom = new JSDOM(read('index.html'), {url:'http://localhost/', runScripts:'outside-only', pretendToBeVisual:true});
  dom.window.ResizeObserver=class {observe(){} disconnect(){}};
  if(!missing)dom.window.eval(read('data.js'));
  dom.window.eval(read('site.mjs'));
  return dom;
}
test('demo shows model predictions separately from the supplied plan',()=>{
  const dom=boot(), d=dom.window.document;
  try {
    assert.equal(d.body.dataset.state,'ready');
    assert.match(d.querySelector('.schedule-status').textContent,/matches previous-day/);
    assert.equal(d.getElementById('flat-cost').textContent,'€2,994.59');
    assert.equal(d.getElementById('aktina-cost').textContent,'€2,628.25');
    assert.equal(d.getElementById('comparison-note').textContent,'Same water production and ending storage.');
    d.querySelector('[data-date="2026-03-16"]').click();
    assert.match(d.getElementById('sun-reading').textContent,/Forecast 486.2/);
    assert.match(d.getElementById('forecast-error').textContent,/Forecast 48 W/);
  } finally {dom.window.close();}
});
test('cloudy day has zero price saving and invalid dates preserve the current review',()=>{
  const dom=boot(),d=dom.window.document;
  try {
    d.querySelector('[data-date="2025-12-10"]').click();
    assert.equal(d.getElementById('cost-difference').textContent,'€0.00');
    assert.equal(d.getElementById('cost-percent').textContent,'0%');
    d.getElementById('day').value='2025-01-01';
    d.getElementById('day').dispatchEvent(new dom.window.Event('change'));
    assert.equal(d.getElementById('day').value,'2025-12-10');
    assert.equal(d.getElementById('date-error').hidden,false);
    assert.match(d.getElementById('table-date').textContent,/10 December 2025/);
  } finally {dom.window.close();}
});
test('missing packaged data gives a visible actionable error',()=>{
  const dom=boot({missing:true}),d=dom.window.document;
  try {assert.equal(d.body.dataset.state,'error');assert.equal(d.getElementById('load-error').hidden,false);assert.equal(d.getElementById('day-review').hidden,true);}
  finally {dom.window.close();}
});
test('About link opens the model disclosure',()=>{
  const dom=boot(),d=dom.window.document;
  try {assert.equal(d.getElementById('about').open,false);d.querySelector('a[href="#about"]').click();assert.equal(d.getElementById('about').open,true);}
  finally {dom.window.close();}
});
