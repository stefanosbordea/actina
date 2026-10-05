import {validateRevisionCase} from './plan-revision.mjs';
import {replayPlan} from './plan-resilience.mjs';
import {pilotTime} from './pilot.mjs';
import {boundSolarTiming} from './solar-timing-bounds.mjs';
import {validateSequenceRevisionComparison} from './sequence-revision.mjs';
const HOUR=3600000;
const fail=message=>{throw Error(`Solar profile: ${message}`);};
const finite=value=>typeof value==='number'&&Number.isFinite(value);
function product(a,b){const result=a*b;if(!finite(result)||(a>0&&b>0&&result===0))fail('Energy or power exceeds finite numeric range or precision.');return result;}
function sumValues(values){
 let total=0,correction=0;
 for(const value of values){const next=total+value;if(!finite(next))fail('Difference bounds exceed finite numeric range.');correction+=Math.abs(total)>=Math.abs(value)?(total-next)+value:(value-next)+total;total=next;}
 const result=total+correction;if(!finite(result))fail('Difference bounds exceed finite numeric range.');return result===0?0:result;
}
const negative=value=>value===0?0:-value;
const signedProduct=(value,hours)=>value<0?negative(product(-value,hours)):product(value,hours);
const loadChange=pieces=>sumValues(pieces.map(p=>signedProduct(p.revised_power_kw-p.original_power_kw,p.duration_hours)));
const epoch=value=>{const r=pilotTime(value);if(r.error)fail(r.error);return r.epoch;};
function fields(value,allowed,label){if(!value||typeof value!=='object'||Array.isArray(value))fail(`${label} must be an object.`);for(const key of Object.keys(value))if(!allowed.includes(key))fail(`Unsupported ${label} field: ${key}.`);}
function label(value,name){if(typeof value!=='string'||!value.trim()||value.length>300||/[\u0000-\u001f]/.test(value))fail(`Declare ${name} in 1–300 characters.`);}
function context(comparison){
 if(comparison?.schema!==1||comparison.kind!=='fixed_plan_revision_comparison'||!/^[a-f0-9]{64}$/.test(comparison.case_identity?.sha256??''))fail('Use a validated returned-plan comparison.');
 const c=validateRevisionCase(comparison.revision_case),input=c.assessment.inputs,production=comparison.revised?.inputs?.production;
 if(!Array.isArray(production)||production.length!==24||production.some(v=>!finite(v)||v<0||v>c.unit_capacity_m3_h))fail('Invalid returned production.');
 const original=replayPlan(input),revised=replayPlan({...input,production}),base=epoch(input.times[0]);
 const outage=original.scenario.outage;
 return {sec:c.specific_energy_kwh_m3,original,revised,times:input.times,originalProduction:input.production,revisedProduction:production,productionMultiplier:original.scenario.production_multiplier,
  outages:outage?[{start:base+outage.start_hour*HOUR,end:base+(outage.start_hour+outage.duration_hours)*HOUR}]:[],start:base+original.start_hour*HOUR,end:base+24*HOUR,maxIntervals:4096};
}
function sequenceContext(comparison){
 const checked=validateSequenceRevisionComparison(comparison),input=checked.original.inputs;
 return {sec:checked.specific_energy_kwh_m3,original:checked.original.result,revised:checked.revised.result,times:input.blocks.flatMap(block=>block.times),
  originalProduction:input.blocks.flatMap(block=>block.production),revisedProduction:checked.revised.inputs.blocks.flatMap(block=>block.production),productionMultiplier:checked.original.result.scenario.production_multiplier,
  outages:(input.outages??[]).map(outage=>({start:epoch(outage.start),end:epoch(outage.end)})),start:epoch(checked.original.result.start_time),end:epoch(checked.original.result.end_time),maxIntervals:8784};
}
function template(comparison,semantics,x){
 if(!['constant_power','interval_energy'].includes(semantics))fail('Unsupported interval semantics.');
 const cutoff=new Date().toISOString();
 return {schema:1,kind:'plant_solar_allocation',case_sha256:comparison.case_identity.sha256,source_kind:'reviewer_supplied',source_label:'',plant_mapping:'',power_basis:'total_plant_eligible_solar',interval_semantics:semantics,review_as_of:cutoff,intervals:x.original.rows.map(r=>({start:r.time,end:r.end_time,available_at:cutoff,...(semantics==='constant_power'?{power_kw:null}:{energy_kwh:null,power_cap_kw:null})}))};
}
export function solarAllocationTemplate(comparison,semantics='constant_power'){return template(comparison,semantics,context(comparison));}
export function sequenceSolarAllocationTemplate(comparison,semantics='constant_power'){return template(comparison,semantics,sequenceContext(comparison));}
function validate(value,comparison,x){
 fields(value,['schema','kind','case_sha256','source_kind','source_label','plant_mapping','power_basis','interval_semantics','review_as_of','intervals'],'profile');
 if(value.schema!==1||value.kind!=='plant_solar_allocation')fail('Unsupported profile schema.');
 if(value.case_sha256!==comparison.case_identity.sha256)fail('Profile belongs to a different case.');
 if(!['illustrative_scenario','reviewer_supplied'].includes(value.source_kind))fail('Declare an illustrative scenario or reviewer-supplied source.');
 label(value.source_label,'the source');label(value.plant_mapping,'which plant the allocation serves');
 if(value.power_basis!=='total_plant_eligible_solar')fail('Supply total plant-eligible solar power, not regional curtailment or surplus remaining after baseline use.');
 if(!['constant_power','interval_energy'].includes(value.interval_semantics))fail('Use power declared constant within each interval, or interval energy and any known power limit, with null for unknown quantities. Point readings and averages alone do not establish simultaneous use.');
 const energy=value.interval_semantics==='interval_energy';
 const cutoff=epoch(value.review_as_of);
 if(!Array.isArray(value.intervals)||value.intervals.length>x.maxIntervals)fail(`Supply at most ${x.maxIntervals} intervals.`);
 const intervals=value.intervals.map((r,index)=>{
  fields(r,['start','end','available_at',...(energy?['energy_kwh','power_cap_kw']:['power_kw'])],`interval ${index+1}`);
  const start=epoch(r.start),end=epoch(r.end),available=epoch(r.available_at);
  if(start>=end||start<x.start||end>x.end)fail('Intervals must have positive duration within the remaining-plan horizon.');
  for(const key of energy?['energy_kwh','power_cap_kw']:['power_kw'])if(r[key]!==null&&(!finite(r[key])||r[key]<0))fail(`${key} must be finite and nonnegative, or null when unknown.`);
  if(energy&&r.energy_kwh!==null&&r.power_cap_kw!==null){
   // Validate even late declarations; their energy still cannot exceed the stated physical bound.
   boundSolarTiming({pieces:[{hours:(end-start)/HOUR,original_power_kw:0,revised_power_kw:0}],energy_kwh:r.energy_kwh,power_cap_kw:r.power_cap_kw});
  }
  const unknown=energy?r.energy_kwh===null||r.power_cap_kw===null:r.power_kw===null;
  return {...r,start_ms:start,end_ms:end,status:available>cutoff?'late':unknown?'unknown':'known'};
 }).sort((a,b)=>a.start_ms-b.start_ms);
 for(let i=1;i<intervals.length;i++)if(intervals[i].start_ms<intervals[i-1].end_ms)fail('Intervals overlap, including equivalent-offset timestamps.');
 return {intervals,allocation:structuredClone(value)};
}
function planPieces(x,intervals){
 const epochs=x.times.map(epoch),points=[x.start,x.end,...epochs,...intervals.flatMap(r=>[r.start_ms,r.end_ms]),...x.outages.flatMap(outage=>[outage.start,outage.end])];
 const cuts=[...new Set(points.filter(t=>t>=x.start&&t<=x.end))].sort((a,b)=>a-b);
 let hour=0;
 return cuts.slice(1).map((to,index)=>{
  const from=cuts[index],hours=(to-from)/HOUR;while(hour+1<epochs.length&&epochs[hour+1]<=from)hour++;
  const stopped=x.outages.some(outage=>from>=outage.start&&from<outage.end),power=rate=>x.sec===null?null:stopped?0:product(product(rate,x.productionMultiplier),x.sec);
  return {start:new Date(from).toISOString(),end:new Date(to).toISOString(),start_epoch_ms:from,end_epoch_ms:to,duration_hours:hours,original_power_kw:power(x.originalProduction[hour]),revised_power_kw:power(x.revisedProduction[hour])};
 });
}
function intervalEnergy(x,v,pieces){
 const sec=x.sec,coverage={horizon_hours:(x.end-x.start)/HOUR,known_hours:0,unknown_hours:0,late_hours:0},rows=[],sum={},deltaTerms={};
 const point=n=>({lower:n,upper:n}),minus=(n,b)=>({lower:n-b.upper,upper:n-b.lower});
 let pointer=0,fullOriginal=0,fullRevised=0;
 for(const p of pieces)if(sec!==null){fullOriginal+=product(p.original_power_kw,p.duration_hours);fullRevised+=product(p.revised_power_kw,p.duration_hours);}
 for(const r of v.intervals){
  while(pointer<pieces.length&&pieces[pointer].end_epoch_ms<=r.start_ms)pointer++;
  const selected=[];while(pointer<pieces.length&&pieces[pointer].start_epoch_ms<r.end_ms)selected.push(pieces[pointer++]);
  const hours=(r.end_ms-r.start_ms)/HOUR,row={start:r.start,end:r.end,status:r.status,energy_kwh:r.energy_kwh,power_cap_kw:r.power_cap_kw,bounds:null};
  if(r.status==='late')coverage.late_hours+=hours;
  if(r.status==='known'){
   coverage.known_hours+=hours;
   if(sec!==null){
    const bounds=boundSolarTiming({pieces:selected.map(p=>({hours:p.duration_hours,original_power_kw:p.original_power_kw,revised_power_kw:p.revised_power_kw})),energy_kwh:r.energy_kwh,power_cap_kw:r.power_cap_kw});
    const a=selected.reduce((total,p)=>total+product(p.original_power_kw,p.duration_hours),0),b=selected.reduce((total,p)=>total+product(p.revised_power_kw,p.duration_hours),0),change=loadChange(selected);
    Object.assign(bounds,{original_load_kwh:point(a),revised_load_kwh:point(b),delta_load_kwh:point(change),allocated_solar_kwh:point(r.energy_kwh),original_other_kwh:minus(a,bounds.original_solar_kwh),revised_other_kwh:minus(b,bounds.revised_solar_kwh),delta_other_kwh:minus(change,bounds.delta_solar_kwh),original_unused_solar_kwh:minus(r.energy_kwh,bounds.original_solar_kwh),revised_unused_solar_kwh:minus(r.energy_kwh,bounds.revised_solar_kwh)});
    for(const [key,value] of Object.entries(bounds)){if(key.startsWith('delta_'))(deltaTerms[key]??=[]).push(value);else{sum[key]??=point(0);sum[key].lower+=value.lower;sum[key].upper+=value.upper;}}
    row.bounds=bounds;
   }
  }
  rows.push(row);
 }
 for(const [key,terms] of Object.entries(deltaTerms))sum[key]={lower:sumValues(terms.map(v=>v.lower)),upper:sumValues(terms.map(v=>v.upper))};
 if(sum.delta_load_kwh)sum.delta_other_kwh=minus(sum.delta_load_kwh.lower,sum.delta_solar_kwh);
 coverage.unknown_hours=Math.max(0,coverage.horizon_hours-coverage.known_hours);
 if(![fullOriginal,fullRevised,...Object.values(sum).flatMap(b=>[b.lower,b.upper])].every(finite))fail('Energy or power exceeds finite numeric range.');
 const status=sec===null?'unknown_energy':coverage.unknown_hours>1e-10?'partial':'complete',known=sec===null||coverage.known_hours===0?null:sum;
 return {schema:1,kind:'conditional_solar_allocation_comparison',status,allocation:v.allocation,coverage,known_totals:null,totals:null,known_bounds:known,bounds:status==='complete'?structuredClone(sum):null,full_load_totals:sec===null?null:{original_load_kwh:fullOriginal,revised_load_kwh:fullRevised,delta_load_kwh:loadChange(pieces)},rows,
  scope:['Interval energy and an upper power bound constrain one shared eligible-solar trace for both supplied plans. No constant solar power or interpolation is assumed.',
   'Bounds are sharp under arbitrary nonnegative within-interval variation below the declared cap; ramp rates, cloud dynamics and cross-interval dependence are not imposed. These are feasible ranges, not confidence intervals.',
   'Change is bounded jointly on the same solar trace. Separate original/returned range endpoints need not occur together and must not be subtracted to obtain the change.',
   'Plant load remains the declared piecewise-constant production model with exact outage splits. Declared interval energy, power limits, source availability and plant eligibility are not authenticated meter evidence.',
   'Missing, null and later-available energy or power limits remain unknown. Partial bounds cover only common known intervals. No measured avoided curtailment, money, carbon or operating permission is established.']};
}
function energyOnlyDifference(pieces,energy){
 function maximum(sign){
  if(energy===0)return 0;
  const edges=[];
  for(const p of pieces){
   const gain=sign*(p.revised_power_kw-p.original_power_kw);if(gain<=0)continue;
   const peak=Math.max(p.original_power_kw,p.revised_power_kw),density=gain/peak;
   if(!finite(density)||density===0)fail('Energy-only density exceeds supported numeric precision.');
   edges.push({capacity:product(peak,p.duration_hours),density});
  }
  edges.sort((a,b)=>b.density-a.density);
  const terms=[];let remaining=energy;
  for(const edge of edges){const used=Math.min(remaining,edge.capacity);terms.push(product(used,edge.density));remaining-=used;if(remaining===0)break;}
  return sumValues(terms);
 }
 return {lower:negative(maximum(-1)),upper:maximum(1)};
}
function differenceEnvelope(x,v,pieces,result){
 const scope=[
  'Returned minus original under one shared nonnegative plant-eligible solar trace. Independent source intervals remain intact, including across midnight; no within-interval energy is invented.',
  'Timely declared constant power, energy and power limits constrain the comparison. Missing and late evidence uses load-only limits; late numeric values are ignored. Partial absolute solar totals remain unknown.',
  'Energy without a power limit gives closed infimum/supremum bounds under arbitrarily high finite power. Some endpoints may be limiting values rather than attainable traces; a zero endpoint does not establish an achievable tie.',
  'Range widths attribute unresolved modeled differences to whole source intervals or contiguous missing gaps. They are not expected information value, promised resolution or a minimum measurement cadence.',
  'No forecast, schedule, authenticated plant allocation, measured recovery or operating permission is established. Water service, spill, production and final inventory remain separate outcomes.'
 ];
 if(x.sec===null)return {status:'unknown_energy',delta_solar_kwh:null,delta_other_kwh:null,width_kwh:null,contributions:[],scope};
 const contributions=[];let pointer=0,cursor=x.start;
 function add(start,end,interval,index){
  const selected=[];while(pointer<pieces.length&&pieces[pointer].start_epoch_ms<end)selected.push(pieces[pointer++]);
  const status=interval?.status??'missing',constraints={};
  if(interval&&status!=='late')for(const key of ['power_kw','energy_kwh','power_cap_kw'])if(interval[key]!==undefined&&interval[key]!==null)constraints[key]=interval[key];
  let method='load_only',delta;
  if(Object.hasOwn(constraints,'power_kw')){
   method='constant_power';const value=sumValues(selected.map(p=>signedProduct(Math.min(p.revised_power_kw,constraints.power_kw)-Math.min(p.original_power_kw,constraints.power_kw),p.duration_hours)));delta={lower:value,upper:value};
  }else if(Object.hasOwn(constraints,'energy_kwh')&&Object.hasOwn(constraints,'power_cap_kw')){
   method='shared_interval_energy';delta={...result.rows[index].bounds.delta_solar_kwh};
  }else if(Object.hasOwn(constraints,'energy_kwh')){
   method='energy_only';delta=energyOnlyDifference(selected,constraints.energy_kwh);
  }else{
   const cap=constraints.power_cap_kw??Infinity;if(cap!==Infinity)method='cap_only';
   const changes=selected.map(p=>({hours:p.duration_hours,difference:Math.min(p.revised_power_kw,cap)-Math.min(p.original_power_kw,cap)}));
   delta={lower:negative(sumValues(changes.map(p=>product(Math.max(0,-p.difference),p.hours)))),upper:sumValues(changes.map(p=>product(Math.max(0,p.difference),p.hours)))};
  }
  const width=delta.upper-delta.lower;if(![delta.lower,delta.upper,width].every(finite)||width<0)fail('Difference bounds exceed finite numeric range or precision.');
  const contribution={start:new Date(start).toISOString(),end:new Date(end).toISOString(),status,method,delta_solar_kwh:delta,width_kwh:width,constraints};
  if(method==='load_only'){
   const groups=[];
   for(const piece of selected){
    if(piece.original_power_kw===piece.revised_power_kw)continue;
    if(groups.at(-1)?.at(-1).end_epoch_ms===piece.start_epoch_ms)groups.at(-1).push(piece);else groups.push([piece]);
   }
   contribution.focus_intervals=groups.map(group=>{
    const terms=group.map(p=>signedProduct(p.revised_power_kw-p.original_power_kw,p.duration_hours));
    const lower=sumValues(terms.filter(value=>value<0)),upper=sumValues(terms.filter(value=>value>0));
    return {start:group[0].start,end:group.at(-1).end,delta_solar_kwh:{lower,upper},width_kwh:upper-lower};
   });
  }
  contributions.push(contribution);
 }
 v.intervals.forEach((interval,index)=>{if(cursor<interval.start_ms)add(cursor,interval.start_ms);add(interval.start_ms,interval.end_ms,interval,index);cursor=interval.end_ms;});
 if(cursor<x.end)add(cursor,x.end);
 const delta_solar_kwh={lower:sumValues(contributions.map(r=>r.delta_solar_kwh.lower)),upper:sumValues(contributions.map(r=>r.delta_solar_kwh.upper))},load=result.full_load_totals.delta_load_kwh;
 const delta_other_kwh={lower:load-delta_solar_kwh.upper,upper:load-delta_solar_kwh.lower},width_kwh=sumValues(contributions.map(r=>r.width_kwh));
 if(!Object.values(delta_other_kwh).every(finite))fail('Difference bounds exceed finite numeric range.');
 return {status:'bounded',delta_solar_kwh,delta_other_kwh,width_kwh,contributions,scope};
}
/** Conditional simultaneous use under an explicitly piecewise-constant scenario; never metered recovery. */
export function evaluateSolarAllocation({comparison,allocation}){return evaluate(comparison,allocation,context(comparison));}
export function evaluateSequenceSolarAllocation({comparison,allocation}){return evaluate(comparison,allocation,sequenceContext(comparison));}
function evaluate(comparison,allocation,x){
 const v=validate(allocation,comparison,x),pieces=planPieces(x,v.intervals),result=allocation.interval_semantics==='interval_energy'?intervalEnergy(x,v,pieces):constantPower(x,v,pieces);
 return {...result,difference_envelope:differenceEnvelope(x,v,pieces,result)};
}
function constantPower(x,v,pieces){
 const sec=x.sec;
 const rows=[],knownLoadChanges=[],knownSolarChanges=[];
 const coverage={horizon_hours:(x.end-x.start)/HOUR,known_hours:0,unknown_hours:0,late_hours:0};
 const sum={original_load_kwh:0,revised_load_kwh:0,original_solar_kwh:0,revised_solar_kwh:0,original_other_kwh:0,revised_other_kwh:0,allocated_solar_kwh:0,original_unused_solar_kwh:0,revised_unused_solar_kwh:0};
 let pointer=0,fullOriginal=0,fullRevised=0;
 for(const piece of pieces){
  const {start_epoch_ms:from,end_epoch_ms:to,duration_hours:hours,original_power_kw:a,revised_power_kw:b}=piece;
  while(pointer<v.intervals.length&&v.intervals[pointer].end_ms<=from)pointer++;
  const candidate=v.intervals[pointer],interval=candidate&&candidate.start_ms<=from&&candidate.end_ms>=to?candidate:null,status=interval?.status??'missing';
  const solar=status==='known'?interval.power_kw:null,row={...piece,status,solar_power_kw:solar,original_solar_kwh:null,revised_solar_kwh:null};
  if(sec!==null){fullOriginal+=product(a,hours);fullRevised+=product(b,hours);}
  if(status==='known'){
   coverage.known_hours+=hours;
   if(sec!==null){
    const original=product(Math.min(a,solar),hours),revised=product(Math.min(b,solar),hours);
    knownLoadChanges.push(signedProduct(b-a,hours));knownSolarChanges.push(signedProduct(Math.min(b,solar)-Math.min(a,solar),hours));
    Object.assign(row,{original_solar_kwh:original,revised_solar_kwh:revised});
    sum.original_load_kwh+=product(a,hours);sum.revised_load_kwh+=product(b,hours);sum.original_solar_kwh+=original;sum.revised_solar_kwh+=revised;sum.allocated_solar_kwh+=product(solar,hours);
   }
  }else {coverage.unknown_hours+=hours;if(status==='late')coverage.late_hours+=hours;}
  rows.push(row);
 }
 sum.original_other_kwh=sum.original_load_kwh-sum.original_solar_kwh;sum.revised_other_kwh=sum.revised_load_kwh-sum.revised_solar_kwh;
 sum.original_unused_solar_kwh=sum.allocated_solar_kwh-sum.original_solar_kwh;sum.revised_unused_solar_kwh=sum.allocated_solar_kwh-sum.revised_solar_kwh;
 sum.delta_load_kwh=sumValues(knownLoadChanges);sum.delta_solar_kwh=sumValues(knownSolarChanges);sum.delta_other_kwh=sum.delta_load_kwh-sum.delta_solar_kwh;
 if(![fullOriginal,fullRevised,...Object.values(sum),...rows.flatMap(r=>[r.original_power_kw,r.revised_power_kw].filter(n=>n!==null))].every(finite))fail('Energy or power exceeds finite numeric range.');
 const known=sec===null||coverage.known_hours===0?null:sum,status=sec===null?'unknown_energy':coverage.unknown_hours>0?'partial':'complete';
 return {schema:1,kind:'conditional_solar_allocation_comparison',status,allocation:v.allocation,coverage,known_totals:known,totals:status==='complete'?structuredClone(sum):null,full_load_totals:sec===null?null:{original_load_kwh:fullOriginal,revised_load_kwh:fullRevised,delta_load_kwh:loadChange(pieces)},rows,
  scope:['Same plant-eligible solar profile and interval support for both supplied plans. Source, plant mapping and allocation authority are reviewer declarations.',
   'Conditional simultaneous use is the integral of min(modeled plant power, declared eligible solar power), with both rates constant between explicit boundaries. Point readings, interval averages and regional curtailment are not accepted as this profile.',
   'Modeled power is effective production times declared constant specific energy, with exact outage splits and energy for spilled water included. Other electricity is the load not matched to this allocation; its actual source is unknown.',
   'Profile availability is checked at its declared review cutoff, which may be retrospective. Missing, null and later-available intervals remain unknown. Partial totals use only identical known intervals for both plans.',
   'Solar-use difference is conditional on the profile; it is not measured recovery, causal avoided curtailment, verified renewable procurement, money, carbon or operating permission. Check water service, reserve, spill, final storage and total electricity alongside it.']};
}
