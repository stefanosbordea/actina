import {strict as assert} from 'node:assert';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {JSDOM} from '../web/node_modules/jsdom/lib/api.js';
const read = name => readFileSync(new URL('../site/' + name, import.meta.url), 'utf8');
function boot(missing=false) {
  const dom=new JSDOM(read('benchmark.html'),{url:'http://localhost/benchmark.html',runScripts:'outside-only'});
  if(!missing)dom.window.eval(read('benchmark-data.js'));
  dom.window.eval(read('benchmark.mjs'));
  return dom;
}
test('full test is the default and all six experiments remain visible',()=>{
  const dom=boot(),d=dom.window.document;
  try {
    assert.equal(d.getElementById('bench-results').hidden,false);
    assert.match(d.getElementById('verdict').textContent,/Persistence leads/);
    assert.match(d.getElementById('period').textContent,/3,567/);
    assert.match(d.getElementById('metric-comparison').textContent,/96.55%/);
    assert.equal(d.querySelectorAll('#experiment-rows tr').length,6);
    assert.match(d.querySelector('#experiment-rows [data-selected=true]').textContent,/Direct classifier/);
    assert.match(d.getElementById('experiment-rows').textContent,/95.70%/);
  } finally {dom.window.close();}
});
test('changing period updates the comparison, errors and experiment results together',()=>{
  const dom=boot(),d=dom.window.document;
  try {
    d.querySelector('[data-split=validation]').click();
    assert.match(d.getElementById('period').textContent,/3,566/);
    assert.match(d.getElementById('metric-comparison').textContent,/80.07%/);
    assert.match(d.getElementById('experiment-caption').textContent,/Validation/);
    assert.match(d.getElementById('monthly-errors').textContent,/2025-12/);
    assert.match(d.getElementById('experiment-rows').textContent,/85.59%/);
    assert.equal(d.querySelector('[data-split=test]').getAttribute('aria-pressed'),'false');
  } finally {dom.window.close();}
});
test('missing results show an error without publishing empty scores',()=>{
  const dom=boot(true),d=dom.window.document;
  try {assert.equal(d.getElementById('bench-error').hidden,false);assert.equal(d.getElementById('bench-results').hidden,true);}
  finally {dom.window.close();}
});
