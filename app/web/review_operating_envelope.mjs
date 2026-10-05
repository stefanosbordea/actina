import fs from 'node:fs/promises';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {parseArgs} from 'node:util';

const usage='node web/review_operating_envelope.mjs --input supplied-trace.json --output new-review.json';
const sha=bytes=>createHash('sha256').update(bytes).digest('hex');

try{
 const {values}=parseArgs({options:{input:{type:'string'},output:{type:'string'},help:{type:'boolean'}},allowPositionals:false});
 if(values.help){
  console.log(`${usage}\nOffline review of supplied operating limits and traces. No plant commands or schedule generation.\nInput limit: 4 MiB. Existing output files are preserved.\nExit 0 means the review was saved, including findings or unknown checks; exit 1 means invalid input or a file error.`);
 }else{
  if(!values.input||!values.output)throw Error(usage);
  if((await fs.stat(values.input)).size>4*1024*1024)throw Error('Input exceeds 4 MiB.');
  const bytes=await fs.readFile(values.input);
  if(bytes.length>4*1024*1024)throw Error('Input exceeds 4 MiB.');
  const name=path.basename(values.input);
  if(name.length>255||/[\u0000-\u001f]/.test(name))throw Error('Unsupported input filename.');
  const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),raw=text.replace(/^\uFEFF/,'');
  for(const [token]of raw.replace(/"(?:\\.|[^"\\])*"/g,'""').matchAll(/-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/g)){
   const n=Number(token);
   if(!Number.isFinite(n)||(n===0&&/[1-9]/.test(token.split(/[eE]/)[0])))throw Error('Input number exceeds finite numeric range or precision.');
  }
  const evaluatorBytes=await fs.readFile(new URL('./operating-envelope.mjs',import.meta.url));
  const {evaluateOperatingEnvelope}=await import('data:text/javascript;base64,'+evaluatorBytes.toString('base64'));
  const results=evaluateOperatingEnvelope(JSON.parse(raw));
  const review={schema:1,kind:'operating_envelope_review',created_at_utc:new Date().toISOString(),
   source_file:{name,bytes:bytes.length,sha256:sha(bytes),text},
   evaluator_sha256:sha(evaluatorBytes),results};
  const output=path.resolve(values.output);
  await fs.mkdir(path.dirname(output),{recursive:true});
  await fs.writeFile(output,JSON.stringify(review,null,2)+'\n',{flag:'wx'});
  console.log(`${results.decision}: ${output}`);
 }
}catch(error){console.error(`Review not saved: ${error.message}`);process.exitCode=1;}
