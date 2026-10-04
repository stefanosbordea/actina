// Whole-period execution accounting. No point-sample integration or plan generation.
import {replayPlan} from './plan-resilience.mjs';
import {pilotTime} from './pilot.mjs';
import {evaluateTemporalWater} from './temporal-water.mjs';

const HOUR=3600000,MAX_RECORDS=4096;
const roles={energy:'kWh',produced:'m3',delivered:'m3',other_inflow:'m3',other_outflow:'m3',spill:'m3'};
const zeroRoles=['other_inflow','other_outflow','spill'];
const waterKeys=['produced','delivered','other_inflow','other_outflow','spill','initial_storage','final_storage'];
const finite=n=>typeof n==='number'&&Number.isFinite(n);
const fail=message=>{throw Error(`Execution review: ${message}`);};
const copy=value=>JSON.parse(JSON.stringify(value));
function fields(value,allowed,label){if(!value||typeof value!=='object'||Array.isArray(value))fail(`${label} must be an object.`);for(const key of Object.keys(value))if(!allowed.includes(key))fail(`Unsupported ${label} field: ${key}.`);}
function label(value,name,max=300){if(typeof value!=='string'||!value.trim()||value.length>max||/[\u0000-\u001f]/.test(value))fail(`Declare ${name} in 1–${max} characters.`);return value;}
function hash(value){if(typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value))fail('Retain an exact SHA-256 identity.');return value;}
function identity(value){fields(value,['name','sha256'],'file identity');return {name:label(value.name,'filename',255),sha256:hash(value.sha256)};}
function epoch(value){const parsed=pilotTime(value);if(parsed.error)fail(parsed.error);return parsed.epoch;}
function sum(values){let total=0,correction=0;for(const value of values){const next=total+value;if(!finite(next))fail('Accounting exceeds finite numeric range.');correction+=Math.abs(total)>=Math.abs(value)?(total-next)+value:(value-next)+total;total=next;}const result=total+correction;if(!finite(result))fail('Accounting exceeds finite numeric range.');return result===0?0:result;}
function product(a,b){const n=a*b;if(!finite(n)||(a>0&&b>0&&n===0))fail('Modeled energy exceeds finite numeric range or precision.');return n;}
function bounded(value){if(value.lower===null&&value.upper===null)return null;if(!finite(value.lower)||!finite(value.upper)||value.lower<0||value.upper<value.lower)fail('Supply ordered nonnegative finite bounds, or paired null bounds.');return {lower:value.lower,upper:value.upper};}
const point=n=>({lower:[n],upper:[n]});
function range(expression){if(!expression)return null;const lower=sum(expression.lower),upper=sum(expression.upper);if(lower>upper)fail('Accounting bounds exceed numeric precision.');return {lower,upper};}
function difference(expression,terms){return expression&&terms?range({lower:[...expression.lower,...terms.map(n=>-n)],upper:[...expression.upper,...terms.map(n=>-n)]}):null;}
function consistency(value){return !value?'unknown':value.lower>0||value.upper<0?'different':'compatible';}

export function makeExecutionCase(args){
 fields(args,['schema','kind','input','unit_capacity_m3_h','specific_energy_kwh_m3','identity'],'execution case');
 if(('schema'in args||'kind'in args)&&(args.schema!==1||args.kind!=='fixed_plan_execution_case'))fail('Use a schema-1 fixed_plan_execution_case.');
 const input=args.input,unit=args.unit_capacity_m3_h,sec=args.specific_energy_kwh_m3;
 if(!finite(unit)||unit<=0)fail('Declared unit capacity must be positive and finite.');
 if(sec!==null&&(!finite(sec)||sec<=0))fail('Specific energy must be positive and finite, or null.');
 if(!input||!Array.isArray(input.production)||input.production.length!==24||Array.from(input.production).some(n=>!finite(n)||n<0||n>unit))fail('Supply 24 production values within the declared unit capacity.');
 if((input.startHour??0)!==0||input.scenario?.restart!==undefined)fail('Execution accounting requires the entire 24-hour plan, without a restart.');
 const hashes=args.identity;fields(hashes,Object.keys(hashes??{}),'source identity');
 if(!Object.keys(hashes).length||Object.keys(hashes).length>32)fail('Retain 1–32 named source hashes.');
 for(const [name,value]of Object.entries(hashes)){if(!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$/.test(name))fail('Unsupported source hash name.');hash(value);}
 const replay=replayPlan(input);if(replay.rows.length!==24)fail('Execution accounting requires 24 complete elapsed hours.');
 if(sec!==null)sum(replay.rows.map(row=>product(row.available_production_m3,sec)));
 return {schema:1,kind:'fixed_plan_execution_case',input:copy(input),unit_capacity_m3_h:unit,specific_energy_kwh_m3:sec,identity:copy(hashes)};
}

export function executionMeasurementTemplate({executionCase,case_sha256}){
 const c=makeExecutionCase(executionCase),start=c.input.times[0],end=new Date(epoch(start)+24*HOUR).toISOString();hash(case_sha256);
 return {schema:1,kind:'plant_execution_measurements',case_sha256,source_kind:'reviewer_supplied',source_label:'',plant_mapping:'',tank_mapping:'',electricity_basis:'gross_plant_load',review_as_of:end,
  streams:Object.entries(roles).map(([role,unit])=>({role,unit,semantics:'interval_total',readings:[{start,end,available_at:end,lower:null,upper:null}]})),declared_zero:[],tank:[start,end].map(time=>({time,available_at:time,lower:null,upper:null}))};
}

export function evaluateExecution({executionCase,caseIdentity,source,sourceIdentity}){
 const c=makeExecutionCase(executionCase),caseFile=identity(caseIdentity),sourceFile=identity(sourceIdentity),replay=replayPlan(c.input),start=epoch(c.input.times[0]),end=start+24*HOUR;
 fields(source,['schema','kind','case_sha256','source_kind','source_label','plant_mapping','tank_mapping','electricity_basis','review_as_of','streams','declared_zero','tank'],'measurement source');
 if(source.schema!==1||source.kind!=='plant_execution_measurements')fail('Use schema-1 plant_execution_measurements.');
 if(source.case_sha256!==caseFile.sha256)fail('Measurement source belongs to a different frozen case.');
 if(!['illustrative_scenario','reviewer_supplied'].includes(source.source_kind))fail('Declare the source kind.');
 for(const key of ['source_label','plant_mapping','tank_mapping'])label(source[key],key);
 if(source.electricity_basis!=='gross_plant_load')fail('Gross plant electricity is required; grid imports or point power alone are not the plant total.');
 const cutoff=epoch(source.review_as_of),issues=[],coverage={},expressions={},streams=new Map(),temporalStreams=new Map();
 const issue=(role,code,message)=>issues.push({role,code,message});
 if(!Array.isArray(source.streams)||source.streams.length>6||!Array.isArray(source.tank)||!Array.isArray(source.declared_zero))fail('Supply streams, declared_zero and tank arrays.');
 const zeros=new Set(source.declared_zero);if(zeros.size!==source.declared_zero.length||[...zeros].some(role=>!zeroRoles.includes(role)))fail('Explicit zero is supported only once for other_inflow, other_outflow and spill.');
 let count=source.tank.length;
 for(const stream of source.streams){
  fields(stream,['role','unit','semantics','no_reset','readings'],'stream');
  if(!Object.hasOwn(roles,stream.role)||stream.unit!==roles[stream.role])fail('Use supported roles with m3 volumes or kWh energy, not point power or flow rates.');
  if(streams.has(stream.role)||zeros.has(stream.role))fail('Each role must have one stream or one explicit zero declaration.');
  if(!['interval_total','cumulative_counter'].includes(stream.semantics))fail('Use measured interval totals or cumulative counters; point samples cannot be integrated.');
  if(stream.semantics==='interval_total'&&Object.hasOwn(stream,'no_reset'))fail('no_reset applies only to cumulative counters.');
  if(stream.semantics==='cumulative_counter'&&![true,false,null].includes(stream.no_reset))fail('Declare counter no_reset as true, false or null.');
  if(!Array.isArray(stream.readings))fail('Stream readings must be an array.');count+=stream.readings.length;streams.set(stream.role,stream);
 }
 if(count>MAX_RECORDS)fail(`Supply at most ${MAX_RECORDS} measurement records.`);
 function read(row,interval){
  fields(row,interval?['start','end','available_at','lower','upper']:['time','available_at','lower','upper'],'measurement');
  const a=epoch(interval?row.start:row.time),b=interval?epoch(row.end):a,available=epoch(row.available_at),bounds=bounded(row);
  if(a<start||b>end||a>end||b<a||(interval&&a===b))fail('Measurements must lie within the exact plan horizon, with positive interval durations.');
  if(available<b)fail('A total or reading cannot be available before its measurement ends.');
  return {start:a,end:b,available,bounds};
 }
 for(const role of Object.keys(roles)){
  expressions[role]=null;const stream=streams.get(role),report={status:'unknown',semantics:stream?.semantics??null,known_hours:0,known_support:null,late_records:0,unknown_records:0};coverage[role]=report;
  if(zeros.has(role)){expressions[role]=point(0);Object.assign(report,{status:'declared_zero',semantics:'declared_zero',known_hours:24,known_support:{lower:0,upper:0}});continue;}
  if(!stream){issue(role,'missing_role','No measurement or explicit zero declaration supplied.');continue;}
  const interval=stream.semantics==='interval_total',rows=Array.from(stream.readings,row=>read(row,interval)).sort((a,b)=>a.start-b.start||a.end-b.end);
  report.late_records=rows.filter(row=>row.available>cutoff).length;report.unknown_records=rows.filter(row=>row.available<=cutoff&&!row.bounds).length;
  const conflict=rows.some((row,index)=>index&&(interval?row.start<rows[index-1].end:row.start===rows[index-1].start));
  temporalStreams.set(role,{semantics:stream.semantics,no_reset:stream.no_reset,rows,conflict});
  if(conflict){issue(role,'conflicting_records','Overlapping or duplicate records cannot establish an unambiguous total.');continue;}
  if(interval){
   const known=rows.filter(row=>row.available<=cutoff&&row.bounds),expression={lower:known.map(row=>row.bounds.lower),upper:known.map(row=>row.bounds.upper)};
   report.known_hours=sum(known.map(row=>(row.end-row.start)/HOUR));report.known_support=known.length?range(expression):null;
   const complete=known.length>0&&known[0].start===start&&known.at(-1).end===end&&known.every((row,index)=>!index||row.start===known[index-1].end);
   if(complete){expressions[role]=expression;report.status='complete';}else {report.status=known.length?'partial':'unknown';issue(role,'incomplete_coverage','Missing, late or unknown intervals leave the whole-period total unknown.');}
  }else{
   if(stream.no_reset!==true){issue(role,'reset_ambiguity','A cumulative total requires an explicit no-reset declaration.');continue;}
   const known=rows.filter(row=>row.available<=cutoff&&row.bounds);
   if(!known.length||known[0].start!==start||known.at(-1).start!==end){issue(role,'missing_boundary','Both exact horizon counter endpoints must be known at the cutoff.');continue;}
   const lower=known.map(row=>row.bounds.lower),upper=known.map(row=>row.bounds.upper);
   for(let i=1;i<lower.length;i++)lower[i]=Math.max(lower[i],lower[i-1]);
   for(let i=upper.length-2;i>=0;i--)upper[i]=Math.min(upper[i],upper[i+1]);
   if(lower.some((value,index)=>value>upper[index])){issue(role,'infeasible_counter','Timely counter ranges have no nondecreasing, no-reset trajectory.');continue;}
   expressions[role]={lower:lower.at(-1)>upper[0]?[lower.at(-1),-upper[0]]:[0],upper:[upper.at(-1),-lower[0]]};
   Object.assign(report,{status:'complete',known_hours:24,known_support:range(expressions[role])});
  }
 }
 const tank=Array.from(source.tank,row=>read(row,false));if(tank.some(row=>row.start!==start&&row.start!==end))fail('Tank readings must be at the exact initial or final boundary.');
 for(const [role,time]of [['initial_storage',start],['final_storage',end]]){
  const rows=tank.filter(row=>row.start===time),report={status:'unknown',semantics:'tank_boundary',known_hours:null,known_support:null,late_records:rows.filter(row=>row.available>cutoff).length,unknown_records:rows.filter(row=>row.available<=cutoff&&!row.bounds).length};coverage[role]=report;expressions[role]=null;
  if(rows.length>1)issue(role,'conflicting_records','Duplicate tank boundary readings are ambiguous.');
  else if(rows.length!==1||rows[0].available>cutoff||!rows[0].bounds)issue(role,'missing_boundary','An exact, timely tank boundary reading is required.');
  else {expressions[role]={lower:[rows[0].bounds.lower],upper:[rows[0].bounds.upper]};report.status='complete';report.known_support=range(expressions[role]);if(rows[0].bounds.lower>c.input.capacity)issue(role,'outside_capacity','The entire declared tank range exceeds the case capacity.');}
 }
 const modelTerms={energy:c.specific_energy_kwh_m3===null?null:replay.rows.map(row=>product(row.available_production_m3,c.specific_energy_kwh_m3)),produced:replay.rows.map(row=>row.available_production_m3),delivered:replay.rows.map(row=>row.delivered_m3),spill:replay.rows.map(row=>row.spill_m3),other_inflow:[0],other_outflow:[0],initial_storage:[replay.totals.initial_storage_m3],final_storage:[replay.totals.final_storage_m3]};
 const modeled=Object.fromEntries(Object.entries(modelTerms).map(([key,terms])=>[key,terms?sum(terms):null])),measured=Object.fromEntries(Object.entries(expressions).map(([key,value])=>[key,range(value)])),differences=Object.fromEntries(Object.entries(expressions).map(([key,value])=>[key,difference(value,modelTerms[key])]));
 let residual=null;
 if(waterKeys.every(key=>expressions[key])){
  const positives=['initial_storage','produced','other_inflow'],negatives=['delivered','other_outflow','spill','final_storage'];
  residual=range({lower:[...positives.flatMap(key=>expressions[key].lower),...negatives.flatMap(key=>expressions[key].upper.map(n=>-n))],upper:[...positives.flatMap(key=>expressions[key].upper),...negatives.flatMap(key=>expressions[key].lower.map(n=>-n))]});
 }
 const balance=consistency(residual),waterStatus=waterKeys.map(key=>consistency(differences[key]));
 const temporal_water=evaluateTemporalWater({start,end,capacity:c.input.capacity,cutoff,streams:temporalStreams,tank,zeros});
 if(temporal_water.status==='inconsistent')issue('water','temporal_inconsistency','The timely water measurements cannot fit a nonnegative tank path within the declared capacity.');
 return {schema:1,kind:'plant_execution_review',case_identity:caseFile,source_identity:sourceFile,execution_case:c,source:copy(source),horizon:{start:new Date(start).toISOString(),end:new Date(end).toISOString()},modeled,measured,differences,coverage,
  water_balance:{status:balance==='different'?'inconsistent':balance,residual_m3:residual},volume_stock_comparison:{status:balance==='different'||waterStatus.includes('different')?'different':waterStatus.includes('unknown')?'unknown':'compatible'},temporal_water,issues,
  scope:['Measured interval totals and explicitly continuous counters cover one frozen 24-hour modeled reference. Different role partitions do not imply an hourly allocation.',
   'Bounds are caller-declared ranges, not confidence intervals or authenticated meter accuracy. Shared cumulative endpoints cancel once; other bounds are combined conservatively without an independence claim.',
   'Compatibility means declared bounds permit agreement, not proven equality, actual demand satisfaction, tank safety between readings, pressure or water quality.',
   'Gross plant electricity is distinct from grid imports or solar use. A lower energy total alone establishes no matched-water benefit, curtailment recovery or causal saving. No restoration energy is assumed.',
   'Mappings, no-reset and zero-flow declarations are caller statements. Hashes bind file identity, not provenance, historical issuance or plant operating permission. The caller must verify retained raw-file hashes.']};
}
