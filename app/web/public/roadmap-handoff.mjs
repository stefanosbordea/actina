import {isoHour} from './core.mjs';

const HOUR=3600000,MAX_FILE_BYTES=4*1024*1024;
const headers={weather:['time','shortwave_radiation','cloud_cover','temperature_2m','relative_humidity_2m'],predictions:['time','actual','predicted','baseline'],day_forecast:['date','hour','predicted_radiation','surplus_flag'],schedule:['date','hour','normal_power_kw','aquashift_power_kw','tank_level_m3','surplus_flag']};
const declarationKeys=['schema','kind','source_kind','source_label','utc_offset','radiation_time_semantics','date_hour_semantics','weather_units','power_semantics','tank_level_semantics','tank_capacity_m3','surplus_threshold_w_m2','surplus_comparison','test_period','tariffs','declared_links'];
const units={shortwave_radiation:'W/m2',cloud_cover:'percent',temperature_2m:'degC',relative_humidity_2m:'percent'};
const localClock=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Nicosia',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',hourCycle:'h23'});
const clone=value=>JSON.parse(JSON.stringify(value));
const finite=value=>typeof value==='number'&&Number.isFinite(value);
const fail=message=>{throw Error(`Roadmap handoff: ${message}`);};
function fields(value,keys,label){
 if(!value||typeof value!=='object'||Array.isArray(value))fail(`Declare ${label}.`);
 for(const key of Object.keys(value))if(!keys.includes(key))fail(`Unsupported ${label} field: ${key}.`);
 for(const key of keys)if(!Object.hasOwn(value,key))fail(`Missing ${label} field: ${key}.`);
}
function label(value,name,max=300){if(typeof value!=='string'||!value.trim()||value.length>max||/[\u0000-\u001f]/.test(value))fail(`Invalid ${name}.`);return value;}
function hash(value){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))fail('Retain lowercase SHA-256 file identities.');return value;}
function amount(value,name,min=0,max=Infinity){if(!finite(value)||value<min||value>max)fail(`Invalid ${name}.`);return value===0?0:value;}
function number(value,name,min=0,max=Infinity){const s=String(value??'').trim();if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(s))fail(`Invalid ${name}.`);const n=Number(s);if(n===0&&/[1-9]/.test(s.split(/[eE]/)[0]))fail(`${name} exceeds numeric precision.`);return amount(n,name,min,max);}
function instant(value,name){if(typeof value!=='string')fail(`Invalid ${name}.`);const parsed=isoHour(value);if(parsed.error)fail(`${name}: ${parsed.error}`);return parsed.epoch;}
function clockParts(epoch){const p=Object.fromEntries(localClock.formatToParts(epoch).map(x=>[x.type,x.value]));return {date:`${p.year}-${p.month}-${p.day}`,hour:Number(p.hour)};}
function demoTime(date,hour,offset){
 if(typeof date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(date)||!Number.isInteger(hour)||hour<0||hour>23)fail('Use an exact demo date and hour 0–23.');
 const epoch=instant(`${date}T${String(hour).padStart(2,'0')}:00:00${offset}`,'demo time');
 const same=at=>{const p=clockParts(at);return p.date===date&&p.hour===hour;};
 if(!same(epoch))fail('Demo date/hour offset does not match Europe/Nicosia.');
 if(same(epoch-HOUR)||same(epoch+HOUR))fail('Ambiguous duplicated local demo hour requires a separate time contract.');
 return epoch;
}
function sum(values){
 let total=0,correction=0;
 for(const value of values){const next=total+value;if(!finite(next))fail('Totals exceed finite numeric range.');correction+=Math.abs(total)>=Math.abs(value)?(total-next)+value:(value-next)+total;total=next;}
 const result=total+correction;if(!finite(result))fail('Totals exceed finite numeric range.');return result===0?0:result;
}
function product(a,b){const value=a*b;if(!finite(value)||(a!==0&&b!==0&&value===0))fail('Product exceeds finite numeric range or precision.');return value===0?0:value;}
function metrics(rows,column){
 if(!rows.length)return {rows:0,mae:null,rmse:null,bias:null};
 const errors=rows.map(row=>row[column]-row.actual),mean=values=>product(sum(values),1/rows.length);
 return {rows:rows.length,mae:mean(errors.map(Math.abs)),rmse:Math.sqrt(mean(errors.map(e=>product(e,e)))),bias:mean(errors)};
}
function paired(rows,weight){
 return {normal:sum(rows.map(r=>product(r.normal_power_kw,weight(r)))),aquashift:sum(rows.map(r=>product(r.aquashift_power_kw,weight(r)))),delta:sum(rows.map(r=>product(r.aquashift_power_kw-r.normal_power_kw,weight(r))))};
}
function support(rows,powerSemantics){
 const mean=powerSemantics==='interval_mean'&&rows.length>0;
 return {hours:rows.length,electricity_kwh:mean?paired(rows,()=>1):null,cost_eur:mean&&rows.every(r=>r.tariff_eur_kwh!==null)?paired(rows,r=>r.tariff_eur_kwh):null,forecast_flagged_electricity_kwh:mean&&rows.every(r=>r.forecast_flag!==null)?paired(rows,r=>r.forecast_flag):null};
}
function csv(file,role,Papa){
 fields(file,['name','text','sha256'],`${role} file`);label(file.name,`${role} filename`,255);hash(file.sha256);
 if(typeof file.text!=='string')fail(`Retain ${role} CSV text.`);
 const bytes=new TextEncoder().encode(file.text).byteLength;if(bytes>MAX_FILE_BYTES)fail(`${role} exceeds 4 MiB.`);
 const parsed=Papa.parse(file.text,{delimiter:',',skipEmptyLines:'greedy'});
 if(parsed.errors?.length)fail(`${role} has CSV parsing errors.`);
 if(!Array.isArray(parsed.data)||!Array.isArray(parsed.data[0]))fail(`${role} needs its declared CSV header.`);
 const matrix=parsed.data,keys=matrix[0].map(x=>String(x).trim().replace(/^\uFEFF/,'')),expected=headers[role];
 if(keys.length!==expected.length||new Set(keys).size!==keys.length||keys.some(key=>!expected.includes(key)))fail(`${role} headers must match the declared schema; unsupported columns or totals are not accepted.`);
 if(matrix.length-1>(role==='weather'||role==='predictions'?30000:8784))fail(`${role} exceeds its row limit.`);
 const rows=matrix.slice(1).map(values=>{if(values.length!==keys.length)fail(`${role} CSV field count does not match its header.`);return Object.fromEntries(keys.map((key,i)=>[key,values[i]]));});
 return {rows,identity:{name:file.name,sha256:file.sha256,bytes}};
}

export function parseRoadmapDeclaration(text){
 if(typeof text!=='string')fail('Retain declaration JSON text.');
 const raw=text.replace(/^\uFEFF/,''),value=JSON.parse(raw);
 const unquoted=raw.replace(/"(?:\\.|[^"\\])*"/g,'""');
 for(const [token]of unquoted.matchAll(/-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g)){
  const n=Number(token);if(!Number.isFinite(n)||(n===0&&/[1-9]/.test(token.split(/[eE]/)[0])))fail('Declaration number exceeds finite numeric range or precision.');
 }
 return value;
}

export function evaluateRoadmapHandoff({declaration:d,files,Papa}){
 fields(d,declarationKeys,'declaration');
 if(d.schema!==1||d.kind!=='roadmap_handoff_declaration')fail('Use a schema-1 roadmap_handoff_declaration.');
 if(!['illustrative_scenario','reviewer_supplied'].includes(d.source_kind))fail('Declare the source kind.');label(d.source_label,'source label');
 if(typeof d.utc_offset!=='string'||!/^[-+]\d{2}:\d{2}$/.test(d.utc_offset))fail('Declare an explicit fixed demo UTC offset.');
 instant(`2026-01-01T00:00:00${d.utc_offset}`,'demo UTC offset');
 if(d.radiation_time_semantics!=='interval_start'||d.date_hour_semantics!=='interval_start')fail('Only declared interval-start labels are supported.');
 fields(d.weather_units,Object.keys(units),'weather units');for(const [key,unit]of Object.entries(units))if(d.weather_units[key]!==unit)fail(`Declare ${key} in ${unit}.`);
 if(!['interval_mean','point_sample'].includes(d.power_semantics))fail('Declare interval_mean or point_sample power.');
 if(!['aquashift_interval_end','unspecified'].includes(d.tank_level_semantics))fail('Declare the supplied tank meaning.');
 if(d.tank_capacity_m3!==null)amount(d.tank_capacity_m3,'tank capacity',Number.MIN_VALUE);
 amount(d.surplus_threshold_w_m2,'surplus threshold',0,2000);
 if(!['greater_than','at_or_above'].includes(d.surplus_comparison))fail('Declare the threshold comparison.');
 fields(d.test_period,['start','end'],'test period');const start=instant(d.test_period.start,'test start'),end=instant(d.test_period.end,'test end'),expectedHours=(end-start)/HOUR;
 if(expectedHours<=0||expectedHours>30000)fail('Test period must contain 1–30,000 elapsed hours.');
 fields(d.declared_links,['schedule_forecast_sha256','weather_sha256'],'declared links');for(const value of Object.values(d.declared_links))hash(value);
 fields(files,Object.keys(headers),'files');if(typeof Papa?.parse!=='function')fail('A CSV parser is required.');
 const parsed=Object.fromEntries(Object.keys(headers).map(role=>[role,csv(files[role],role,Papa)]));
 if(d.declared_links.schedule_forecast_sha256!==files.day_forecast.sha256||d.declared_links.weather_sha256!==files.weather.sha256)fail('Declared file links do not match retained file identities.');
 const weather=new Map(),predictions=new Map(),forecast=new Map(),schedule=new Map();
 function put(map,epoch,row,role){if(map.has(epoch))fail(`Duplicate ${role} instant.`);map.set(epoch,row);}
 for(const row of parsed.weather.rows){
  const epoch=instant(row.time,'weather time');
  put(weather,epoch,{shortwave_radiation:number(row.shortwave_radiation,'weather radiation',0,2000),cloud_cover:number(row.cloud_cover,'cloud cover',0,100),temperature_2m:number(row.temperature_2m,'temperature',-Infinity),relative_humidity_2m:number(row.relative_humidity_2m,'relative humidity',0,100)},'weather');
 }
 for(const row of parsed.predictions.rows){
  const epoch=instant(row.time,'prediction time');if(epoch<start||epoch>=end)fail('Prediction is outside the declared test period.');
  const value=Object.fromEntries(['actual','predicted','baseline'].map(key=>[key,number(row[key],`prediction ${key}`,0,2000)]));
  if(weather.has(epoch)&&Math.abs(value.actual-weather.get(epoch).shortwave_radiation)>1e-6)fail('Prediction actual contradicts supplied weather radiation.');
  put(predictions,epoch,value,'prediction');
 }
 const flagged=radiation=>Number(d.surplus_comparison==='greater_than'?radiation>d.surplus_threshold_w_m2:radiation>=d.surplus_threshold_w_m2);
 for(const role of ['day_forecast','schedule'])for(const raw of parsed[role].rows){
  const date=String(raw.date).trim(),hourText=String(raw.hour).trim();if(!/^\d{1,2}$/.test(hourText))fail('Use an integer demo hour 0–23.');
  const hour=Number(hourText),epoch=demoTime(date,hour,d.utc_offset),flagText=String(raw.surplus_flag).trim();if(!/^[01]$/.test(flagText))fail('Surplus flags must be explicit 0 or 1.');
  const row={date,hour,flag:Number(flagText)};
  if(role==='day_forecast'){
   row.predicted_radiation=number(raw.predicted_radiation,'demo radiation',0,2000);if(row.flag!==flagged(row.predicted_radiation))fail('Demo surplus flag contradicts its declared radiation threshold.');put(forecast,epoch,row,'demo forecast');
  }else{for(const key of ['normal_power_kw','aquashift_power_kw','tank_level_m3'])row[key]=number(raw[key],key);put(schedule,epoch,row,'schedule');}
 }
 for(const [epoch,row]of schedule)if(forecast.has(epoch)&&row.flag!==forecast.get(epoch).flag)fail('Schedule flag contradicts the same supplied demo forecast hour.');
 const tariffs=new Map();
 if(d.tariffs!==null){
  if(!Array.isArray(d.tariffs)||d.tariffs.length>8784)fail('Tariffs must be null or at most 8,784 declared hourly rows.');
  for(const row of d.tariffs){fields(row,['date','hour','eur_kwh'],'tariff row');const epoch=demoTime(row.date,row.hour,d.utc_offset);if(!schedule.has(epoch))fail('Tariff is outside supplied schedule hours.');put(tariffs,epoch,amount(row.eur_kwh,'tariff'),'tariff');}
 }
 const accepted=[...predictions].filter(([epoch])=>weather.has(epoch)).sort(([a],[b])=>a-b).map(([,row])=>row),missingTimes=[],unmatchedTimes=[];
 for(let epoch=start;epoch<end;epoch+=HOUR)if(!predictions.has(epoch)||!weather.has(epoch))missingTimes.push(new Date(epoch).toISOString());
 for(const epoch of predictions.keys())if(!weather.has(epoch))unmatchedTimes.push(new Date(epoch).toISOString());unmatchedTimes.sort();
 const rows=[...new Set([...forecast.keys(),...schedule.keys()])].sort((a,b)=>a-b).map(epoch=>{
  const f=forecast.get(epoch),s=schedule.get(epoch),local=f??s;
  return {time:new Date(epoch).toISOString(),date:local.date,hour:local.hour,predicted_radiation:f?.predicted_radiation??null,forecast_flag:f?.flag??null,normal_power_kw:s?.normal_power_kw??null,aquashift_power_kw:s?.aquashift_power_kw??null,tank_level_m3:s?.tank_level_m3??null,schedule_flag:s?.flag??null,tariff_eur_kwh:tariffs.get(epoch)??null};
 });
 const byDate=new Map();for(const row of rows){if(!byDate.has(row.date))byDate.set(row.date,[]);byDate.get(row.date).push(row);}
 const days=[...byDate].sort(([a],[b])=>a.localeCompare(b)).map(([date,dayRows])=>{
  const f=new Set(dayRows.filter(r=>r.forecast_flag!==null).map(r=>r.hour)),s=new Set(dayRows.filter(r=>r.schedule_flag!==null).map(r=>r.hour)),matched=dayRows.filter(r=>r.forecast_flag!==null&&r.schedule_flag!==null).length;
  const coverage={status:f.size===24&&s.size===24?'complete':'partial',expected_hours:24,forecast_hours:f.size,schedule_hours:s.size,matched_hours:matched,missing_forecast_hours:Array.from({length:24},(_,i)=>i).filter(h=>!f.has(h)),missing_schedule_hours:Array.from({length:24},(_,i)=>i).filter(h=>!s.has(h))};
  return {date,coverage,totals:coverage.status==='complete'?support(dayRows,d.power_semantics):null};
 });
 const pairedRows=rows.filter(r=>r.schedule_flag!==null),tankValues=pairedRows.map(r=>r.tank_level_m3),above=d.tank_capacity_m3===null||!tankValues.length?null:tankValues.filter(v=>v>d.tank_capacity_m3).length;
 const coverage={status:days.length&&days.every(day=>day.coverage.status==='complete')?'complete':'partial',selected_dates:days.map(day=>day.date),expected_hours:days.length*24,forecast_hours:forecast.size,schedule_hours:schedule.size,matched_hours:rows.filter(r=>r.forecast_flag!==null&&r.schedule_flag!==null).length};
 const demoPredictionDifferences=[...forecast].filter(([epoch,row])=>predictions.has(epoch)&&row.predicted_radiation!==predictions.get(epoch).predicted).length;
 const gaps=[{code:'water_comparability_unestablished',message:'One supplied tank trace does not establish normal-plan stock, produced water or delivered water; lower electricity is not a matched-water benefit.'},{code:'forecast_attribution_unestablished',message:'Normal versus AquaShift is a supplied policy comparison; the forecast contribution is not isolated.'},{code:'provenance_unverified',message:'Source, training, baseline origin, forecast issue and feature availability remain unverified; file links are caller declarations.'}];
 if(demoPredictionDifferences)gaps.push({code:'different_supplied_predictions',count:demoPredictionDifferences,message:`${demoPredictionDifferences} overlapping demo/test hours contain different supplied predictions; their model-version linkage is unverified.`});
 if(missingTimes.length)gaps.push({code:'partial_test_coverage',message:`${missingTimes.length} declared test hours have no matched weather/prediction pair.`});
 if(unmatchedTimes.length)gaps.push({code:'missing_weather',message:`${unmatchedTimes.length} supplied prediction hours lack matching weather and are excluded from metrics.`});
 if(coverage.status==='partial')gaps.push({code:'partial_demo_coverage',message:'At least one selected demo date lacks complete forecast and schedule hours; whole-day totals are unavailable.'});
 if(d.power_semantics==='point_sample')gaps.push({code:'point_power',message:'Point power samples do not establish electricity or cost totals.'});
 if(pairedRows.some(r=>r.tariff_eur_kwh===null))gaps.push({code:'missing_tariffs',message:'Some supplied schedule hours lack tariffs; complete-support cost is unknown.'});
 if(pairedRows.some(r=>r.forecast_flag===null))gaps.push({code:'missing_demo_forecast',message:'Some supplied schedule hours lack matching demo forecasts; forecast-flagged electrical load is unknown.'});
 if(above)gaps.push({code:'tank_above_declared_capacity',message:`${above} supplied tank readings exceed the declared capacity.`});
 if(d.tank_level_semantics==='unspecified')gaps.push({code:'tank_meaning_unspecified',message:'The supplied tank trace has no declared plan/boundary interpretation.'});
 return {schema:1,kind:'roadmap_handoff_evaluation',declaration:clone(d),file_identities:Object.fromEntries(Object.entries(parsed).map(([role,value])=>[role,value.identity])),forecast:{model:metrics(accepted,'predicted'),baseline:metrics(accepted,'baseline'),coverage:{status:missingTimes.length?'partial':'complete',expected_hours:expectedHours,supplied_hours:predictions.size,matched_hours:accepted.length,missing_times:missingTimes,unmatched_times:unmatchedTimes}},demo:{coverage,support:support(pairedRows,d.power_semantics),days,rows},tank:{semantics:d.tank_level_semantics,capacity_m3:d.tank_capacity_m3,min_m3:tankValues.length?Math.min(...tankValues):null,max_m3:tankValues.length?Math.max(...tankValues):null,above_capacity_hours:above},lineage:{status:'caller_declared'},water_comparability:{status:'not_established'},forecast_attribution:{status:'not_established'},gaps,scope:['Retained supplied files; their SHA-256 bytes must be verified by the caller before evaluation.','Prediction metrics use only matched supplied weather and prediction hours; missing hours remain missing.','Electrical support totals cover supplied schedule hours only; complete selected dates are reported separately.','Mean kW over one elapsed hour gives kWh; point samples are not integrated.','Forecast flags describe radiation, not plant-eligible solar or recovered curtailment.','Supplied tank readings do not establish water conservation, comparable service or between-reading safety.','No forecast, plant model or schedule is generated; no source authenticity or operating authority is established.']};
}
