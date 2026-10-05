import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {parseArgs} from 'node:util';
import vm from 'node:vm';
import {evaluateRoadmapHandoff,parseRoadmapDeclaration} from './public/roadmap-handoff.mjs';

const root=path.dirname(fileURLToPath(import.meta.url));
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');
const decode=bytes=>new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);
const usage='node web/review_roadmap.mjs --declaration declaration.json --weather paphos_weather.csv --predictions test_predictions.csv --forecast day_forecast.csv --schedule schedule_results.csv --output new-review.json';

async function retained(file){
 if((await fs.stat(file)).size>4*1024*1024)throw Error('Each input must be at most4MiB.');
 const bytes=await fs.readFile(file);if(bytes.length>4*1024*1024)throw Error('Each input must be at most4MiB.');
 const name=path.basename(file);if(!name||name.length>255||/[\u0000-\u001f]/.test(name))throw Error('Unsupported input filename.');
 return {name,text:decode(bytes),sha256:sha(bytes)};
}

try{
 const {values}=parseArgs({options:Object.fromEntries(['declaration','weather','predictions','forecast','schedule','output'].map(name=>[name,{type:'string'}]).concat([['help',{type:'boolean'}]])),allowPositionals:false});
 if(values.help){
  console.log(`${usage}\nOffline supplied-file review. No model execution or schedule generation. Existing output files are preserved.\nThe declaration must state units, interval semantics, flag rules and source links; one tank trace does not establish matched water service.`);
 }else{
  if(['declaration','weather','predictions','forecast','schedule','output'].some(key=>!values[key]))throw Error(usage);
  const inputs=await Promise.all(['declaration','weather','predictions','forecast','schedule'].map(key=>retained(values[key])));
  const [declaration_file,weather,predictions,day_forecast,schedule]=inputs;
  const declaration=parseRoadmapDeclaration(declaration_file.text);
  const vendor=await fs.readFile(path.join(root,'public/vendor/papaparse.min.js'));
  const provenance=JSON.parse(await fs.readFile(path.join(root,'vendor/provenance.json'),'utf8'));
  if(sha(vendor)!==provenance.script_sha256)throw Error('CSV parser does not match retained provenance.');
  const sandbox={module:{exports:{}},exports:{}};
  vm.runInNewContext(decode(vendor),sandbox,{filename:'papaparse.min.js',timeout:1000});
  const files={weather,predictions,day_forecast,schedule};
  const results=evaluateRoadmapHandoff({declaration,files,Papa:sandbox.module.exports});
  const review={schema:1,kind:'roadmap_handoff_review',declaration_file,files,createdAt:new Date().toISOString(),results};
  const output=JSON.stringify(review,null,2)+'\n';
  if(Buffer.byteLength(output)>20*1024*1024)throw Error('Complete review exceeds20MiB.');
  await fs.writeFile(path.resolve(values.output),output,{flag:'wx'});
  console.log(`Review saved: ${path.resolve(values.output)}. Source files retained; water comparability and forecast attribution remain unestablished.`);
 }
}catch(error){console.error(`Review not saved: ${error.message}`);process.exitCode=1;}
