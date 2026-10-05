// Exact comparison of supplied uniform-rate models; no schedule generation.
const ZERO={n:0n,d:1n},HOUR=3600000,MAX_HOURS=8784,MAX_SEGMENTS=3*MAX_HOURS;
const fail=message=>{throw Error(`Paired water service: ${message}`);};
const abs=n=>n<0n?-n:n;
function gcd(a,b){while(b){const next=a%b;a=b;b=next;}return a;}
function rational(n,d=1n){if(!n)return ZERO;if(d<0n){n=-n;d=-d;}const g=gcd(abs(n),d);return {n:n/g,d:d/g};}
function add(a,b){
 if(!a.n)return b;if(!b.n)return a;
 const g=gcd(a.d,b.d),ad=a.d/g,bd=b.d/g,n=a.n*bd+b.n*ad;if(!n)return ZERO;
 const cancel=gcd(abs(n),g);return {n:n/cancel,d:ad*(b.d/cancel)};
}
const negative=a=>a.n?{n:-a.n,d:a.d}:ZERO;
const subtract=(a,b)=>add(a,negative(b));
function multiply(a,b){if(!a.n||!b.n)return ZERO;const x=gcd(abs(a.n),b.d),y=gcd(abs(b.n),a.d);return {n:(a.n/x)*(b.n/y),d:(a.d/y)*(b.d/x)};}
function divide(a,b){if(!b.n)fail('Internal zero divisor.');return multiply(a,b.n<0n?{n:-b.d,d:-b.n}:{n:b.d,d:b.n});}
const compare=(a,b)=>{const delta=a.d===b.d?a.n-b.n:a.n*b.d-b.n*a.d;return delta<0n?-1:delta>0n?1:0;};
const minimum=(a,b)=>compare(a,b)<=0?a:b;
const maximum=(a,b)=>compare(a,b)>=0?a:b;
const bits=new DataView(new ArrayBuffer(8));
function exact(value){
 if(value===0)return ZERO;bits.setFloat64(0,value);
 const raw=bits.getBigUint64(0),e=Number((raw>>52n)&2047n),fraction=raw&((1n<<52n)-1n),sign=raw>>63n?-1n:1n;
 const significand=sign*(e?(1n<<52n)|fraction:fraction),power=e?e-1075:-1074;
 return power>=0?rational(significand<<BigInt(power)):rational(significand,1n<<BigInt(-power));
}
function display(value){
 if(!value.n)return 0;
 const n=abs(value.n),d=value.d;let exponent=n.toString(2).length-d.toString(2).length;
 if(exponent>=0?n<(d<<BigInt(exponent)):(n<<BigInt(-exponent))<d)exponent--;
 if(exponent>1023||exponent< -1075)return null;
 const shift=exponent< -1022?1074:52-exponent,numerator=shift>=0?n<<BigInt(shift):n,denominator=shift>=0?d:d<<BigInt(-shift);
 let rounded=numerator/denominator;const remainder=numerator%denominator;
 if(2n*remainder>denominator||(2n*remainder===denominator&&(rounded&1n)))rounded++;
 const result=Number(rounded)*(exponent< -1022?Number.MIN_VALUE:2**(exponent-52));
 return Number.isFinite(result)&&result!==0?(value.n<0n?-result:result):null;
}
const quantity=value=>({value:display(value),exact:{numerator:String(value.n),denominator:String(value.d)}});
function fields(value,keys,label){
 if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!keys.includes(key))||keys.some(key=>!Object.hasOwn(value,key)))fail(`Supply exactly the ${label} fields.`);
}
function finite(value,label,min=0,max=Infinity){if(typeof value!=='number'||!Number.isFinite(value)||value<min||value>max)fail(`${label} is outside the supported finite range.`);}
function validate(model){
 fields(model,['start_epoch','start_hour','end_hour','initial','capacity','reserve','target','segments'],'model');
 if(!Number.isSafeInteger(model.start_epoch)||Math.abs(model.start_epoch)>8640000000000000)fail('Declare a supported integer UTC epoch.');
 finite(model.start_hour,'Start hour');finite(model.end_hour,'End hour',model.start_hour);
 if(compare(subtract(exact(model.end_hour),exact(model.start_hour)),exact(MAX_HOURS))>0||Math.abs(model.start_epoch+model.end_hour*HOUR)>8640000000000000)fail('The supported horizon is at most 8,784 hours within the calendar range.');
 finite(model.capacity,'Tank capacity');if(model.capacity===0)fail('Tank capacity must be positive.');
 for(const key of ['initial','reserve','target'])finite(model[key],key,0,model.capacity);
 if(!Array.isArray(model.segments)||model.segments.length>MAX_SEGMENTS)fail('Supply a complete segment array with at most 26,352 entries.');
 let next=model.start_hour;
 for(const segment of model.segments){
  fields(segment,['from','to','production','demand'],'segment');finite(segment.from,'Segment start',model.start_hour,model.end_hour);finite(segment.to,'Segment end',model.start_hour,model.end_hour);
  if(segment.from!==next||segment.to<=segment.from)fail('Segments must form an ordered, positive-duration, gap-free partition.');
  finite(segment.production,'Production rate');finite(segment.demand,'Demand rate');next=segment.to;
 }
 if(next!==model.end_hour)fail('Segments must cover the complete declared horizon.');
}
function comparable(a,b){
 validate(a);validate(b);
 for(const key of ['start_epoch','start_hour','end_hour','initial','capacity','reserve','target'])if(a[key]!==b[key])fail(`The supplied models disagree on ${key}.`);
 let i=0,j=0;
 while(i<a.segments.length&&j<b.segments.length){const x=a.segments[i],y=b.segments[j];if(x.demand!==y.demand)fail('Demanded rates must match on every common interval.');const end=Math.min(x.to,y.to);if(x.to===end)i++;if(y.to===end)j++;}
}

function* trajectory(model){
 const capacity=exact(model.capacity),reserve=exact(model.reserve);let storage=exact(model.initial);
 function* piece(from,to,initial,slope,unserved){
  if(compare(from,to)>=0)return;
  const final=add(initial,multiply(slope,subtract(to,from))),cuts=[from];
  if((compare(initial,reserve)<0&&compare(final,reserve)>0)||(compare(initial,reserve)>0&&compare(final,reserve)<0))cuts.push(add(from,divide(subtract(reserve,initial),slope)));
  cuts.push(to);
  for(let i=1;i<cuts.length;i++)yield {from:cuts[i-1],to:cuts[i],initial:add(initial,multiply(slope,subtract(cuts[i-1],from))),slope,unserved,reserve};
 }
 for(const segment of model.segments){
  const from=exact(segment.from),to=exact(segment.to),production=exact(segment.production),demand=exact(segment.demand),slope=subtract(production,demand),trial=add(storage,multiply(slope,subtract(to,from)));
  const clipped=compare(trial,ZERO)<0?ZERO:compare(trial,capacity)>0?capacity:null;
  if(clipped!==null){
   const contact=add(from,divide(subtract(clipped,storage),slope));
   yield* piece(from,contact,storage,slope,ZERO);
   yield* piece(contact,to,clipped,ZERO,maximum(subtract(demand,production),ZERO));storage=clipped;
  }else{yield* piece(from,to,storage,slope,ZERO);storage=trial;}
 }
 return storage;
}
const stockAt=(piece,time)=>add(piece.initial,multiply(piece.slope,subtract(time,piece.from)));
const deficitAt=(piece,time)=>maximum(subtract(piece.reserve,stockAt(piece,time)),ZERO);
const deliveryWitness=(start,end,a,b,delta)=>({start_hour:start,end_hour:end,original_unserved_rate_m3_h:a,revised_unserved_rate_m3_h:b,added_unserved_rate_m3_h:delta});
const extendsWitness=(prior,next)=>prior&&compare(prior.end_hour,next.start_hour)===0&&compare(prior.original_unserved_rate_m3_h,next.original_unserved_rate_m3_h)===0&&compare(prior.revised_unserved_rate_m3_h,next.revised_unserved_rate_m3_h)===0;
function witness(value){return value?Object.fromEntries(Object.entries(value).map(([key,v])=>[key,typeof v==='boolean'?v:quantity(v)])):null;}

/** Absolute requirements under the same exact uniform-rate trajectory. */
export function assessWaterService(model){
 validate(model);let unmet=ZERO,minStock=exact(model.initial);const path=trajectory(model);let next=path.next();
 while(!next.done){
  const piece=next.value;
  unmet=add(unmet,multiply(piece.unserved,subtract(piece.to,piece.from)));
  minStock=minimum(minStock,minimum(piece.initial,stockAt(piece,piece.to)));next=path.next();
 }
 const final=next.value,criteria={demand_met:unmet.n===0n,reserve_met:compare(minStock,exact(model.reserve))>=0,terminal_target_met:compare(final,exact(model.target))>=0};
 return {status:Object.values(criteria).every(Boolean)?'modeled_requirements_met':'modeled_requirements_failed',criteria,
  unmet_m3:quantity(unmet),min_storage_m3:quantity(minStock),final_storage_m3:quantity(final)};
}

/** Integrate normalized effective rates before converting totals for display. */
export function compareProductionEnergy({original,revised,specific_energy_kwh_m3:sec,tariffs}){
 comparable(original,revised);finite(sec,'Specific energy');if(sec===0)fail('Specific energy must be positive.');
 if(original.start_hour!==0||!Number.isInteger(original.end_hour)||!Array.isArray(tariffs)||tariffs.length!==original.end_hour)fail('Supply one tariff for every whole elapsed hour.');
 tariffs.forEach(price=>finite(price,'Tariff'));
 function volumes(model){
  let water=ZERO,pricedWater=ZERO;
  for(const segment of model.segments)for(let h=Math.floor(segment.from);h<Math.ceil(segment.to);h++){
   const from=exact(Math.max(segment.from,h)),to=exact(Math.min(segment.to,h+1));
   const volume=multiply(exact(segment.production),subtract(to,from));
   water=add(water,volume);pricedWater=add(pricedWater,multiply(volume,exact(tariffs[h])));
  }
  return {water,pricedWater};
 }
 const a=volumes(original),b=volumes(revised),energy=exact(sec),proof={};
 function pair(key,name){
  const control=multiply(a[key],energy),candidate=multiply(b[key],energy),delta=subtract(candidate,control);
  const exactValues={control:quantity(control),candidate:quantity(candidate),delta:quantity(delta)};proof[name]=exactValues;
  if(Object.values(exactValues).some(q=>q.value===null))fail('Energy or cost exceeds finite nonzero numeric display range.');
  return Object.fromEntries(Object.entries(exactValues).map(([key,q])=>[key,q.value]));
 }
 return {electricity_kwh:pair('water','electricity_kwh'),cost_eur:pair('pricedWater','cost_eur'),proof};
}

/** Necessary conservation bounds; sufficient total water does not establish feasible timing. */
export function waterProductionBudget(model){
 validate(model);let production=ZERO,demand=ZERO;
 for(const segment of model.segments){
  const duration=subtract(exact(segment.to),exact(segment.from));
  production=add(production,multiply(exact(segment.production),duration));
  demand=add(demand,multiply(exact(segment.demand),duration));
 }
 const initial=exact(model.initial),target=exact(model.target),required=maximum(ZERO,subtract(add(demand,target),initial)),additional=maximum(ZERO,subtract(required,production));
 return {schema:1,kind:'fixed_production_budget',status:additional.n>0n?'additional_production_necessary':'budget_not_excluded',
  horizon_duration_hours:quantity(subtract(exact(model.end_hour),exact(model.start_hour))),starting_storage_m3:quantity(initial),terminal_target_m3:quantity(target),
  effective_production_m3:quantity(production),demand_m3:quantity(demand),unavoidable_unserved_m3:quantity(maximum(ZERO,subtract(subtract(demand,initial),production))),
  production_required_for_demand_and_target_m3:quantity(required),additional_production_required_m3:quantity(additional)};
}

/** Exact whole-horizon storage bounds for unchanged effective production and demand. */
export function storageRequirements(model){
 validate(model);
 const start=exact(model.start_hour),end=exact(model.end_hour),initial=exact(model.initial),capacity=exact(model.capacity),reserve=exact(model.reserve),target=exact(model.target);
 let net=ZERO,low=ZERO,lowHour=start,peak=ZERO,peakHour=start,drawdown=ZERO,drawdownStart=start,drawdownEnd=start;
 for(const segment of model.segments){
  const to=exact(segment.to),duration=subtract(to,exact(segment.from));
  net=add(net,multiply(subtract(exact(segment.production),exact(segment.demand)),duration));
  if(compare(net,low)<0){low=net;lowHour=to;}
  if(compare(net,peak)>0){peak=net;peakHour=to;}
  const deficit=subtract(peak,net);
  if(compare(deficit,drawdown)>0){drawdown=deficit;drawdownStart=peakHour;drawdownEnd=to;}
 }
 const bound=(constraint,start_hour,end_hour,net_supply_m3,required_storage_m3)=>({constraint,start_hour,end_hour,net_supply_m3,required_storage_m3});
 const priority=['reserve','terminal_target','stored_initial','no_spill'];
 const binding=candidates=>candidates.reduce((best,next)=>{
  const order=compare(next.required_storage_m3,best.required_storage_m3)||compare(best.end_hour,next.end_hour)||compare(best.start_hour,next.start_hour)||priority.indexOf(best.constraint)-priority.indexOf(next.constraint);
  return order>0?next:best;
 });
 const initialWitness=binding([
  bound('reserve',start,lowHour,low,subtract(reserve,low)),
  bound('terminal_target',start,end,net,subtract(target,net))
 ]);
 const capacityWitness=binding([
  bound('reserve',drawdownStart,drawdownEnd,negative(drawdown),add(reserve,drawdown)),
  bound('terminal_target',peakHour,end,subtract(net,peak),add(target,subtract(peak,net))),
  bound('stored_initial',start,start,ZERO,initial)
 ]);
 const initialMinimum=initialWitness.required_storage_m3,capacityMinimum=capacityWitness.required_storage_m3,noSpillMinimum=add(initial,peak),topupMinimum=add(maximum(initial,initialMinimum),peak);
 const gap=required=>maximum(ZERO,subtract(required,capacity)),initialGap=maximum(ZERO,subtract(initialMinimum,initial));
 const serialize=value=>Object.fromEntries(Object.entries(value).map(([key,v])=>[key,typeof v==='string'?v:quantity(v)]));
 return {schema:1,kind:'fixed_plan_storage_requirements',
  horizon:{start_epoch:model.start_epoch,start_hour:quantity(start),end_hour:quantity(end),duration_hours:quantity(subtract(end,start))},
  minimum_initial_m3:quantity(initialMinimum),initial_shortfall_m3:quantity(initialGap),
  with_spill:{minimum_capacity_m3:quantity(capacityMinimum),capacity_shortfall_m3:quantity(gap(capacityMinimum)),feasible:initialGap.n===0n&&compare(capacity,capacityMinimum)>=0},
  without_spill:{minimum_capacity_m3:quantity(noSpillMinimum),capacity_shortfall_m3:quantity(gap(noSpillMinimum)),minimum_capacity_after_initial_topup_m3:quantity(topupMinimum),capacity_shortfall_after_initial_topup_m3:quantity(gap(topupMinimum)),feasible:initialGap.n===0n&&compare(capacity,noSpillMinimum)>=0},
  witnesses:{initial:serialize(initialWitness),with_spill:serialize(capacityWitness),without_spill:serialize(bound('no_spill',start,peakHour,peak,noSpillMinimum))},
  scope:['Finite binary64 effective rates, stocks and elapsed-hour endpoints are interpreted as exact rationals under the declared uniform-rate model.',
   'Feasibility means all demand, reserve and the terminal target are met across the complete horizon. Starting water and capacity must meet their bounds together; starting water is counted once.',
   'With-spill bounds permit overflow as retained water loss, not reduced production or permission to discharge. Without-spill bounds retain all supplied production.',
   'The after-top-up bound holds starting water at the greater of the supplied stock and its minimum requirement. Availability of additional water is not established.',
   'Witness ties use greatest requirement, earliest end, earliest start, then reserve, terminal target, stored initial, no spill. Witness hours use the original model coordinates.',
   'Numeric values are rounded display approximations. Null means an exact nonzero quantity is outside finite nonzero numeric display range; exact fractions remain authoritative.',
   'No forecast, schedule or operating command is generated. These water-only bounds do not establish pressure, quality, pump or plant feasibility, operating authorization, energy savings or recovered solar.']};
}

export function compareWaterService({original,revised}){
 comparable(original,revised);
 const a=trajectory(original),b=trajectory(revised);let left=a.next(),right=b.next(),from=exact(original.start_hour);
 let shifted=ZERO,deliveryDuration=ZERO,deliveryCount=0,deliveryEnd=null,deliveryFirst=null,deliveryMaximum=null,maxRate=ZERO;
 let reserveDuration=ZERO,reserveCount=0,reserveSpan=null,reserveFirst=null,reserveMaximum=null,maxDeficit=ZERO;
 function finishReserve(){
  if(!reserveSpan)return;reserveCount++;if(!reserveFirst)reserveFirst=reserveSpan;
  if(compare(reserveSpan.added_deficit_m3,maxDeficit)>0){maxDeficit=reserveSpan.added_deficit_m3;reserveMaximum=reserveSpan;}
  reserveSpan=null;
 }
 while(!left.done&&!right.done){
  const x=left.value,y=right.value,to=minimum(x.to,y.to),duration=subtract(to,from),rate=subtract(y.unserved,x.unserved);
  if(rate.n>0n){
   if(deliveryEnd===null||compare(deliveryEnd,from)!==0)deliveryCount++;deliveryEnd=to;
   deliveryDuration=add(deliveryDuration,duration);shifted=add(shifted,multiply(rate,duration));
   const current=deliveryWitness(from,to,x.unserved,y.unserved,rate);if(!deliveryFirst)deliveryFirst={...current};else if(extendsWitness(deliveryFirst,current))deliveryFirst.end_hour=to;
   if(compare(rate,maxRate)>0){maxRate=rate;deliveryMaximum={...current};}else if(extendsWitness(deliveryMaximum,current))deliveryMaximum.end_hour=to;
  }
  const originalStart=deficitAt(x,from),originalEnd=deficitAt(x,to),revisedStart=deficitAt(y,from),revisedEnd=deficitAt(y,to),startDelta=subtract(revisedStart,originalStart),endDelta=subtract(revisedEnd,originalEnd);
  if(startDelta.n>0n||endDelta.n>0n){
   const cross=()=>add(from,multiply(duration,divide(negative(startDelta),subtract(endDelta,startDelta))));
   const start=startDelta.n<0n?cross():from,end=endDelta.n<0n?cross():to,peak=compare(startDelta,endDelta)>=0?from:to,added=maximum(startDelta,endDelta);
   const current={start_hour:start,end_hour:end,start_open:compare(start,from)!==0||startDelta.n===0n,end_open:compare(end,to)!==0||endDelta.n===0n,peak_hour:peak,original_deficit_m3:deficitAt(x,peak),revised_deficit_m3:deficitAt(y,peak),added_deficit_m3:added};
   reserveDuration=add(reserveDuration,subtract(end,start));
   if(reserveSpan&&compare(reserveSpan.end_hour,start)===0){
    reserveSpan.end_hour=end;reserveSpan.end_open=current.end_open;
    if(compare(added,reserveSpan.added_deficit_m3)>0)for(const key of ['peak_hour','original_deficit_m3','revised_deficit_m3','added_deficit_m3'])reserveSpan[key]=current[key];
   }else{finishReserve();reserveSpan=current;}
  }
  from=to;if(compare(x.to,to)===0)left=a.next();if(compare(y.to,to)===0)right=b.next();
 }
 finishReserve();
 const originalEnd=left.value,revisedEnd=right.value,delta=subtract(revisedEnd,originalEnd),criteria={delivery_no_worse:shifted.n===0n,reserve_no_worse:maxDeficit.n===0n,end_stock_no_lower:delta.n>=0n};
 return {schema:1,kind:'modeled_paired_water_service',status:Object.values(criteria).every(Boolean)?'no_modeled_regression':'regression_detected',criteria,
  horizon:{start_epoch:original.start_epoch,start_hour:quantity(exact(original.start_hour)),end_hour:quantity(exact(original.end_hour)),duration_hours:quantity(subtract(exact(original.end_hour),exact(original.start_hour)))},
  delivery:{interval_count:deliveryCount,duration_hours:quantity(deliveryDuration),shifted_shortfall_m3:quantity(shifted),max_added_unserved_rate_m3_h:quantity(maxRate),first:witness(deliveryFirst),maximum:witness(deliveryMaximum)},
  reserve:{interval_count:reserveCount,duration_hours:quantity(reserveDuration),max_added_deficit_m3:quantity(maxDeficit),first:witness(reserveFirst),maximum:witness(reserveMaximum)},
  end_stock:{original_m3:quantity(originalEnd),revised_m3:quantity(revisedEnd),delta_m3:quantity(delta)},
  scope:['Finite binary64 effective rates, volumes and elapsed-hour endpoints are interpreted as exact rationals under the declared uniform-rate model.',
   'Delivery compares unserved rates almost everywhere; reserve compares clipped physical stock pointwise; final stock is a separate non-regression condition.',
   'Touching positive-duration pieces are grouped for interval counts, including isolated zero contacts. Delivery witnesses retain a constant-rate subinterval; reserve witnesses retain a grouped span and its earliest maximum.',
   'Numeric values are rounded display approximations. Null means an exact nonzero quantity is outside finite nonzero numeric display range, not unknown evidence; exact fractions remain authoritative.',
   'No modeled regression is relative to the supplied original. Both plans may still undersupply demand or breach reserve and target requirements.',
   'No forecast or schedule is generated. This model does not establish actual service, pressure, water quality, flow-rate or ramp feasibility, plant authorization or recovered solar.']};
}
