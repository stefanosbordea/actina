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
  assert.equal($('home-demo-minimum').textContent,'668 m³'); assert.match($('home-demo-detail').textContent,/132 m³ below reserve\. 288 m³ below/);assert.notEqual($('home-demo-chart').innerHTML,original);
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
  menu.open=true;menu.querySelector('a').click();assert.equal(menu.open,false);assert.equal(menu.querySelectorAll('a').length,4);
 } finally {w.close();}
});

test('concept animation respects reduced motion by default and allows an explicit play override', () => {
 const dom=new JSDOM(read('index.html')),w=dom.window,document=w.document;let changed;
 const preference={matches:true,addEventListener:(event,fn)=>{assert.equal(event,'change');changed=fn;}};
 w.matchMedia=()=>preference;
 try {
  setupHomeDemo({document,onOpen:()=>{}});
  const image=document.getElementById('home-flow-diagram'),button=document.getElementById('home-flow-toggle'),before=document.getElementById('home-demo-values').innerHTML;
  assert.equal(button.hidden,false);assert.equal(image.getAttribute('src'),'solar-water.svg#still');assert.equal(button.getAttribute('aria-label'),'Play diagram animation');
  preference.matches=false;changed();assert.equal(image.getAttribute('src'),'solar-water.svg');
  preference.matches=true;changed();assert.equal(image.getAttribute('src'),'solar-water.svg#still');
  button.click();assert.equal(image.getAttribute('src'),'solar-water.svg#play');assert.equal(button.getAttribute('aria-label'),'Pause diagram animation');
  preference.matches=false;changed();preference.matches=true;changed();assert.equal(image.getAttribute('src'),'solar-water.svg#play');
  button.click();assert.equal(image.getAttribute('src'),'solar-water.svg#still');assert.equal(button.getAttribute('aria-label'),'Play diagram animation');
  preference.matches=false;changed();assert.equal(image.getAttribute('src'),'solar-water.svg#still');
  assert.equal(document.getElementById('home-demo-values').innerHTML,before);
 } finally {w.close();}
});

test('explicit play and pause survive a reload and returning home without restarting the image', () => {
 const key='aktina.diagram-motion';
 for(const [choice,reduced,fragment,label] of [['play',true,'#play','Pause'],['pause',false,'#still','Play']]){
  const first=new JSDOM(read('index.html'),{url:'https://aktina.example/workspace/#home'});
  let saved;
  try {
   first.window.matchMedia=()=>({matches:reduced,addEventListener:()=>{}});
   setupHomeDemo({document:first.window.document,onOpen:()=>{}});
   first.window.document.getElementById('home-flow-toggle').click();
   saved=first.window.localStorage.getItem(key);
   assert.equal(saved,choice);
  } finally {first.window.close();}
  const restored=new JSDOM(read('index.html'),{url:'https://aktina.example/workspace/#overview'}),w=restored.window;
  try {
   w.localStorage.setItem(key,saved);
   w.matchMedia=()=>({matches:reduced,addEventListener:()=>{}});
   setupHomeDemo({document:w.document,onOpen:()=>{}});
   const image=w.document.getElementById('home-flow-diagram'),button=w.document.getElementById('home-flow-toggle');
   assert.equal(image.getAttribute('src'),`solar-water.svg${fragment}`);
   assert.equal(button.getAttribute('aria-label'),`${label} diagram animation`);
   const setAttribute=image.setAttribute.bind(image),writes=[];
   image.setAttribute=(name,value)=>{writes.push(name);setAttribute(name,value);};
   w.history.replaceState(null,'','#home');w.dispatchEvent(new w.HashChangeEvent('hashchange'));
   w.dispatchEvent(new w.PageTransitionEvent('pageshow',{persisted:true}));
   assert.equal(image.getAttribute('src'),`solar-water.svg${fragment}`);
   assert.deepEqual(writes,[]);
  } finally {w.close();}
 }
});

test('unavailable or invalid saved motion settings cannot prevent playback or bypass reduced motion', () => {
 for(const unavailable of [false,true]){
  const dom=new JSDOM(read('index.html'),{url:'https://aktina.example/workspace/#home'}),w=dom.window;
  try {
   w.matchMedia=()=>({matches:true,addEventListener:()=>{}});
   if(unavailable)Object.defineProperty(w,'localStorage',{get:()=>{throw new w.DOMException('Storage blocked','SecurityError');}});
   else w.localStorage.setItem('aktina.diagram-motion','invalid');
   setupHomeDemo({document:w.document,onOpen:()=>{}});
   const image=w.document.getElementById('home-flow-diagram'),button=w.document.getElementById('home-flow-toggle');
   assert.equal(image.getAttribute('src'),'solar-water.svg#still');
   button.click();assert.equal(image.getAttribute('src'),'solar-water.svg#play');
   button.click();assert.equal(image.getAttribute('src'),'solar-water.svg#still');
  } finally {w.close();}
 }
});

test('workspace home links verified v2 forecasts and keeps the simulation label out of the border', () => {
 const dom=new JSDOM(read('index.html')),document=dom.window.document;
 try {
  assert.equal(document.querySelectorAll('#product-home a[href="../forecast.html"]').length,3);
  assert.equal(document.querySelector('.home-demo-controls legend').textContent,'Scenario');
  assert.equal(document.querySelector('.home-demo-controls').querySelectorAll('input[type=radio]').length,3);
  assert.doesNotMatch(document.getElementById('product-home').textContent,/Test the same plan/);
  const svg=read('solar-water.svg');
  assert.match(svg,/id="still"/);assert.match(svg,/:root:target/);assert.match(svg,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(svg,/id="play"/);assert.match(svg,/#play:target .energy-flow/);assert.match(svg,/animation-play-state:running/);
  assert.match(svg,/animation:flow 4s linear infinite/);assert.match(svg,/animation:ripple 4s ease-out infinite/);
  assert.match(svg,/class="energy-flow"/);assert.match(svg,/class="water-flow"/);assert.match(svg,/level is illustrative and fixed/);
 } finally {dom.window.close();}
});
test('failed full-review handoff restores the action and reports the failure', async () => {
 const dom=new JSDOM(read('index.html')),w=dom.window,document=w.document;
 try {
  setupHomeDemo({document,onOpen:async()=>{throw Error('Unavailable');}});document.getElementById('home-demo-open').click();await Promise.resolve();await Promise.resolve();
  assert.equal(document.getElementById('home-demo-open').disabled,false);assert.equal(document.getElementById('home-demo-error').hidden,false);
 } finally {w.close();}
});
