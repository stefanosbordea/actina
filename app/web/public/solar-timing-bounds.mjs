const fail=message=>{throw Error(`Solar timing: ${message}`);};
const nonnegative=value=>typeof value==='number'&&Number.isFinite(value)&&value>=0;
function sum(values){let total=0,error=0;for(const value of values){const corrected=value-error,next=total+corrected;error=(next-total)-corrected;total=next;}return total;}
function product(a,b){const value=a*b;if(!Number.isFinite(value)||(a!==0&&b!==0&&value===0))fail('Energy exceeds the supported numeric range.');return value;}
function slope(a,b){const difference=b[1]-a[1],value=difference/(b[0]-a[0]);if(!Number.isFinite(value)||(difference!==0&&value===0))fail('Hull slope exceeds the supported numeric range.');return value;}

// Arbitrary variation within each piece makes its attainable (energy, use) set
// the convex hull of the power breakpoints. Lower/upper hull slopes allocate
// the shared energy exactly; bounding the difference uses one common trace.
function extremum(pieces,energy,cap,value,upper){
 const edges=[],direction=upper?-1:1;
 for(const p of pieces){
  const points=[...new Set([0,cap,Math.min(p.original_power_kw,cap),Math.min(p.revised_power_kw,cap)])].sort((a,b)=>a-b),hull=[];
  for(const power of points){
   const point=[power,value(p,power)];
   while(hull.length>1&&direction*slope(hull.at(-2),hull.at(-1))>=direction*slope(hull.at(-1),point))hull.pop();
   hull.push(point);
  }
  for(let i=1;i<hull.length;i++){
   const capacity=product(hull[i][0]-hull[i-1][0],p.hours);
   edges.push({capacity,slope:slope(hull[i-1],hull[i])});
  }
 }
 edges.sort((a,b)=>direction*(a.slope-b.slope));
 const terms=[];let remaining=energy;
 for(const edge of edges){const used=Math.min(remaining,edge.capacity);terms.push(product(used,edge.slope));remaining-=used;if(remaining===0)break;}
 if(remaining>64*Number.EPSILON*energy)fail('Energy allocation exceeds the supported numeric precision.');
 return sum(terms);
}

/** Sharp to floating precision under a shared trace in [0, power_cap_kw], with no ramp constraint. */
export function boundSolarTiming(input){
 if(!input||typeof input!=='object'||Array.isArray(input))fail('Supply pieces, energy_kwh and power_cap_kw.');
 const {pieces,power_cap_kw:cap}=input;let energy=input.energy_kwh;
 if(!Array.isArray(pieces)||pieces.length===0)fail('Supply at least one piece.');
 if(!nonnegative(energy)||!nonnegative(cap))fail('Energy and power cap must be finite nonnegative numbers.');
 for(const p of pieces)if(!p||!nonnegative(p.hours)||p.hours===0||!nonnegative(p.original_power_kw)||!nonnegative(p.revised_power_kw))fail('Each piece requires positive finite hours and finite nonnegative original and revised power.');
 const hours=sum(pieces.map(p=>p.hours)),capacity=Number.isFinite(hours)?product(hours,cap):sum(pieces.map(p=>product(p.hours,cap)));
 if(!Number.isFinite(capacity))fail('Total energy capacity exceeds the supported numeric range.');
 // Splitting integer-time intervals can round their capacity a few ulps low.
 // Snap only excess within 4 machine epsilons relative to capacity; never at zero.
 if(energy>capacity){
  if(capacity===0||energy-capacity>4*Number.EPSILON*capacity)fail('Energy exceeds the power cap times the interval duration.');
  energy=capacity;
 }
 const original=(p,s)=>Math.min(p.original_power_kw,s),revised=(p,s)=>Math.min(p.revised_power_kw,s),delta=(p,s)=>revised(p,s)-original(p,s);
 const result={};
 for(const [key,value] of [['original_solar_kwh',original],['revised_solar_kwh',revised],['delta_solar_kwh',delta]]){
  if(energy===0)result[key]={lower:0,upper:0};
  else if(energy===capacity){const total=sum(pieces.map(p=>product(value(p,cap),p.hours)));result[key]={lower:total,upper:total};}
  else result[key]={lower:extremum(pieces,energy,cap,value,false),upper:extremum(pieces,energy,cap,value,true)};
  if(!Object.values(result[key]).every(Number.isFinite))fail('Solar-use bound exceeds the supported numeric range.');
 }
 return result;
}
