import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {evaluateRoadmapHandoff,parseRoadmapDeclaration} from './public/roadmap-handoff.mjs';

const box={};vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);const Papa=box.Papa;
const hash=text=>createHash('sha256').update(text).digest('hex');
const columns={weather:['time','shortwave_radiation','cloud_cover','temperature_2m','relative_humidity_2m'],predictions:['time','actual','predicted','baseline'],day_forecast:['date','hour','predicted_radiation','surplus_flag'],schedule:['date','hour','normal_power_kw','aquashift_power_kw','tank_level_m3','surplus_flag']};
const at=(date,hour)=>`${date}T${String(hour).padStart(2,'0')}:00:00+03:00`;
function retain(a,role,rows){const text=Papa.unparse([columns[role],...rows]);a.files[role]={name:`${role}.csv`,text,sha256:hash(text)};a.declaration.declared_links={schedule_forecast_sha256:a.files.day_forecast?.sha256,weather_sha256:a.files.weather?.sha256};}
function patch(a,role,change){const rows=Papa.parse(a.files[role].text).data.slice(1);change(rows);retain(a,role,rows);}
function fixture(dates=['2026-07-01']){
 const a={files:{},Papa,declaration:{schema:1,kind:'roadmap_handoff_declaration',source_kind:'illustrative_scenario',source_label:'Analytical handoff',utc_offset:'+03:00',radiation_time_semantics:'interval_start',date_hour_semantics:'interval_start',weather_units:{shortwave_radiation:'W/m2',cloud_cover:'percent',temperature_2m:'degC',relative_humidity_2m:'percent'},power_semantics:'interval_mean',tank_level_semantics:'aquashift_interval_end',tank_capacity_m3:1000,surplus_threshold_w_m2:600,surplus_comparison:'greater_than',test_period:{start:at(dates[0],0),end:new Date(Date.parse(at(dates.at(-1),0))+24*3600000).toISOString()},tariffs:[],declared_links:{}}};
 const rows=Object.fromEntries(Object.keys(columns).map(role=>[role,[]]));
 for(const date of dates)for(let hour=0;hour<24;hour++){
  const radiation=hour<12?700:200,flag=Number(hour<12);rows.weather.push([at(date,hour),radiation,30,25,50]);rows.predictions.push([at(date,hour),radiation,radiation+10,radiation-20]);rows.day_forecast.push([date,hour,radiation+10,flag]);rows.schedule.push([date,hour,10,10,100,flag]);a.declaration.tariffs.push({date,hour,eur_kwh:hour<12?.1:.3});
 }
 for(const role of Object.keys(columns))retain(a,role,rows[role]);return a;
}
const evaluate=a=>evaluateRoadmapHandoff(a);
const near=(actual,expected)=>assert.ok(Math.abs(actual-expected)<=Math.max(1e-12,Math.abs(expected)*1e-14),`${actual} != ${expected}`);

test('identical complete plans have zero differences and explicit unestablished water/forecast claims',()=>{
 const a=fixture(),before=JSON.stringify([a.declaration,a.files]),r=evaluate(a);
 assert.deepEqual(r.forecast.model,{rows:24,mae:10,rmse:10,bias:10});assert.deepEqual(r.forecast.baseline,{rows:24,mae:20,rmse:20,bias:-20});
 assert.equal(r.forecast.coverage.status,'complete');assert.equal(r.demo.coverage.status,'complete');assert.equal(r.demo.support.hours,24);
 assert.deepEqual(r.demo.support.electricity_kwh,{normal:240,aquashift:240,delta:0});assert.deepEqual(r.demo.support.forecast_flagged_electricity_kwh,{normal:120,aquashift:120,delta:0});assert.equal(r.demo.support.cost_eur.delta,0);
 assert.equal(r.water_comparability.status,'not_established');assert.equal(r.forecast_attribution.status,'not_established');assert.equal(r.lineage.status,'caller_declared');assert.equal(JSON.stringify([a.declaration,a.files]),before);assert.equal(r.file_identities.weather.sha256,a.files.weather.sha256);
});
test('nonconsecutive selected days retain exact support without bridging unprovided days',()=>{
 const a=fixture(['2026-07-01','2026-07-03']);patch(a,'schedule',rows=>rows.forEach(r=>r[3]=Number(r[1])<12?20:0));const r=evaluate(a);
 assert.deepEqual(r.demo.coverage.selected_dates,['2026-07-01','2026-07-03']);assert.equal(r.demo.coverage.expected_hours,48);assert.equal(r.demo.support.hours,48);assert.equal(r.demo.support.electricity_kwh.delta,0);near(r.demo.support.cost_eur.delta,-48);assert.equal(r.demo.support.forecast_flagged_electricity_kwh.delta,240);
 assert.equal(r.forecast.coverage.expected_hours,72);assert.equal(r.forecast.coverage.matched_hours,48);assert.equal(r.forecast.coverage.missing_times.length,24);assert.ok(r.demo.days.every(d=>d.totals.hours===24));
});
test('lower power never establishes comparable water even with a bounded tank trace',()=>{
 const a=fixture();patch(a,'schedule',rows=>rows.forEach(r=>{r[3]=5;r[4]=50;}));const r=evaluate(a);assert.equal(r.demo.support.electricity_kwh.delta,-120);assert.equal(r.tank.min_m3,50);assert.equal(r.water_comparability.status,'not_established');assert.equal(r.produced_m3,undefined);
});
test('better forecast with unchanged schedules has zero decision difference',()=>{
 const a=fixture();patch(a,'predictions',rows=>rows.forEach(r=>r[2]=r[1]));const r=evaluate(a);assert.equal(r.forecast.model.mae,0);assert.equal(r.demo.support.electricity_kwh.delta,0);assert.equal(r.demo.support.cost_eur.delta,0);assert.equal(r.forecast_attribution.status,'not_established');assert.equal(r.gaps.find(g=>g.code==='different_supplied_predictions').count,24);
});
test('point power remains inspectable and never receives energy or cost totals',()=>{
 const a=fixture();a.declaration.power_semantics='point_sample';const r=evaluate(a);assert.equal(r.demo.rows[0].normal_power_kw,10);assert.deepEqual(r.demo.support,{hours:24,electricity_kwh:null,cost_eur:null,forecast_flagged_electricity_kwh:null});assert.equal(r.demo.days[0].totals.electricity_kwh,null);
});
test('missing schedule or forecast hours distinguish paired electrical support and joined flag coverage',()=>{
 const a=fixture();patch(a,'schedule',rows=>rows.shift());a.declaration.tariffs.shift();let r=evaluate(a);assert.equal(r.demo.coverage.status,'partial');assert.equal(r.demo.support.hours,23);assert.equal(r.demo.support.electricity_kwh.normal,230);assert.equal(r.demo.days[0].totals,null);assert.deepEqual(r.demo.days[0].coverage.missing_schedule_hours,[0]);assert.equal(r.demo.rows[0].normal_power_kw,null);
 const b=fixture();patch(b,'day_forecast',rows=>rows.shift());r=evaluate(b);assert.equal(r.demo.support.hours,24);assert.equal(r.demo.coverage.matched_hours,23);assert.equal(r.demo.support.electricity_kwh.normal,240);assert.equal(r.demo.support.forecast_flagged_electricity_kwh,null);assert.equal(r.demo.days[0].totals,null);
});
test('missing prediction or weather hours stay explicit without substituting canonical truth',()=>{
 const a=fixture();patch(a,'predictions',rows=>rows.shift());patch(a,'weather',rows=>rows.splice(1,1));const r=evaluate(a);assert.equal(r.forecast.coverage.supplied_hours,23);assert.equal(r.forecast.coverage.matched_hours,22);assert.equal(r.forecast.coverage.missing_times.length,2);assert.equal(r.forecast.coverage.unmatched_times.length,1);assert.equal(r.forecast.model.mae,10);
});
test('empty retained schemas produce unknown metrics rather than zero results',()=>{
 const a=fixture();for(const role of Object.keys(columns))retain(a,role,[]);a.declaration.tariffs=[];const r=evaluate(a);assert.equal(r.forecast.model.mae,null);assert.equal(r.demo.support.electricity_kwh,null);assert.equal(r.demo.support.cost_eur,null);assert.equal(r.demo.coverage.status,'partial');assert.equal(r.tank.min_m3,null);
});
test('missing tariffs keep full-support cost unknown; explicit zero prices stay zero',()=>{
 const a=fixture();a.declaration.tariffs.pop();let r=evaluate(a);assert.equal(r.demo.support.cost_eur,null);assert.equal(r.demo.days[0].totals.cost_eur,null);a.declaration.tariffs=null;assert.equal(evaluate(a).demo.support.cost_eur,null);a.declaration.tariffs=fixture().declaration.tariffs.map(t=>({...t,eur_kwh:0}));r=evaluate(a);assert.deepEqual(r.demo.support.cost_eur,{normal:0,aquashift:0,delta:0});
});
test('threshold boundaries distinguish strict and inclusive flags',()=>{
 const a=fixture();patch(a,'day_forecast',rows=>rows.forEach(r=>{r[2]=600;r[3]=0;}));patch(a,'schedule',rows=>rows.forEach(r=>r[5]=0));assert.equal(evaluate(a).demo.support.forecast_flagged_electricity_kwh.normal,0);a.declaration.surplus_comparison='at_or_above';assert.throws(()=>evaluate(a),/threshold/);patch(a,'day_forecast',rows=>rows.forEach(r=>r[3]=1));patch(a,'schedule',rows=>rows.forEach(r=>r[5]=1));assert.equal(evaluate(a).demo.support.forecast_flagged_electricity_kwh.normal,240);
});
test('UTC-equivalent prediction instants, BOM and reordered source rows preserve calculations',()=>{
 const a=fixture();patch(a,'predictions',rows=>{rows.forEach(r=>r[0]=new Date(r[0]).toISOString());rows.reverse();});a.files.weather.text='\uFEFF'+a.files.weather.text;a.files.weather.sha256=hash(a.files.weather.text);a.declaration.declared_links.weather_sha256=a.files.weather.sha256;const r=evaluate(a);assert.equal(r.forecast.coverage.status,'complete');assert.equal(r.forecast.model.mae,10);
});
test('strict schemas, numeric domains and raw links reject incompatible supplied material',()=>{
 for(const change of [a=>a.declaration.extra=true,a=>delete a.declaration.power_semantics,a=>a.declaration.weather_units.cloud_cover='fraction',a=>a.declaration.date_hour_semantics='interval_end',a=>a.declaration.declared_links.weather_sha256='0'.repeat(64),a=>a.declaration.declared_links.schedule_forecast_sha256='0'.repeat(64),a=>a.files.weather.extra=true,a=>a.declaration.tank_capacity_m3=0,a=>a.declaration.utc_offset='+99:00']){const a=fixture();change(a);assert.throws(()=>evaluate(a));}
 for(const [role,index,value]of [['schedule',2,-1],['weather',2,101],['weather',4,101],['weather',1,2001],['predictions',2,'NaN'],['day_forecast',3,'true'],['day_forecast',1,'1.5']]){const a=fixture();patch(a,role,rows=>rows[0][index]=value);assert.throws(()=>evaluate(a));}
 const a=fixture();a.files.schedule.text=a.files.schedule.text.replace('surplus_flag','surplus_flag,total_eur');assert.throws(()=>evaluate(a),/headers/);
});
test('duplicate instants, naive times, wrong reference actuals and conflicting flags reject',()=>{
 for(const role of Object.keys(columns)){const a=fixture();patch(a,role,rows=>rows.push(rows[0]));assert.throws(()=>evaluate(a),/Duplicate/);}
 for(const [role,index,value]of [['weather',0,'2026-07-01T00:00:00'],['predictions',1,699],['schedule',5,0]]){const a=fixture();patch(a,role,rows=>rows[0][index]=value);assert.throws(()=>evaluate(a));}
 const a=fixture();patch(a,'predictions',rows=>rows[0][0]='2026-06-01T00:00:00+03:00');assert.throws(()=>evaluate(a),/outside/);
});
test('demo offset must match Cyprus and duplicated autumn local hours are unsupported',()=>{
 const a=fixture();a.declaration.utc_offset='+02:00';assert.throws(()=>evaluate(a),/Europe\/Nicosia/);
 const b=fixture();for(const role of ['day_forecast','schedule'])patch(b,role,rows=>{rows.splice(1);rows[0][0]='2026-10-25';rows[0][1]=3;});b.declaration.tariffs=null;assert.throws(()=>evaluate(b),/Ambiguous/);
});
test('tariff duplicates, unmatched instants, malformed rows and negative prices reject',()=>{
 for(const change of [a=>a.declaration.tariffs.push({...a.declaration.tariffs[0]}),a=>a.declaration.tariffs[0].date='2026-07-02',a=>a.declaration.tariffs[0].eur_kwh=-1,a=>a.declaration.tariffs[0].hour='0',a=>a.declaration.tariffs[0].extra=1]){const a=fixture();change(a);assert.throws(()=>evaluate(a));}
});
test('tank contradictions remain visible evidence without inventing normal water service',()=>{
 const a=fixture();a.declaration.tank_capacity_m3=80;a.declaration.tank_level_semantics='unspecified';const r=evaluate(a);assert.equal(r.tank.above_capacity_hours,24);assert.ok(r.gaps.some(g=>g.code==='tank_above_declared_capacity'));assert.equal(r.water_comparability.status,'not_established');
});
test('compensated rowwise changes survive common large loads and price products',()=>{
 const a=fixture();patch(a,'schedule',rows=>rows.forEach((r,i)=>{r[2]=i===0?1e100:0;r[3]=i===0?1e100:i===1?1e80:0;}));a.declaration.tariffs.forEach(t=>t.eur_kwh=2);const r=evaluate(a);assert.equal(r.demo.support.electricity_kwh.normal,r.demo.support.electricity_kwh.aquashift);assert.equal(r.demo.support.electricity_kwh.delta,1e80);assert.equal(r.demo.support.cost_eur.delta,2e80);assert.equal(r.demo.support.forecast_flagged_electricity_kwh.delta,1e80);
});
test('overflow, positive product underflow and nonzero CSV literal underflow reject',()=>{
 const a=fixture();patch(a,'schedule',rows=>rows.forEach(r=>r[2]=1e308));assert.throws(()=>evaluate(a),/finite numeric/);
 const b=fixture();patch(b,'schedule',rows=>rows.forEach(r=>r[2]=1e-200));b.declaration.tariffs.forEach(t=>t.eur_kwh=1e-200);assert.throws(()=>evaluate(b),/precision/);
 const c=fixture();patch(c,'schedule',rows=>rows[0][2]='1e-400');assert.throws(()=>evaluate(c),/precision/);
});
test('file/row bounds and malformed CSV preserve strict boundaries',()=>{
 const a=fixture();a.files.weather.text='x'.repeat(4*1024*1024+1);assert.throws(()=>evaluate(a),/4 MiB/);
 const b=fixture();patch(b,'day_forecast',rows=>{while(rows.length<8785)rows.push(rows[0]);});assert.throws(()=>evaluate(b),/row limit/);
 const c=fixture();c.files.schedule.text+='\r\n"unterminated';assert.throws(()=>evaluate(c),/CSV/);
});

test('raw declaration parsing rejects numeric overflow/underflow without interpreting strings',()=>{
 const raw=JSON.stringify(fixture().declaration);assert.deepEqual(parseRoadmapDeclaration('\uFEFF'+raw),JSON.parse(raw));
 for(const token of ['1e-400','-1e-400','1e400'])assert.throws(()=>parseRoadmapDeclaration(raw.replace('"eur_kwh":0.1',`"eur_kwh":${token}`)),/numeric/);
 assert.equal(parseRoadmapDeclaration(raw.replace('"eur_kwh":0.1','"eur_kwh":0e-400')).tariffs[0].eur_kwh,0);
 const strings={message:'1e-400, \"-1e400\", 1e9999',number:0};assert.deepEqual(parseRoadmapDeclaration(JSON.stringify(strings)),strings);
 assert.throws(()=>parseRoadmapDeclaration('{"x":01}'),SyntaxError);
});
