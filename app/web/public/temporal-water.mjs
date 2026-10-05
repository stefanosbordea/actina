// Internal evaluator: execution-review supplies validated, normalized measurements.
const roles=['produced','delivered','other_inflow','other_outflow','spill'];
const incoming=new Set(['produced','other_inflow']);
const scope=[
 'Compatibility means at least one water-volume path fits the timely declared bounds and tank capacity; it does not identify the actual path.',
 'Whole interval totals and shared no-reset counter readings stay coupled. No uniform flow profile or missing value is inferred.',
 'Unknown flows permit nonnegative completions; unknown tank boundaries permit values within capacity. Such feasible incomplete evidence remains unknown.',
 'This check does not establish flow-rate or ramp feasibility, reserve-policy compliance, matched demand, pressure, water quality or operating permission.'
];

// Every finite nonnegative binary64 value is an integer multiple of 2^-1074.
function exactCapacity(value){
 const bytes=new DataView(new ArrayBuffer(8));bytes.setFloat64(0,value);
 const bits=bytes.getBigUint64(0),exponent=Number((bits>>52n)&2047n),fraction=bits&((1n<<52n)-1n);
 return exponent?((1n<<52n)|fraction)<<BigInt(exponent-1):fraction;
}

function feasibleCirculation(size,bounds){
 const balance=Array(size).fill(0n),graph=Array.from({length:size+2},()=>[]),source=size,sink=size+1;
 function edge(from,to,capacity){const forward={to,capacity,reverse:graph[to].length},backward={to:from,capacity:0n,reverse:graph[from].length};graph[from].push(forward);graph[to].push(backward);}
 for(const [from,to,lower,upper]of bounds){if(upper!==null&&lower>upper)return false;balance[from]-=lower;balance[to]+=lower;}
 const required=balance.reduce((total,value)=>total+(value>0n?value:0n),0n);
 if(required===0n)return true;
 for(const [from,to,lower,upper]of bounds)edge(from,to,upper===null?required:upper-lower);
 for(let i=0;i<size;i++){if(balance[i]>0n)edge(source,i,balance[i]);else if(balance[i]<0n)edge(i,sink,-balance[i]);}
 const level=new Int32Array(size+2),next=new Int32Array(size+2),queue=new Int32Array(size+2);
 let sent=0n;
 while(sent<required){
  level.fill(-1);level[source]=0;queue[0]=source;let head=0,tail=1;
  while(head<tail){const node=queue[head++];for(const e of graph[node])if(e.capacity>0n&&level[e.to]===-1){level[e.to]=level[node]+1;queue[tail++]=e.to;}}
  if(level[sink]===-1)return false;
  next.fill(0);
  // Iterative blocking flow: long meter/storage chains must not use the JS call stack.
  const path=[source],edges=[],limits=[required-sent];
  while(path.length&&sent<required){
   const node=path.at(-1);
   if(node===sink){
    const amount=limits.at(-1);
    for(let i=0;i<edges.length;i++){const e=graph[path[i]][edges[i]];e.capacity-=amount;graph[e.to][e.reverse].capacity+=amount;}
    sent+=amount;path.length=1;edges.length=0;limits.length=1;limits[0]=required-sent;continue;
   }
   while(next[node]<graph[node].length){const e=graph[node][next[node]];if(e.capacity>0n&&level[e.to]===level[node]+1)break;next[node]++;}
   if(next[node]===graph[node].length){level[node]=-1;path.pop();limits.pop();if(edges.length){edges.pop();next[path.at(-1)]++;}continue;}
   const e=graph[node][next[node]],limit=limits.at(-1);edges.push(next[node]);path.push(e.to);limits.push(e.capacity<limit?e.capacity:limit);
  }
 }
 return true;
}

export function evaluateTemporalWater({start,end,capacity,cutoff,streams,tank,zeros}){
 const known=new Map(),unresolved=[],cuts=new Set([start,end]);
 for(const role of roles){
  if(zeros.has(role)){known.set(role,{semantics:'zero',rows:[]});continue;}
  const stream=streams.get(role);
  if(!stream||stream.conflict||(stream.semantics==='cumulative_counter'&&stream.no_reset!==true)){known.set(role,{semantics:'unknown',rows:[]});unresolved.push(role);continue;}
  const rows=stream.rows.filter(row=>row.available<=cutoff&&row.bounds),interval=stream.semantics==='interval_total';
  const complete=rows.length>0&&rows[0].start===start&&(interval?rows.at(-1).end:rows.at(-1).start)===end&&(!interval||rows.every((row,index)=>!index||row.start===rows[index-1].end));
  if(!complete)unresolved.push(role);
  for(const row of rows){cuts.add(row.start);cuts.add(row.end);}
  known.set(role,{semantics:stream.semantics,rows});
 }
 const boundaryBounds=[start,end].map((time,index)=>{
  const rows=tank.filter(row=>row.start===time);
  if(rows.length!==1||rows[0].available>cutoff||!rows[0].bounds){unresolved.push(index?'final_storage':'initial_storage');return {lower:0,upper:capacity};}
  return {lower:rows[0].bounds.lower,upper:Math.min(capacity,rows[0].bounds.upper)};
 });
 const times=[...cuts].sort((a,b)=>a-b),index=new Map(times.map((time,i)=>[time,i])),bins=times.length-1,bounds=[],cap=exactCapacity(capacity);
 let size=bins+1;const reservoir=bins,node=()=>size++;
 const add=(from,to,lower=0n,upper=null)=>bounds.push([from,to,lower,upper]);
 const measured=(from,to,value)=>add(from,to,exactCapacity(value.lower),exactCapacity(value.upper));
 for(let i=0;i<bins-1;i++)add(i,i+1,0n,cap);
 measured(reservoir,0,boundaryBounds[0]);measured(bins-1,reservoir,boundaryBounds[1]);
 for(const role of roles){
  const {semantics,rows}=known.get(role),inflow=incoming.has(role);
  const branch=(from,to)=>inflow?add(from,to):add(to,from);
  if(semantics==='zero')continue;
  if(semantics==='unknown'){for(let i=0;i<bins;i++)branch(reservoir,i);continue;}
  if(semantics==='interval_total'){
   let cursor=0;
   for(const row of rows){
    const first=index.get(row.start),last=index.get(row.end),interval=node();
    for(;cursor<first;cursor++)branch(reservoir,cursor);
    if(inflow)measured(reservoir,interval,row.bounds);else measured(interval,reservoir,row.bounds);
    for(;cursor<last;cursor++)branch(interval,cursor);
   }
   for(;cursor<bins;cursor++)branch(reservoir,cursor);
  }else{
   const chain=Array.from({length:bins},node),readings=new Map(rows.map(row=>[row.start,row.bounds]));
   for(let i=0;i<=bins;i++){
    const from=i===0?reservoir:chain[i-1],to=i===bins?reservoir:chain[i],value=readings.get(times[i]);
    if(value){if(inflow)measured(to,from,value);else measured(from,to,value);}else if(inflow)add(to,from);else add(from,to);
   }
   for(let i=0;i<bins;i++)branch(chain[i],i);
  }
 }
 const feasible=feasibleCirculation(size,bounds),complete=unresolved.length===0;
 return {status:!feasible?'inconsistent':complete?'compatible':'unknown',method:'exact_bounded_circulation',evidence_complete:complete,boundary_count:times.length,unresolved_roles:unresolved,scope:[...scope]};
}
