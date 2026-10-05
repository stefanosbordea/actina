import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {JSDOM} from 'jsdom';
import {resilienceTemplate,setupResilience} from './public/resilience-ui.mjs';
import {planForObservation} from './public/observation-restart.mjs';

function boot(drawChart){
 const dom=new JSDOM(resilienceTemplate),w=dom.window,$=id=>w.document.getElementById(id),data=JSON.parse(fs.readFileSync(new URL('public/data.json',import.meta.url)));
 const c={day:data.days[0],capacity:4000,reserve:800,demand:data.demand,unitCapacity:data.unit_capacity,plan:data.days[0].schedules['4000'],label:'Retained reference',imported:false,identity:{data_sha256:'a'.repeat(64)}};
 const previous={document:globalThis.document,Option:globalThis.Option};globalThis.document=w.document;globalThis.Option=w.Option;
 const downloads=[],text=(id,value)=>{$(id).textContent=value;},rows=(id,values)=>text(id,JSON.stringify(values));let readings=[],bridgeCurrent=true;
 const ui=setupResilience({$,fmt:(n,d=0)=>n.toLocaleString('en-GB',{maximumFractionDigits:d}),text,kpis:rows,facts:rows,table:(id,headers,values)=>rows(id,[headers,...values]),lineChart:(id,series)=>{rows(id,series);drawChart?.($(id),series);},json:(name,value)=>downloads.push({name,value}),getContext:()=>c,getTankReadings:()=>readings,isObservationRestartCurrent:()=>bridgeCurrent});
 const input=(id,value,event='input')=>{$(id).value=value;$(id).dispatchEvent(new w.Event(event));};
 return {ui,w,$,c,downloads,input,setReadings:value=>{readings=value;},revoke:()=>{bridgeCurrent=false;},close(){w.close();for(const [key,value] of Object.entries(previous))if(value===undefined)delete globalThis[key];else globalThis[key]=value;}};
}

test('assessment stages preserve inputs and block stale or invalid results',()=>{
 const a=boot();try{
  a.ui.render();const before=a.ui.snapshot();assert.equal(a.$('assessment-workbench').dataset.mode,'result');
  a.ui.editConditions();assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.equal(a.w.document.activeElement.id,'resilience-demand');assert.deepEqual(a.ui.snapshot(),before);
  a.input('resilience-demand','');assert.equal(a.ui.snapshot(),null);assert.equal(a.ui.conditionSummary(),'');assert.equal(a.$('resilience-export').disabled,true);assert.equal(a.$('resilience-show-result').disabled,true);assert.equal(a.ui.showResult(),false);
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.notEqual(a.$('resilience-error').textContent,'');
  a.input('resilience-demand','20');a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.w.document.activeElement.id,'resilience-verdict');assert.equal(a.$('resilience-show-result').disabled,false);
  const after=a.ui.snapshot();assert.equal(after.inputs.scenario.demand_multiplier,1.2);assert.match(a.ui.conditionSummary(),/demand \+20%, starting water 2,000 m³/);assert.deepEqual(after.identity,before.identity);assert.deepEqual(after.inputs.production,before.inputs.production);
  a.$('resilience-export').click();assert.deepEqual(a.downloads[0].value,after);
  a.input('resilience-start','10','change');assert.equal(a.ui.snapshot(),null);assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');
 }finally{a.close();}
});

test('mobile result chart is measured again after its stage becomes visible',()=>{
 const measured=[],a=boot(chart=>{const width=chart.getBoundingClientRect().width||680;chart.dataset.drawnWidth=String(width);measured.push({mode:a.$('assessment-workbench').dataset.mode,width});});
 try{
  const chart=a.$('resilience-chart'),workbench=a.$('assessment-workbench');
  chart.getBoundingClientRect=()=>({width:workbench.dataset.mode==='result'?312:0});
  const scrolled=[];workbench.scrollIntoView=()=>scrolled.push(workbench.id);
  a.ui.render();a.ui.editConditions();measured.length=0;
  a.ui.showResult();assert.deepEqual(measured.at(-1),{mode:'result',width:312});assert.equal(chart.dataset.drawnWidth,'312');
  a.ui.editConditions();a.input('resilience-demand','20');measured.length=0;
  a.$('resilience-form').dispatchEvent(new a.w.Event('submit',{cancelable:true}));
  assert.deepEqual(measured.at(-1),{mode:'result',width:312});assert.equal(chart.dataset.drawnWidth,'312');
  assert.equal(a.w.document.activeElement.id,'resilience-verdict');assert.equal(scrolled.at(-1),'assessment-workbench');assert.equal(a.ui.snapshot().inputs.scenario.demand_multiplier,1.2);
 }finally{a.close();}
});

test('one evidence selector exposes accounting, sensitivity, comparison and source without nested disclosures',()=>{
 const a=boot();try{
  a.ui.render();assert.equal(a.$('resilience-details').querySelectorAll('details').length,0);
  for(const name of ['accounting','sensitivity','comparison','source']){
   a.input('resilience-evidence-view',name,'change');
   const visible=[...a.w.document.querySelectorAll('.assessment-evidence-panel')].filter(p=>!p.hidden);
   assert.equal(visible.length,1);assert.equal(visible[0].id,'resilience-evidence-'+name);assert.notEqual(visible[0].textContent,'');
  }
  assert.match(a.$('resilience-conditions-summary').textContent,/Simulation: demand \+10%/);assert.match(a.$('resilience-identity').textContent,/Source data SHA-256/);
 }finally{a.close();}
});

test('reading restart, sensitivity, reset and showcase keep their result and provenance semantics',()=>{
 const a=boot();try{
  const time=a.c.day.times[10],reading={time,epoch:Date.parse(time),available_at:time,asset_id:'tank-a',assetLabel:'Tank A',value:700,reviewAsOf:time,sourceKind:'synthetic_fixture',identity:{observations:{sha256:'b'.repeat(64)},contract:{sha256:'c'.repeat(64)}}};
  a.setReadings([reading]);a.ui.render();a.ui.editConditions();a.$('resilience-reading').value='0';a.$('resilience-map').checked=true;a.$('resilience-use-reading').click();
  assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.ui.snapshot().selected.start_hour,10);assert.equal(a.ui.snapshot().observation.value,700);
  a.$('resilience-details').open=true;a.input('resilience-evidence-view','sensitivity','change');a.$('resilience-matrix').querySelector('button[aria-label^="Demand +20%, production loss 10%:"]').click();
  const changed=a.ui.snapshot();assert.equal(changed.inputs.scenario.demand_multiplier,1.2);assert.equal(changed.inputs.scenario.production_multiplier,0.9);assert.equal(changed.observation.value,700);assert.equal(changed.selected.start_hour,10);assert.equal(a.$('assessment-workbench').dataset.mode,'result');
  a.$('resilience-reset').click();assert.equal(a.ui.snapshot().observation,null);assert.equal(a.ui.snapshot().selected.start_hour,0);assert.equal(a.ui.snapshot().inputs.scenario.demand_multiplier,1);
  a.ui.setScenario({demand_multiplier:1.15,production_multiplier:0.8,outage:{start_hour:12,duration_hours:0.5}});assert.equal(a.$('assessment-workbench').dataset.mode,'result');assert.equal(a.ui.snapshot().inputs.scenario.outage.duration_hours,0.5);
  const proof={plan:planForObservation(a.c),reading,start_hour:10,comparison_cutoff:time};a.ui.acceptObservationRestart(proof);
  assert.equal(a.ui.snapshot().observation.bridge.start_hour,10);assert.equal(a.$('resilience-manual-reading').hidden,true);assert.equal(a.$('assessment-workbench').dataset.mode,'result');
  a.revoke();a.ui.render();assert.equal(a.ui.snapshot(),null);assert.equal(a.$('resilience-export').disabled,true);assert.equal(a.$('assessment-workbench').dataset.mode,'conditions');assert.equal(a.$('resilience-manual-reading').hidden,false);
 }finally{a.close();}
});
