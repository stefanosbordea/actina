import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {canonicalRows,isoHour,validateHandoff,evaluateRows,feedbackRows,safeCSV,planRecord,alertRows,weatherDiagnostics} from './public/core.mjs';

const sandbox={module:{exports:{}},exports:{}};
vm.runInNewContext(fs.readFileSync(new URL('./public/vendor/papaparse.min.js',import.meta.url),'utf8'),sandbox);
const Papa=sandbox.module.exports;
const data=JSON.parse(fs.readFileSync(new URL('./public/data.json',import.meta.url)));
const canonical=canonicalRows(data), review=JSON.parse(fs.readFileSync(new URL('../results/independent-review.json',import.meta.url)));
const csv=(rows,extra=[])=>Papa.unparse([['time','predicted',...extra],...rows.map(r=>[r.time,r.predicted,...extra.map(k=>r[k])])]);
const check=text=>validateHandoff(text,canonical,Papa);

test('full canonical import reproduces independently retained regression on exactly paired controls',()=>{
  const result=check(csv(canonical,['actual','baseline']));
  assert.equal(result.status,'COMPLETE');assert.equal(result.rows.length,2208);assert.equal(result.missing.length,0);
  const scores=evaluateRows(result.rows);
  assert.ok(Math.abs(scores.model.mae-review.regression.frozen_model.mae)<1e-10);
  assert.ok(Math.abs(scores.baseline.mae-review.regression.latest_available_persistence.mae)<1e-10);
  assert.equal(scores.byHour.length,24);assert.equal(scores.byMonth.length,3);assert.equal(scores.days,92);
  assert.equal(feedbackRows(scores).length,34);
});
test('equivalent ISO offsets match the same canonical instant',()=>{
  const row=canonical[0], instant=new Date(row.epoch).toISOString();
  assert.equal(isoHour(instant).epoch,isoHour(row.time).epoch);
  assert.equal(check(`time,predicted\n${instant},${row.predicted}`).status,'PARTIAL');
});
test('duplicate instants are blocked even with different offset spellings',()=>{
  const row=canonical[0];const result=check(`time,predicted\n${row.time},1\n${new Date(row.epoch).toISOString()},2`);
  assert.equal(result.status,'BLOCKED');assert.ok(result.issues.some(i=>i.code==='duplicate_time'));assert.equal(result.rows.length,0);
});
test('missing hours are reported and partial scores use only matching truth/control rows',()=>{
  const rows=canonical.slice(0,5).map(r=>({...r,predicted:r.actual})),result=check(csv(rows));
  assert.equal(result.status,'PARTIAL');assert.equal(result.missing.length,2203);
  const scores=evaluateRows(result.rows);assert.equal(scores.model.rows,5);assert.equal(scores.model.mae,0);
  assert.equal(scores.baseline.rows,5);assert.equal(scores.climatology.rows,5);
});
test('timezone-naive, impossible calendar, non-hourly and out-of-period inputs are blocked',()=>{
  for(const time of ['2026-07-01T00:00:00','2026-06-31T00:00:00+03:00','2026-07-01T00:01:00+03:00','2026-10-01T00:00:00+03:00','2026-07-01T24:00:00+03:00','2026-07-01T00:00:00+15:00']){
    const result=check(`time,predicted\n${time},1`);assert.equal(result.status,'BLOCKED',time);assert.equal(result.rows.length,0);
  }
});
test('nonfinite, empty, negative, hexadecimal and spreadsheet-formula predictions are blocked',()=>{
  for(const value of ['Infinity','NaN','','-1','0xff','=1+1','1e308','2000.001'])assert.equal(check(`time,predicted\n${canonical[0].time},${value}`).status,'BLOCKED',value);
});
test('supplied truth and baseline cannot redefine the comparison',()=>{
  for(const field of ['actual','baseline']){
    const result=check(`time,predicted,${field}\n${canonical[0].time},1,${canonical[0][field]+1}`);
    assert.equal(result.status,'BLOCKED');assert.ok(result.issues.some(i=>i.field===field));
  }
});
test('issue provenance matches the nominal preceding-day 18:00 contract',()=>{
  const row=canonical[0];
  assert.equal(check(`time,predicted,forecast_issue_time\n${row.time},1,${row.issue}`).status,'PARTIAL');
  const bad=check(`time,predicted,forecast_issue_time\n${row.time},1,${row.time}`);
  assert.equal(bad.status,'BLOCKED');assert.ok(bad.issues.some(i=>i.code==='issue_mismatch'));
});
test('supplied baseline source time must match canonical authority; omission stays explicit',()=>{
  const row=canonical[0],text=`time,predicted,baseline_source_time\n${row.time},1,${row.baselineSource}`;
  const good=check(text);assert.equal(good.status,'PARTIAL');assert.equal(good.baselineSourceProvenanceSupplied,true);
  const wrong=check(`time,predicted,baseline_source_time\n${row.time},1,${row.time}`);
  assert.equal(wrong.status,'BLOCKED');assert.ok(wrong.issues.some(i=>i.code==='baseline_source_mismatch'));
  assert.equal(check(csv([row])).baselineSourceProvenanceSupplied,false);
  const unsupported=validateHandoff(text,[{...row,baselineSource:null}],Papa);assert.equal(unsupported.status,'BLOCKED');assert.ok(unsupported.issues.some(i=>i.code==='unsupported_provenance'));
});
test('quoted CSV works; malformed quotes, duplicate headers and field mismatches are blocked',()=>{
  const row=canonical[0];
  assert.equal(check(`"time","predicted"\n"${row.time}","${row.predicted}"`).status,'PARTIAL');
  for(const text of [`time,predicted,predicted\n${row.time},1,1`,`time,predicted\n"${row.time},1`,`time,predicted\n${row.time},1,unexpected`])assert.equal(check(text).status,'BLOCKED');
});
test('unsupported forecast headers block rather than silently losing timing or comparator declarations',()=>{
  const row=canonical[0];
  for(const field of ['forecast_issued_at','climatology','Predicted','']){
    const result=check(Papa.unparse([['time','predicted',field],[row.time,1,'2030-01-01T00:00:00Z']]));
    assert.equal(result.status,'BLOCKED',field);assert.equal(result.rows.length,0);
    assert.ok(result.issues.some(i=>i.record===1&&i.field===field&&i.code==='unsupported_column'),field);
  }
});
test('CSV exports preserve quotes/newlines and neutralize formula-leading text',()=>{
  const rows=[['note','value'],['=1+1','hello, "world"\nnext'],['@SUM(A1)','ok']];
  const roundtrip=Papa.parse(safeCSV(rows,Papa)).data;
  assert.equal(roundtrip[1][0],"'=1+1");assert.equal(roundtrip[1][1],rows[1][1]);assert.equal(roundtrip[2][0],"'@SUM(A1)");
});
test('review records retain selected plan, immutable dataset identity and simulation-only authority',()=>{
  const day=data.days.find(d=>d.date==='2026-07-15'),plan=day.schedules['500'];
  const record=planRecord({day,tank:500,plan,manifest:{data_sha256:'dataset-fixture'},reviewer:' QA ',decision:'Needs team review',note:' Fixture only ',analysis:{source:'imported',hash:'model-fixture'},id:'id',createdAt:'2026-10-02T00:00:00Z'});
  assert.equal(record.reviewer,'QA');assert.equal(record.note,'Fixture only');assert.equal(record.tankCapacityM3,500);
  assert.equal(record.hourly.productionM3.length,24);assert.equal(record.datasetSHA256,'dataset-fixture');
  assert.equal(record.planSource,'Frozen reference radiation; illustrative clock tariffs');assert.match(record.scope,/no plant authorization/);
  assert.throws(()=>planRecord({day,tank:500,plan,manifest:{},reviewer:'',decision:'Needs team review',note:'x'}),/reviewer/);
  assert.throws(()=>planRecord({day,tank:500,plan,manifest:{},reviewer:'QA',decision:'Operate plant',note:'x'}),/Invalid/);
});
test('alerts reflect injected/no-leak fixtures and acknowledgements cannot transfer to another model',()=>{
  const day=data.days.find(d=>d.date==='2026-07-15'),plan=day.schedules['4000'],rows=canonical.filter(r=>r.date===day.date);
  const injected=alertRows(day,plan,4000,rows,true),normal=alertRows(day,plan,4000,rows,false);
  assert.equal(injected.filter(r=>r.type==='Synthetic meter').length,4);assert.equal(normal.filter(r=>r.type==='Synthetic meter').length,0);
  const event=injected[0],ack={[event.id]:true};assert.equal(alertRows(day,plan,4000,rows,true,ack)[0].reviewed,true);
  assert.equal(alertRows(day,plan,4000,rows,true,ack,'different-model')[0].reviewed,false);
});

test('retained daylight/cloud comparisons reproduce Python evaluator on the same timestamps',()=>{
 const expected=JSON.parse(fs.readFileSync(new URL('../results/metrics.json',import.meta.url))),d=evaluateRows(canonical).diagnostics;
 assert.equal(d.daylight.rows,1200);assert.equal(d.daylight.days,92);assert.equal(d.unknown.rows,0);
 for(const [name,column]of[['model','model'],['persistence','baseline'],['climatology','climatology']]){
  assert.ok(Math.abs(d.daylight[column].mae-expected.daylight[name].mae)<1e-10);
  for(const bin of d.cloudiness){const e=expected.cloudiness_daylight[bin.key];assert.equal(bin.rows,e.rows);assert.ok(Math.abs(bin[column].mae-e[name].mae)<1e-10);assert.ok(Math.abs(bin[column].rmse-e[name].rmse)<1e-10);}
 }
 assert.deepEqual(d.cloudiness.map(x=>x.rows),[1090,92,18]);assert.deepEqual(d.cloudiness.map(x=>x.days),[92,25,9]);
});
test('diagnostic boundaries preserve exact 20/60 decisions and missing cloud remains unknown',()=>{
 const row={...canonical[0],actual:21,predicted:20,baseline:19,climatology:18};
 const rows=[0,19.99,20,59.99,60,100,100.5,101,-1,null,undefined,NaN,Infinity,'0'].map(cloudCover=>({...row,cloudCover}));
 rows.push({...row,actual:20,cloudCover:0});const d=weatherDiagnostics(rows);
 assert.equal(d.daylight.rows,14);assert.deepEqual(d.cloudiness.map(x=>x.rows),[2,2,2]);assert.equal(d.unknown.rows,8);assert.equal(d.daylight.model.rows,14);
 assert.equal(d.cloudiness[2].label,'60 ≤ cloud ≤ 100%');
 assert.equal(weatherDiagnostics([{...row,cloudCover:100.000001}]).unknown.rows,1);
 const empty=weatherDiagnostics([{...row,actual:20,cloudCover:null}]);assert.equal(empty.daylight.rows,0);assert.equal(empty.daylight.model.mae,null);assert.ok(empty.cloudiness.every(x=>x.rows===0&&x.model.mae===null));
 const missing=canonicalRows({days:[{...data.days[0],cloud_cover:undefined}]}).filter(r=>r.actual>20);assert.ok(missing.every(r=>r.cloudCover===null));assert.equal(weatherDiagnostics(missing).unknown.rows,missing.length);
});
test('incoming forecasts use canonical realized cloud diagnostics even if CSV supplies a different cloud',()=>{
 const truth=canonical.find(r=>r.actual>20&&r.cloudCover>=20),result=check(`time,predicted,cloud_cover\n${truth.time},${truth.actual},0`);
 assert.equal(result.status,'PARTIAL');assert.equal(result.rows[0].cloudCover,truth.cloudCover);assert.ok(result.warnings.some(s=>s.includes('Supplied cloud_cover is not used')));
 const d=evaluateRows(result.rows).diagnostics;assert.equal(d.daylight.model.mae,0);assert.equal(d.cloudiness[0].rows,0);assert.equal(d.cloudiness[1].rows+d.cloudiness[2].rows,1);
});
