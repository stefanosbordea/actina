import {parseRoadmapDeclaration} from './roadmap-handoff.mjs';
import {pilotTime} from './pilot.mjs';
import {compareSequenceRevision,sequenceWaterServiceModel} from './sequence-revision.mjs';
import {assessWaterService,compareProductionEnergy} from './paired-water-service.mjs';

const roles=['case','returned','weather','candidate_forecast','control_forecast','tariffs'],HOUR=3600000;
const clockKeys=['forecast_issue_time','forecast_first_observed_time','features_available_time','plan_first_observed_time'];
const clockLabels={forecast_issue_time:'forecast issue',forecast_first_observed_time:'first forecast observation',features_available_time:'feature availability',plan_first_observed_time:'first plan observation'};
const clone=value=>JSON.parse(JSON.stringify(value)),fail=message=>{throw Error(`Forecast decision: ${message}`);};
function fields(value,keys,label,optional=[]){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!keys.includes(k)&&!optional.includes(k))||keys.some(k=>!Object.hasOwn(value,k)))fail(`Supply exactly the ${label} fields.`);
}
function label(value,name,max=300){if(typeof value!=='string'||!value.trim()||value.length>max||/[\u0000-\u001f]/.test(value))fail(`Invalid ${name}.`);}
function hash(value){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))fail('Use lowercase SHA-256 identities.');}
function time(value,name){const p=pilotTime(value);if(p.error)fail(`${name}: ${p.error}`);return p.epoch;}
function sum(values){
 let total=0,correction=0;for(const value of values){const next=total+value;if(!Number.isFinite(next))fail('Totals exceed finite numeric range.');correction+=Math.abs(total)>=Math.abs(value)?(total-next)+value:(value-next)+total;total=next;}
 const value=total+correction;if(!Number.isFinite(value))fail('Totals exceed finite numeric range.');return value===0?0:value;
}
function product(a,b){const value=a*b;if(!Number.isFinite(value)||(a!==0&&b!==0&&value===0))fail('Product exceeds finite numeric range or precision.');return value===0?0:value;}
function number(value,name,max=Infinity){
 const s=String(value??'').trim(),n=Number(s);
 if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(s)||!Number.isFinite(n)||n<0||n>max||(n===0&&/[1-9]/.test(s.split(/[eE]/)[0])))fail(`Invalid ${name} or numeric precision.`);return n;
}
function series(file,column,times,Papa,max=Infinity){
 const parsed=Papa.parse(file.text,{delimiter:',',skipEmptyLines:'greedy'});
 if(parsed.errors?.length||!Array.isArray(parsed.data?.[0]))fail(`${file.name}: malformed CSV.`);
 const [head,...rows]=parsed.data,keys=head.map(x=>String(x).trim().replace(/^\uFEFF/,''));
 if(keys.length!==2||new Set(keys).size!==2||!keys.includes('time')||!keys.includes(column))fail(`${file.name}: columns must be exactly time,${column}.`);
 if(rows.length!==times.length)fail(`${file.name}: supply exactly ${times.length} case hours.`);
 const expected=new Set(times),values=new Map();
 const name={radiation_w_m2:'realized radiation',predicted_radiation_w_m2:'predicted radiation',eur_kwh:'tariff'}[column];
 for(const row of rows){if(row.length!==2)fail(`${file.name}: wrong field count.`);const epoch=time(row[keys.indexOf('time')],'CSV time');if(!expected.has(epoch)||values.has(epoch))fail(`${file.name}: outside or duplicate case hour.`);values.set(epoch,number(row[keys.indexOf(column)],name,max));}
 return times.map(t=>values.get(t));
}
function errors(predicted,actual){
 const e=predicted.map((v,i)=>v-actual[i]),mean=values=>product(sum(values),1/e.length);
 return {rows:e.length,mae:mean(e.map(Math.abs)),rmse:Math.sqrt(mean(e.map(v=>product(v,v)))),bias:mean(e)};
}

/** Evaluate retained supplied alternatives. Declarations never establish execution authority. */
export async function evaluateForecastDecisionReview(packet,{sha256,Papa}){
 fields(packet,['schema','kind','declaration_file','files'],'review',['createdAt','results','note']);
 if(packet.schema!==1||packet.kind!=='forecast_decision_review')fail('Use a schema-1 forecast_decision_review.');
 fields(packet.files,roles,'files');if(typeof sha256!=='function'||typeof Papa?.parse!=='function')fail('File hashing and CSV parsing are required.');
 if(new TextEncoder().encode(JSON.stringify(packet)).byteLength>20*1024*1024)fail('Review exceeds 20 MiB.');
 async function retained(file){
  fields(file,['name','text','sha256'],'retained file');label(file.name,'filename',255);hash(file.sha256);
  if(typeof file.text!=='string')fail('Retain original UTF-8 text.');const bytes=new TextEncoder().encode(file.text);
  if(bytes.byteLength>4*1024*1024)fail('Each raw file must be at most 4 MiB.');
  if(new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes)!==file.text)fail('Retained text must be valid UTF-8.');
  if(await sha256(file.text)!==file.sha256)fail(`Retained hash does not match ${file.name}.`);return clone(file);
 }
 const [declaration_file,...raw]=await Promise.all([retained(packet.declaration_file),...roles.map(role=>retained(packet.files[role]))]);
 const files=Object.fromEntries(roles.map((role,i)=>[role,raw[i]])),d=parseRoadmapDeclaration(declaration_file.text);
 fields(d,['schema','kind','source_kind','source_label','decision_cutoff','specific_energy_kwh_m3','candidate','control'],'declaration');
 if(d.schema!==1||d.kind!=='forecast_decision_declaration'||!['illustrative_scenario','reviewer_supplied'].includes(d.source_kind))fail('Use a schema-1 declared source.');label(d.source_label,'source label');
 const sec=d.specific_energy_kwh_m3;
 if(sec!==null&&(typeof sec!=='number'||!Number.isFinite(sec)||sec<=0))fail('Specific energy must be positive and finite, or null.');
 const cutoff=time(d.decision_cutoff,'decision cutoff'),methodGaps=[],timingGaps=[];let late=false,missing=false;
 for(const arm of ['candidate','control']){
  const r=d[arm];fields(r,['forecast_sha256','plan_sha256','case_sha256','tariffs_sha256','controller_sha256','settings_sha256','randomness',...clockKeys],`${arm} run`);
  for(const k of ['forecast_sha256','plan_sha256','case_sha256','tariffs_sha256','controller_sha256','settings_sha256'])hash(r[k]);label(r.randomness,'randomness');
  if(r.forecast_sha256!==files[`${arm}_forecast`].sha256||r.plan_sha256!==files[arm==='control'?'case':'returned'].sha256)fail(`${arm} forecast/plan link does not match retained bytes.`);
  for(const [key,role]of [['case_sha256','case'],['tariffs_sha256','tariffs']])if(r[key]!==files[role].sha256)methodGaps.push(`${arm}: declared ${role} differs from the common evaluated file.`);
  const clocks={};for(const key of clockKeys){if(r[key]===null){missing=true;timingGaps.push(`${arm}: ${clockLabels[key]} not supplied.`);}else{clocks[key]=time(r[key],clockLabels[key]);if(clocks[key]>cutoff){late=true;timingGaps.push(`${arm}: ${clockLabels[key]} is after the common decision cutoff.`);}}}
  if(clocks.forecast_issue_time!==undefined&&clocks.forecast_first_observed_time!==undefined&&clocks.forecast_first_observed_time<clocks.forecast_issue_time)fail(`${arm}: first observation precedes declared issue.`);
 }
 for(const [key,name]of [['controller_sha256','controllers'],['settings_sha256','settings'],['randomness','randomness']])if(d.candidate[key]!==d.control[key])methodGaps.push(`Candidate and control declare different ${name}.`);
 const input=parseRoadmapDeclaration(files.case.text),identity=file=>({name:file.name,sha256:file.sha256});
 const comparison=compareSequenceRevision({input,block_index:0,caseIdentity:identity(files.case),csvText:files.returned.text,proposalIdentity:identity(files.returned),specific_energy_kwh_m3:sec,Papa});
 const a=comparison.original,b=comparison.revised,times=input.blocks.flatMap(block=>block.times.map(t=>time(t,'case time')));
 if(cutoff>=times[0])fail('Decision cutoff must precede the evaluated horizon.');
 const actual=series(files.weather,'radiation_w_m2',times,Papa,2000),candidate=series(files.candidate_forecast,'predicted_radiation_w_m2',times,Papa,2000),control=series(files.control_forecast,'predicted_radiation_w_m2',times,Papa,2000),prices=series(files.tariffs,'eur_kwh',times,Papa);
 const models={control:sequenceWaterServiceModel(a.inputs,a.result),candidate:sequenceWaterServiceModel(b.inputs,b.result)};
 const energy=sec===null?null:compareProductionEnergy({original:models.control,revised:models.candidate,specific_energy_kwh_m3:sec,tariffs:prices});
 const cost=energy?.cost_eur??null,result={schema:1,kind:'forecast_decision_evaluation',source_kind:d.source_kind,source_label:d.source_label,
  horizon:{start:a.result.start_time,end:a.result.end_time,hours:times.length},forecast:{candidate:errors(candidate,actual),control:errors(control,actual)},
  actions:{changed_hours:input.blocks.reduce((n,block,i)=>n+block.production.filter((v,j)=>v!==b.inputs.blocks[i].production[j]).length,0)},
  water_service:comparison.water_service,adequacy:{candidate:assessWaterService(models.candidate),control:assessWaterService(models.control)},
  energy:{electricity_kwh:energy?.electricity_kwh??null,cost_eur:cost,proof:energy?.proof??null,matched_water_cost_reduction:cost!==null&&cost.delta<0&&comparison.water_service.status==='no_modeled_regression'},
  method:{status:methodGaps.length?'confounded_declaration':'same_declared_method',gaps:methodGaps},
  timing:{status:late?'late_declared':missing?'not_established':'declared_before_cutoff',gaps:timingGaps},forecast_attribution:{status:'not_established'},
  file_identities:Object.fromEntries([['declaration',declaration_file],...Object.entries(files)].map(([role,file])=>[role,{...identity(file),bytes:new TextEncoder().encode(file.text).byteLength}])),
  scope:['Supplied paired-plan difference on one complete common realization. No forecast fitting, scheduling or plant command.',
   'Forecast errors measure the same supplied realized radiation hours; radiation is not eligible plant solar or recovered curtailment.',
   'Exact water criteria apply to the declared uniform-rate model. Relative nonregression and absolute demand, reserve and terminal adequacy remain separate; neither establishes operating readiness.',
   'Modeled electricity integrates normalized effective rates, including spill, times one declared constant specific energy; modeled tariff cost uses the same hourly prices. Exact fractions remain in the evidence; numeric values are rounded display approximations.',
   'Method and timing are caller declarations. Hashes identify bytes, not execution, issuance, training or feature authority. Even matching declarations do not establish causal forecast attribution.']};
 const record={schema:1,kind:'forecast_decision_review',declaration_file,files,createdAt:new Date().toISOString(),results:clone(result)};
 if(new TextEncoder().encode(JSON.stringify(record,null,2)+'\n').byteLength>20*1024*1024)fail('Recomputed review exceeds 20 MiB.');
 return {record,result};
}
