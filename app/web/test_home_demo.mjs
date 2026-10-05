import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createHash} from 'node:crypto';
import {JSDOM} from 'jsdom';
import {homeReference} from './public/home-reference.mjs';
import {replayDemo, setupHomeDemo} from './public/home-demo.mjs';

const read = file => fs.readFileSync(new URL(`public/${file}`, import.meta.url), 'utf8');
test('homepage subset matches retained source bytes and exact replay inputs', () => {
 const raw = read('data.json'), source = JSON.parse(raw), day = source.days.find(day => day.date === homeReference.date), plan = day.schedules['4000'];
 assert.equal(homeReference.source.sha256, createHash('sha256').update(raw).digest('hex'));
 assert.equal(homeReference.source.sha256, JSON.parse(read('manifest.json')).data_sha256);
 assert.deepEqual(homeReference.input, {times: day.times, production: plan.production, demand: source.demand, capacity: 4000, reserve: 800, initial: plan.totals.initial_storage_m3, target: plan.totals.final_storage_m3});
 assert.ok(fs.statSync(new URL('public/home-reference.mjs', import.meta.url)).size < 2500);
});
test('three homepage conditions retain exact water accounting and reveal reserve failures', () => {
 for (const [name, minimum, final, deficit] of [['original',800,2000,0], ['demand',668,1712,132], ['outage',700,1000,100]]) {
  const r = replayDemo(name);
  assert.equal(r.totals.min_storage_m3, minimum); assert.equal(r.totals.final_storage_m3, final); assert.equal(r.totals.max_reserve_deficit_m3, deficit);
  assert.equal(r.totals.unmet_m3,0); assert.equal(r.totals.spill_m3,0); assert.equal(r.rows.length,24);
 }
 assert.throws(() => replayDemo('unknown'), /Unknown/);
});
test('demo controls redraw real values, preserve accessible hourly data, and hand off the selected case', async () => {
 const dom = new JSDOM(read('index.html')), w = dom.window, document = w.document, $ = id => document.getElementById(id), opened = [];
 try {
  setupHomeDemo({document,onOpen:name=>opened.push(name)});
  assert.equal($('home-demo-outcome').textContent,'Reserve holds'); assert.equal($('home-demo-values').rows.length,25);
  const original = $('home-demo-chart').innerHTML, input = document.querySelector('[name="home-demo-case"][value="demand"]');
  input.checked=true;input.dispatchEvent(new w.Event('change'));
  assert.equal($('home-demo-minimum').textContent,'668 m³'); assert.match($('home-demo-detail').textContent,/132 m³ below reserve; 288 m³ below/);assert.notEqual($('home-demo-chart').innerHTML,original);
  assert.match($('home-demo-source').textContent,/ceebcc105842c026/);assert.match($('home-demo-chart').getAttribute('aria-label'),/Reserve breached/);
  $('home-demo-open').click();await Promise.resolve();assert.deepEqual(opened,['demand']);assert.equal($('home-demo-open').disabled,false);
 } finally {w.close();}
});
test('hidden-to-visible and mobile-to-desktop demo charts measure the actual container', () => {
 const dom=new JSDOM(read('index.html')),w=dom.window,document=w.document,chart=document.getElementById('home-demo-chart');let observed,callback,width=0;
 try {
  chart.getBoundingClientRect=()=>({width});w.ResizeObserver=class{constructor(fn){callback=fn;}observe(element){observed=element;}};
  setupHomeDemo({document,onOpen:()=>{}});assert.equal(observed,chart);
  for(width of [310,1006]){callback([{contentRect:{width}}]);assert.equal(chart.querySelector('svg').getAttribute('viewBox'),`0 0 ${width} 230`);}
  width=0;callback([{contentRect:{width}}]);assert.equal(chart.querySelector('svg').getAttribute('viewBox'),'0 0 1006 230');
 } finally {w.close();}
});
test('mobile section menu closes on Escape with focus return, and on section selection', () => {
 const dom=new JSDOM(read('index.html')),w=dom.window,document=w.document,menu=document.getElementById('home-menu');
 try {
  setupHomeDemo({document,onOpen:()=>{}});menu.open=true;menu.querySelector('a').focus();document.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));
  assert.equal(menu.open,false);assert.equal(document.activeElement,menu.querySelector('summary'));
  menu.open=true;menu.querySelector('a').click();assert.equal(menu.open,false);assert.equal(menu.querySelectorAll('a').length,3);
 } finally {w.close();}
});
test('failed full-review handoff restores the action and reports the failure', async () => {
 const dom=new JSDOM(read('index.html')),w=dom.window,document=w.document;
 try {
  setupHomeDemo({document,onOpen:async()=>{throw Error('Unavailable');}});document.getElementById('home-demo-open').click();await Promise.resolve();await Promise.resolve();
  assert.equal(document.getElementById('home-demo-open').disabled,false);assert.equal(document.getElementById('home-demo-error').hidden,false);
 } finally {w.close();}
});
