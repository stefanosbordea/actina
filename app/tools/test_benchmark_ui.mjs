import {strict as assert} from 'node:assert';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {JSDOM} from '../web/node_modules/jsdom/lib/api.js';
const read=name=>readFileSync(new URL('../site/'+name,import.meta.url),'utf8');
function boot(change) {
  const dom=new JSDOM(read('benchmark.html'),{url:'http://localhost/benchmark.html',runScripts:'outside-only',pretendToBeVisual:true});
  dom.window.eval(read('benchmark-data.js'));
  if(change)change(dom.window.ACTINABENCH);
  dom.window.eval(read('benchmark.mjs'));
  return dom;
}
const withPage=fn=>{const dom=boot();try{fn(dom.window.document,dom.window);}finally{dom.window.close();}};
test('full test opens the original forecast, retains seven methods and defines previous-day reference',()=>withPage(d=>{
  assert.equal(d.getElementById('bench-results').hidden,false);
  assert.match(d.getElementById('model-title').textContent,/Original forecast/);
  assert.match(d.getElementById('period').textContent,/3,567/);
  assert.match(d.getElementById('metric-comparison').textContent,/96.55%/);
  assert.equal(d.querySelectorAll('[data-method]').length,7);
  assert.equal(d.querySelectorAll('#model-select option').length,7);
  assert.equal(d.querySelectorAll('[data-point]').length,7);
  assert.equal(d.querySelectorAll('#experiment-rows tr').length,7);
  assert.match(d.querySelector('.model-browser-note').textContent,/prior day/);
  assert.equal(d.getElementById('method-panel').hidden,true);
  assert.equal(d.getElementById('errors-panel').hidden,true);
}));
test('candidate selection shows its actual precision tradeoff and confusion counts',()=>withPage(d=>{
  d.querySelector('[data-method=direct_classifier]').click();
  assert.match(d.getElementById('metric-comparison').textContent,/96.41%/);
  assert.match(d.getElementById('metric-comparison').textContent,/98.51%/);
  assert.match(d.getElementById('metric-comparison').textContent,/97.45%/);
  assert.match(d.getElementById('outcome-summary').textContent,/37false calls/);
  assert.match(d.getElementById('outcome-summary').textContent,/20 with the previous-day/);
  assert.match(d.getElementById('verdict').textContent,/tradeoff/);
  assert.match(d.getElementById('selection-note').textContent,/Selected by validation F1/);
}));
test('period switching updates selected model, counts, tables, chart and coverage together',()=>withPage(d=>{
  d.querySelector('[data-method=direct_classifier]').click();
  d.querySelector('[data-split=validation]').click();
  assert.match(d.getElementById('period').textContent,/3,566/);
  assert.match(d.getElementById('metric-comparison').textContent,/85.59%/);
  assert.match(d.getElementById('outcome-summary').textContent,/83false calls/);
  assert.match(d.getElementById('experiment-caption').textContent,/Validation/);
  assert.match(d.getElementById('coverage').textContent,/2025-12-05 19:00:00/);
  assert.equal(d.querySelector('[data-split=test]').getAttribute('aria-pressed'),'false');
  assert.match(d.querySelector('[data-point=direct_classifier]').getAttribute('aria-label'),/77.81%/);
  d.querySelector('[data-method=original]').click();
  assert.match(d.getElementById('metric-comparison').textContent,/80.07%/);
  assert.match(d.getElementById('verdict').textContent,/tradeoff/);
}));
test('forecast errors always describe original regression and include every hour/month',()=>withPage(d=>{
  d.querySelector('[data-method=deep_classifier]').click();
  d.querySelector('[data-view=errors]').click();
  assert.equal(d.getElementById('compare-panel').hidden,true);
  assert.equal(d.getElementById('errors-panel').hidden,false);
  assert.match(d.getElementById('errors-panel').textContent,/Original forecast error/);
  assert.match(d.getElementById('error-scores').textContent,/14.27/);
  assert.equal(d.querySelectorAll('#error-rows tr').length,24);
  d.querySelector('[data-group=monthly]').click();
  d.querySelector('[data-split=validation]').click();
  assert.equal(d.querySelectorAll('#error-rows tr').length,6);
  assert.match(d.querySelector('#error-rows tr:last-child').textContent,/2026-0557/);
}));
test('keyboard tabs and mobile selector operate the same model state',()=>withPage((d,w)=>{
  d.querySelector('[data-view=compare]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}));
  assert.equal(d.activeElement.id,'errors-tab');
  assert.equal(d.getElementById('errors-panel').hidden,false);
  d.querySelector('[data-view=compare]').click();
  const select=d.getElementById('model-select');select.value='history_classifier';select.dispatchEvent(new w.Event('change'));
  assert.match(d.getElementById('model-title').textContent,/History classifier/);
  assert.equal(d.querySelector('[data-method=history_classifier]').getAttribute('aria-pressed'),'true');
  d.querySelector('[data-point=deep_classifier]').dispatchEvent(new w.KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
  assert.match(d.getElementById('model-title').textContent,/Neural network/);
  assert.equal(d.getElementById('model-select').value,'deep_classifier');
}));
test('undefined scores remain undefined and malformed reports cannot publish scores',()=>{
  const dom=boot(data=>{data.experiment.methods.deep_classifier.test.selected.precision=null;});
  try{const d=dom.window.document;d.querySelector('[data-method=deep_classifier]').click();assert.match(d.getElementById('metric-comparison').textContent,/—/);assert.doesNotMatch(d.getElementById('metric-comparison').textContent,/NaN/);}finally{dom.window.close();}
  const broken=boot(data=>{data.experiment.status='INCOMPLETE';});
  try{assert.equal(broken.window.document.getElementById('bench-error').hidden,false);assert.equal(broken.window.document.getElementById('bench-results').hidden,true);}finally{broken.window.close();}
});
