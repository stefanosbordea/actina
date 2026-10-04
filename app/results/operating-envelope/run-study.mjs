import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {parseArgs} from 'node:util';

const root=fileURLToPath(new URL('../../',import.meta.url));
const folder='results/operating-envelope/';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const read=name=>fs.readFileSync(path.join(root,name));
const decode=name=>JSON.parse(read(name));
const sourceNames=[folder+'PROTOCOL.md',folder+'protocol-fixtures.json',folder+'independent-water-proof.py',
 folder+'independent-water-proof.json',folder+'run-study.mjs','web/operating-envelope.mjs','web/review_operating_envelope.mjs'];
const identity=()=>Object.fromEntries(sourceNames.map(name=>[name,sha(read(name))]));
const {values}=parseArgs({options:{output:{type:'string'}},allowPositionals:false});
if(!values.output)throw Error('Use --output with a new result directory.');
const output=path.resolve(values.output);
fs.mkdirSync(output,{recursive:false});
const receipt={status:'RUNNING',started_at_utc:new Date().toISOString(),commands:[],cases:[]};
function save(name,value){fs.writeFileSync(path.join(output,name),JSON.stringify(value,null,2)+'\n');}
function run(name,command){
 const result=spawnSync(command[0],command.slice(1),{cwd:root,encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
 fs.writeFileSync(path.join(output,name+'.stdout'),result.stdout??'');
 fs.writeFileSync(path.join(output,name+'.stderr'),result.stderr??'');
 receipt.commands.push({name,command,exit_code:result.status,error:result.error?.message??null,
  stdout_sha256:sha(result.stdout??''),stderr_sha256:sha(result.stderr??'')});
 assert.equal(result.status,0,result.stderr||result.error?.message);
 return result.stdout;
}
try{
 receipt.input_sha256=identity();
 assert.equal(receipt.input_sha256[folder+'PROTOCOL.md'],'d52999f323e1da379b355ef19d5b9a7636230677fe0ed334e09255a19076b46d');
 assert.equal(receipt.input_sha256[folder+'protocol-fixtures.json'],'84dfa25fe16b0cdf11f20db11625590737fec1035cfac2463ca367ff21afe40e');
 const fixtures=decode(folder+'protocol-fixtures.json');
 const water=JSON.parse(run('water-proof',['python3',folder+'independent-water-proof.py']));
 assert.deepEqual(water,decode(folder+'independent-water-proof.json'));
 const ids=['flat_matched_water_control','triangle_water_feasible_ramp_failure','bounded_means_do_not_certify'];
 const selected=ids.map(id=>fixtures.fixtures.find(row=>row.id===id));
 assert.deepEqual(selected[0].input.trajectory.points,[{hour:0,rate_m3_h:2},{hour:2,rate_m3_h:2}]);
 assert.deepEqual(selected[1].input.trajectory.points,[{hour:0,rate_m3_h:0},{hour:1,rate_m3_h:4},{hour:2,rate_m3_h:0}]);
 for(const item of selected){
  const {trajectory:ignored,...controls}=item.input;
  const {trajectory:unused,...base}=selected[0].input;
  assert.deepEqual(controls,base);
  const inputName=item.id+'.input.json',reportName=item.id+'.review.json';
  save(inputName,item.input);
  run(item.id,[process.execPath,'web/review_operating_envelope.mjs','--input',path.join(output,inputName),'--output',path.join(output,reportName)]);
  const packet=JSON.parse(fs.readFileSync(path.join(output,reportName)));
  assert.equal(packet.source_file.sha256,sha(fs.readFileSync(path.join(output,inputName))));
  assert.equal(packet.results.status,item.expected.status);assert.equal(packet.results.decision,item.expected.decision);
  for(const [key,status]of Object.entries(item.expected.checks))assert.equal(packet.results.checks[key].status,status);
  receipt.cases.push({id:item.id,input:inputName,review:reportName,status:packet.results.status,decision:packet.results.decision,
   input_sha256:packet.source_file.sha256,review_sha256:sha(fs.readFileSync(path.join(output,reportName)))});
 }
 for(const result of Object.values(water.results)){
  for(const [field,key]of [['produced_m3','each_production_m3'],['delivered_m3','each_delivered_m3'],['end_m3','each_final_m3'],['initial_m3','initial_m3'],['reserve_m3','reserve_m3'],['capacity_m3','capacity_m3'],['target_m3','target_m3'],['demand_m3_h','demand_m3_h']])assert.equal(result[field],fixtures.matched_water[key]);
  assert.deepEqual(result.hourly_mean_rates_m3_h,['2','2']);
 }
 for(const name of ['flat','triangle'])for(const bound of ['minimum','maximum'])assert.equal(water.results[name][bound+'_m3'],fixtures.matched_water[name+'_'+bound+'_m3']);
 for(const bound of ['minimum','maximum'])assert.equal(water.results.triangle.extrema.find(row=>row.stock_m3===fixtures.matched_water['triangle_'+bound+'_m3']).elapsed_h,fixtures.matched_water['triangle_'+bound+'_hour']);
 assert.equal(String(selected[0].input.horizon.end_hour-selected[0].input.horizon.start_hour),fixtures.matched_water.duration_hours);
 receipt.finding='The synthetic traces meet the same water-service controls and have identical hourly means; the triangle violates supplied continuous ramp limits. Mean-only evidence remains unknown.';
 receipt.scope='Implementation and analytical examples only. No Paphos plant, source authenticity, schedule generation, electricity saving or recovered-solar claim.';
 receipt.input_sha256_after=identity();assert.deepEqual(receipt.input_sha256_after,receipt.input_sha256);
 receipt.status='PASS';
}catch(error){receipt.status='FAIL';receipt.error=error.stack;process.exitCode=1;}
receipt.completed_at_utc=new Date().toISOString();save('receipt.json',receipt);
console.log(`${receipt.status}: ${path.join(output,'receipt.json')}`);
