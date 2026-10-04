import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';

const root=fileURLToPath(new URL('../',import.meta.url));
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'results/operating-envelope/protocol-fixtures.json'))).fixtures;
const fixture=id=>fixtures.find(row=>row.id===id);
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const cli=path.join(root,'web/review_operating_envelope.mjs');
function isolated(body){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'aquashift operating '));
 try{body(dir);}finally{fs.rmSync(dir,{recursive:true,force:true});}
}
function run(dir,text,extra=[]){
 fs.writeFileSync(path.join(dir,'supplied trace.json'),text);
 return spawnSync(process.execPath,[cli,'--input',path.join(dir,'supplied trace.json'),'--output',path.join(dir,'review.json'),...extra],{encoding:'utf8',timeout:30000,maxBuffer:1024*1024});
}
const base=()=>JSON.stringify(fixture('flat_matched_water_control').input);

for(const id of ['flat_matched_water_control','triangle_water_feasible_ramp_failure','bounded_means_do_not_certify']){
 test(`operating CLI preserves evidence and saves the ${id} decision`,()=>isolated(dir=>{
  const item=fixture(id),raw='\uFEFF'+JSON.stringify(item.input,null,2).replaceAll('\n','\r\n')+'\r\n';
  const result=run(dir,raw);assert.equal(result.status,0,result.stderr);
  const packet=JSON.parse(fs.readFileSync(path.join(dir,'review.json')));
  assert.equal(packet.kind,'operating_envelope_review');
  assert.equal(packet.results.status,item.expected.status);assert.equal(packet.results.decision,item.expected.decision);
  assert.match(result.stdout,new RegExp(item.expected.decision));
  assert.equal(packet.source_file.text,raw);assert.equal(packet.source_file.sha256,sha(raw));
  assert.equal(packet.source_file.bytes,Buffer.byteLength(raw));assert.equal(packet.source_file.name,'supplied trace.json');
  assert.equal(packet.evaluator_sha256,sha(fs.readFileSync(path.join(root,'web/operating-envelope.mjs'))));
 }));
}
test('operating CLI never overwrites an existing report',()=>isolated(dir=>{
 const prior='Retained result\n';fs.writeFileSync(path.join(dir,'review.json'),prior);
 const result=run(dir,base());assert.equal(result.status,1);assert.match(result.stderr,/Review not saved/);
 assert.equal(fs.readFileSync(path.join(dir,'review.json'),'utf8'),prior);
}));
test('operating CLI never overwrites its input',()=>isolated(dir=>{
 const input=path.join(dir,'source.json'),raw=base();fs.writeFileSync(input,raw);
 const result=spawnSync(process.execPath,[cli,'--input',input,'--output',input],{encoding:'utf8',timeout:30000});
 assert.equal(result.status,1);assert.equal(fs.readFileSync(input,'utf8'),raw);
}));
test('operating CLI binds identity to loaded evaluator bytes even if its file changes',()=>isolated(dir=>{
 const copy=path.join(dir,'review_operating_envelope.mjs'),modulePath=path.join(dir,'operating-envelope.mjs');
 fs.copyFileSync(cli,copy);
 const before=`import fs from 'node:fs'; export function evaluateOperatingEnvelope(){fs.writeFileSync(${JSON.stringify(modulePath)},'changed after loading');return {status:'unknown',decision:'supply_evidence'};}`;
 fs.writeFileSync(modulePath,before);fs.writeFileSync(path.join(dir,'input.json'),base());
 const result=spawnSync(process.execPath,[copy,'--input',path.join(dir,'input.json'),'--output',path.join(dir,'review.json')],{encoding:'utf8',timeout:30000});
 assert.equal(result.status,0,result.stderr);
 const packet=JSON.parse(fs.readFileSync(path.join(dir,'review.json')));
 assert.equal(packet.evaluator_sha256,sha(before));assert.notEqual(packet.evaluator_sha256,sha(fs.readFileSync(modulePath)));
}));
for(const [name,content] of [
 ['malformed UTF8',Buffer.from([0xc3,0x28])],['malformed JSON','{broken'],
 ['numeric overflow',base().replace('"ramp_up_m3_h2":3','"ramp_up_m3_h2":1e999')],
 ['nonzero underflow',base().replace('"ramp_up_m3_h2":3','"ramp_up_m3_h2":1e-999')],
 ['unsupported fields',base().replace('"schema":1','"schema":1,"operator_authorized":true')],
 ['oversize input',' '.repeat(4*1024*1024+1)],
 ])test(`operating CLI rejects ${name} without saving a result`,()=>isolated(dir=>{
  const result=run(dir,content);assert.equal(result.status,1,result.stdout);assert.match(result.stderr,/Review not saved/);
  assert.equal(fs.existsSync(path.join(dir,'review.json')),false);
 }));
test('operating CLI does not mistake numbers in identity text for nonfinite values',()=>isolated(dir=>{
 const raw=base().replace('synthetic-unit','Example 1e999 and 1e-999');
 assert.equal(run(dir,raw).status,0);
}));
test('operating CLI requires named input/output and rejects unknown arguments',()=>isolated(dir=>{
 assert.equal(spawnSync(process.execPath,[cli],{encoding:'utf8',timeout:30000}).status,1);
 assert.equal(run(dir,base(),['--run-plant']).status,1);
 assert.equal(fs.existsSync(path.join(dir,'review.json')),false);
}));
test('operating CLI help distinguishes saving a review from meeting limits',()=>{
 const result=spawnSync(process.execPath,[cli,'--help'],{encoding:'utf8',timeout:30000});
 assert.equal(result.status,0,result.stderr);assert.match(result.stdout,/including findings or unknown checks/);
});
