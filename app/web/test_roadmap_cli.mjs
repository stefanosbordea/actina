import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root=fileURLToPath(new URL('../',import.meta.url));
const fixture=path.join(root,'results/roadmap-handoff/independent-fixture-files');
const sha=value=>createHash('sha256').update(value).digest('hex');
const paths={declaration:'declaration.json',weather:'paphos_weather.csv',predictions:'test_predictions.csv',forecast:'day_forecast.csv',schedule:'schedule_results.csv'};
function isolated(body){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'aquashift-roadmap-'));try{for(const name of Object.values(paths))fs.copyFileSync(path.join(fixture,name),path.join(dir,name));body(dir);}finally{fs.rmSync(dir,{recursive:true,force:true});}}
function run(dir){return spawnSync(process.execPath,[path.join(root,'web/review_roadmap.mjs'),...Object.entries(paths).flatMap(([role,name])=>['--'+role,path.join(dir,name)]),'--output',path.join(dir,'review.json')],{encoding:'utf8',timeout:30000,maxBuffer:1024*1024});}

test('CLI joins the independently frozen roadmap files and retains every exact input',()=>isolated(dir=>{
 const result=run(dir);assert.equal(result.status,0,result.stderr);const review=JSON.parse(fs.readFileSync(path.join(dir,'review.json'),'utf8'));
 assert.equal(review.kind,'roadmap_handoff_review');assert.equal(review.results.water_comparability.status,'not_established');assert.equal(review.results.forecast_attribution.status,'not_established');
 for(const [role,name]of Object.entries(paths)){const raw=fs.readFileSync(path.join(dir,name)),file=role==='declaration'?review.declaration_file:review.files[role==='forecast'?'day_forecast':role];assert.equal(file.name,name);assert.deepEqual(Buffer.from(file.text,'utf8'),raw);assert.equal(file.sha256,sha(raw));}
 assert.equal(review.results.demo.support.hours,48);assert.equal(review.results.demo.support.electricity_kwh.delta,0);assert.ok(Math.abs(review.results.demo.support.cost_eur.delta+2)<1e-10);
}));
test('CLI preserves an existing output instead of overwriting a prior review',()=>isolated(dir=>{
 const out=path.join(dir,'review.json');fs.writeFileSync(out,'Retained prior review\n');const result=run(dir);assert.equal(result.status,1);assert.match(result.stderr,/Review not saved/);assert.equal(fs.readFileSync(out,'utf8'),'Retained prior review\n');
}));
test('malformed UTF8 never becomes a retained replacement review',()=>isolated(dir=>{
 fs.writeFileSync(path.join(dir,paths.weather),Buffer.from([0xc3,0x28]));const result=run(dir);assert.equal(result.status,1);assert.equal(fs.existsSync(path.join(dir,'review.json')),false);
}));
test('CLI preserves a UTF8 BOM while binding the declaration to its actual bytes',()=>isolated(dir=>{
 const input=path.join(dir,paths.weather),raw=Buffer.concat([Buffer.from([0xef,0xbb,0xbf]),fs.readFileSync(input)]);fs.writeFileSync(input,raw);
 const declarationPath=path.join(dir,paths.declaration),declaration=JSON.parse(fs.readFileSync(declarationPath,'utf8'));declaration.declared_links.weather_sha256=sha(raw);fs.writeFileSync(declarationPath,'\uFEFF'+JSON.stringify(declaration)+'\n');
 const result=run(dir);assert.equal(result.status,0,result.stderr);const review=JSON.parse(fs.readFileSync(path.join(dir,'review.json'),'utf8'));assert.equal(review.files.weather.sha256,sha(raw));assert.deepEqual(Buffer.from(review.files.weather.text,'utf8'),raw);assert.equal(review.declaration_file.text.charCodeAt(0),0xfeff);
}));
test('a wrong declared forecast link blocks output despite valid CSV values',()=>isolated(dir=>{
 const input=path.join(dir,paths.declaration),declaration=JSON.parse(fs.readFileSync(input,'utf8'));declaration.declared_links.schedule_forecast_sha256='0'.repeat(64);fs.writeFileSync(input,JSON.stringify(declaration));const result=run(dir);assert.equal(result.status,1);assert.equal(fs.existsSync(path.join(dir,'review.json')),false);
}));
test('a nonzero JSON tariff cannot underflow into a fabricated zero price',()=>isolated(dir=>{
 const input=path.join(dir,paths.declaration),declaration=JSON.parse(fs.readFileSync(input,'utf8'));declaration.tariffs[0].eur_kwh='UNDERFLOW';fs.writeFileSync(input,JSON.stringify(declaration).replace('"UNDERFLOW"','1e-400'));
 const result=run(dir);assert.equal(result.status,1);assert.equal(fs.existsSync(path.join(dir,'review.json')),false);assert.match(result.stderr,/precision|underflow/i);
}));
