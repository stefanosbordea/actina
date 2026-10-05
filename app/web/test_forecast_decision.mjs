import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import vm from 'node:vm';
import {evaluateForecastDecisionReview} from './public/forecast-decision.mjs';

const fixtureUrl=new URL('../results/forecast-value-study/independent-inputs-v1.json',import.meta.url);
const raw=readFileSync(fixtureUrl,'utf8'),fixture=JSON.parse(raw),box={};
vm.runInNewContext(readFileSync(new URL('public/vendor/papaparse.min.js',import.meta.url),'utf8'),box);
const sha256=text=>createHash('sha256').update(text).digest('hex');
const at=(value,path)=>path.split('.').reduce((current,key)=>current?.[key],value);

test('independent labels retain the frozen protocol and oracle identities',()=>{
 for(const [path,key]of [['../results/forecast-value-study/PROTOCOL.md','protocol_sha256'],['../results/forecast-value-study/build-independent.py','generator_sha256'],['../results/paired-water-service/independent-oracle.py','water_oracle_sha256']])assert.equal(sha256(readFileSync(new URL(path,import.meta.url),'utf8')),fixture[key]);
 assert.equal(fixture.analytical_anchor_count,13);assert.equal(fixture.cases.length,63);
});
for(const c of fixture.cases)test(`supplied decision / ${c.id}`,async()=>{
 const before=JSON.stringify(c.packet),evaluate=()=>evaluateForecastDecisionReview(c.packet,{sha256,Papa:box.Papa});
 if(c.rejection_regex)await assert.rejects(evaluate,new RegExp(c.rejection_regex));
 else{
  const {record,result}=await evaluate();
  for(const [path,expected]of Object.entries(c.expected))assert.deepEqual(at(result,path),expected,`${c.id}: ${path}`);
  assert.deepEqual(record.files,c.packet.files);assert.deepEqual(record.declaration_file,c.packet.declaration_file);
  assert.equal(record.note,undefined);assert.equal(result.forecast_attribution.status,'not_established');
 }
 assert.equal(JSON.stringify(c.packet),before,'Evaluating must not mutate supplied evidence.');
});
