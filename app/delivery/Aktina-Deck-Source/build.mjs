import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {execFileSync} from 'node:child_process';

const dir=path.dirname(fileURLToPath(import.meta.url)),app=path.resolve(dir,'../..');
const runtime=process.env.RUNTIME_ROOT??path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies');
process.env.RUNTIME_NODE_MODULES??=path.join(runtime,'node/node_modules');
process.env.RUNTIME_NODE??=process.execPath;
const skill=process.env.PRESENTATIONS_SKILL??path.join(os.homedir(),'.codex/plugins/cache/openai-primary-runtime/presentations/26.909.12148/skills/presentations');
const {FileBlob,PresentationFile}=await import(pathToFileURL(path.join(runtime,'node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs')));
const {finalizePresentation,applyPresentationChartFont}=await import(pathToFileURL(path.join(skill,'container_tools/artifact_tool_utils.mjs')));
const output=path.resolve(process.argv[2]??path.join(app,'delivery/Aktina-Pafos-2026.pptx'));
const provenance=JSON.parse(await fs.readFile(path.join(dir,'inputs.sha256.json'),'utf8'));
for(const [file,expected] of Object.entries(provenance)){
 const actual=createHash('sha256').update(await fs.readFile(path.join(app,file))).digest('hex');
 if(actual!==expected)throw Error(`Reviewed source changed: ${file}`);
}
const dataText=await fs.readFile(path.join(app,'site/data.js'),'utf8');
const data=JSON.parse(dataText.slice(dataText.indexOf('=')+1).replace(/;\s*$/,''));
const day=data.days.find(d=>d.date==='2026-07-03'),rows=day.rows;
const sum=key=>rows.reduce((total,row)=>total+row[key],0);
const energy=sum('aktina')*data.assumptions.energy;
const cost=key=>rows.reduce((total,row)=>total+row[key]*data.assumptions.energy*(row.actual>600?101:183)/1000,0);
const reduction=(1-cost('aktina')/cost('flat'))*100;
if(rows.length!==24||sum('aktina')!==5658||sum('flat')!==5658||day.start_tank!==966||rows.at(-1).tank!==966)throw Error('July 3 source changed.');
const records=(await fs.readFile(path.join(app,'experiments/f1-001/RESULTS.csv'),'utf8')).trim().split(/\r?\n/).map(row=>row.split(','));
const header=records.shift(),metrics=records.map(row=>Object.fromEntries(header.map((key,i)=>[key,row[i]])));
const metric=(method,split,key)=>Number(metrics.find(r=>r.method===method&&r.split===split)[key]);
const comparisonRows=(await fs.readFile(path.join(app,'experiments/f1-004/result/comparison.csv'),'utf8')).trim().split(/\r?\n/).map(row=>row.split(','));
const comparisonHeader=comparisonRows.shift(),comparison=comparisonRows.map(row=>Object.fromEntries(comparisonHeader.map((key,i)=>[key,row[i]])));
const research=['original','nwp_day2','analogue_raw'].map(method=>{
 const r=comparison.find(row=>row.method===method&&row.split==='test'&&row.basis==='default'&&row.scope==='full');
 if(!r||Number(r.hours)!==3567)throw Error('Expected identical 3,567-hour fixed test comparisons.');
 return {method,...Object.fromEntries(['hours','precision','recall','f1','mae','fp','fn'].map(key=>[key,Number(r[key])]))};
});
const notes=(await fs.readFile(path.join(dir,'Speaker-Notes.md'),'utf8')).split(/\n## \d+\. /).slice(1);
if(notes.length!==12)throw Error('Expected 12 corrected note sections.');
const current=JSON.parse(await fs.readFile(path.join(app,'experiments/v2-019/result/summary.json'),'utf8')).metrics.expanded;
if(current.tp!==270||current.fp!==17||current.fn!==36||current.tn!==3243)throw Error('019 validation comparison changed.');
const p=await PresentationFile.importPptx(await FileBlob.load(path.join(dir,'template.pptx')));
const C={ink:'#141414',muted:'#626262',light:'#D8D8D8',paper:'#FAFAFA',white:'#FFFFFF',black:'#101010'};
function text(s,content,x,y,w,h,size=30,bold=false,color=C.ink){
 const shape=s.shapes.add({geometry:'textbox',position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});
 shape.text=content;shape.text.style={typeface:'Arial',fontSize:size,bold,color,autoFit:'none',verticalAlignment:'top'};return shape;
}
function slide(index,title){
 const s=p.slides.items[index-1];
 for(const shape of [...s.shapes.items])if(!['slide-title','slide-number'].includes(shape.name))s.shapes.deleteById(shape.id);
 for(const chart of [...s.charts.items])s.charts.deleteById(chart.id);
 const heading=s.shapes.items.find(shape=>shape.name==='slide-title');if(heading)heading.text=title;
 s.speakerNotes.textFrame.setText(`SLIDE ${index}: ${title}\n\n${notes[index-1]}\n\nData and artifact provenance: delivery/Aktina-Deck-Source/inputs.sha256.json. Historical original remains unchanged.`);
 return s;
}
function chart(s,type,position,categories,series,extra={}){
 const c=s.charts.add(type,{position,categories,series:series.map(row=>({...row,values:row.values.map(value=>Number(value.toFixed(6)))})),hasLegend:true,
  chartFill:'none',chartLine:{fill:'none',width:0},plotAreaFill:'none',plotAreaLine:{fill:'none',width:0},
  xAxis:{textStyle:{typeface:'Arial',fontSize:18,fill:C.muted},line:{fill:C.light,width:1},majorGridlines:null},
  yAxis:{min:0,textStyle:{typeface:'Arial',fontSize:18,fill:C.muted},line:{fill:'none',width:0},majorGridlines:{fill:C.light,width:1}},
  legend:{position:'bottom',overlay:false,textStyle:{typeface:'Arial',fontSize:20,fill:C.ink}},
  barOptions:{direction:'column',grouping:'clustered',gapWidth:90},...extra});
 applyPresentationChartFont(c,{fontFamily:'Arial'});return c;
}
const foot=(s,copy,y=623)=>text(s,copy,68,y,1110,50,22,false,C.muted);

{
 const s=slide(1,'Aktina');
 text(s,'Aktina',64,68,700,62,38,true,C.white);
 text(s,'Solar power.\nWater for later.',64,182,1150,222,82,true,C.white);
 text(s,'Desalination with otherwise curtailed solar',68,450,1100,70,36,false,C.light);
 text(s,'Pafos 2.0 University category, October 2026\nPrototype. Actual curtailment recovery remains unproven.',68,618,1060,61,22,false,C.light);
}
{
 const s=slide(2,'Why water storage matters');
 text(s,'Production can move between hours',68,167,1100,68,38,true);
 const labels=[['Solar power','Available to the plant'],['Desalination','Production within limits'],['Water storage','Supply carried forward'],['Water demand','Delivery when needed']];
 const boxes=labels.map(([label,copy],i)=>{const x=68+i*290;const node=s.shapes.add({geometry:'rect',position:{left:x,top:298,width:245,height:108},fill:'none',line:{fill:C.ink,width:1.5}});text(s,label,x+14,331,220,45,27,true);text(s,copy,x,439,245,90,25,false,C.muted);return node;});
 for(let i=0;i<3;i++)s.shapes.connect(boxes[i],boxes[i+1],{kind:'straight',fromSide:'right',toSide:'left',line:{fill:C.ink,width:2},tail:{type:'arrow',width:'med',length:'med'}});
 foot(s,'Grid coordination determines whether curtailed electricity can reach a plant.');
}
{
 const s=slide(3,'Grid and Sites');
 text(s,'Grid',68,187,530,70,48,true);text(s,'Desalination and stored water',68,283,520,100,34);text(s,'Supplied model and schedule\nOperator review',68,422,520,120,28,false,C.muted);
 text(s,'Sites',680,187,530,70,48,true);text(s,'Irrigation and unusual night flow',680,283,510,100,34);text(s,'Separate prototype\nSynthetic meter examples',680,422,510,120,28,false,C.muted);
 foot(s,'Today’s supplied evidence covers Grid. Neither prototype controls equipment.');
}
{
 const s=slide(4,'The supplied demonstration');
 text(s,'296',68,158,580,142,112,true);text(s,'complete schedule days',74,317,590,65,36);text(s,'6 December 2025 to 28 September 2026',74,409,580,96,28,false,C.muted);
 text(s,'7,104 rows',742,185,470,75,50,true);text(s,'Forecast column matches\npersistence in every row',746,296,450,125,31);text(s,'Original LightGBM shown separately\nIntended schedule version pending',746,458,460,118,27,false,C.muted);
 foot(s,'The demo runs offline with its retained data, scripts and fonts.');
}
{
 const s=slide(5,'3 July 2026');
 text(s,'Hourly production, m³',70,130,800,42,26,true);
 chart(s,'bar',{left:58,top:169,width:790,height:230},rows.map((_,i)=>String(i).padStart(2,'0')),[
  {name:'Flat',values:rows.map(r=>r.flat),fill:'#A0A0A0'},{name:'Supplied',values:rows.map(r=>r.aktina),fill:C.ink}],
  {yAxis:{min:0,max:400,majorUnit:200,textStyle:{typeface:'Arial',fontSize:18,fill:C.muted},majorGridlines:{fill:C.light,width:1}}});
 text(s,'Tank, m³ at hour endpoints. Minimum 800 m³.',70,404,800,40,25,true);
 chart(s,'line',{left:58,top:445,width:790,height:183},Array.from({length:25},(_,i)=>String(i).padStart(2,'0')),[
  {name:'Tank',values:[day.start_tank,...rows.map(r=>r.tank)],line:{fill:C.ink,width:3}},
  {name:'Minimum',values:Array(25).fill(800),line:{fill:'#999999',width:1,dash:'dash'}}],
  {hasLegend:false,yAxis:{min:0,max:4000,majorUnit:2000,textStyle:{typeface:'Arial',fontSize:18,fill:C.muted},majorGridlines:{fill:C.light,width:1}},lineOptions:{smooth:false}});
 text(s,`${reduction.toFixed(2)}%`,892,171,320,100,66,true);
 text(s,'Lower illustrative tariff cost',896,274,306,92,28);
 text(s,'5,658 m³\n19,237.2 kWh',896,391,300,102,31,true);
 text(s,'Equal water and energy\nStart and end: 966 m³\nTank limit: 4,000 m³',896,516,308,103,24,false,C.muted);
 foot(s,'€101/MWh above 600 W/m², otherwise €183/MWh. No field saving or recovered-solar claim.',642);
}
{
 const s=slide(6,'Inside the demonstration');
 s.images.add({blob:new Uint8Array(await fs.readFile(path.join(dir,'product-july3.jpg'))),contentType:'image/jpeg',alt:'Aktina July 3 radiation, supplied production and tank charts with source qualification',fit:'contain',position:{left:65,top:163,width:822,height:463}});
 text(s,'3 July',928,184,283,52,32,true);text(s,'Matched daily example',928,236,279,65,25,false,C.muted);
 text(s,'10 December',928,329,290,52,32,true);text(s,'Low radiation',928,380,279,65,25,false,C.muted);
 text(s,'AktinaBench',928,473,290,52,32,true);text(s,'Every retained test hour',928,524,279,70,25,false,C.muted);
 foot(s,'44-second silent backup. Historical screenshots, before the current forecast view.',639);
}
{
 const s=slide(7,'Original forecast against persistence');
 text(s,'Mean absolute error, W/m²',68,143,800,43,28,true);
 chart(s,'bar',{left:60,top:208,width:795,height:380},['Validation','Test'],[
  {name:'LightGBM',values:['validation','test'].map(split=>metric('original_model',split,'mae_w_m2')),fill:C.ink,valuesFormatCode:'0.00'},
  {name:'Persistence',values:['validation','test'].map(split=>metric('persistence',split,'mae_w_m2')),fill:'#999999',valuesFormatCode:'0.00'}],
  {dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:'Arial',fontSize:25,fill:C.ink}},yAxis:{min:0,max:40,majorUnit:10,numberFormatCode:'0',textStyle:{typeface:'Arial',fontSize:21,fill:C.muted},majorGridlines:{fill:C.light,width:1}}});
 text(s,'Test F1',917,189,290,52,31,true);text(s,'LightGBM   0.9655\nPersistence  0.9777',917,264,296,107,25);
 text(s,'Test winner:\npersistence',917,425,290,124,34,true);
 foot(s,'3,566 validation and 3,567 test hours. Validation informed fitting. Original splits lack a 24-hour purge.');
}
{
 const s=slide(8,'Archived weather inputs');
 text(s,'Retrospective comparison, the same 3,567 test hours',68,142,1130,52,30,false,C.muted);
 const labels=['Original','Day2 forecast','Raw analogue'];
 chart(s,'bar',{left:60,top:227,width:490,height:330},['MAE, W/m²'],research.map((r,i)=>({name:labels[i],values:[r.mae],fill:['#BBBBBB','#777777',C.ink][i],valuesFormatCode:'0.00'})),
  {dataLabels:{showValue:true,position:'outEnd',textStyle:{typeface:'Arial',fontSize:25,fill:C.ink}},yAxis:{min:0,max:16,majorUnit:4,textStyle:{typeface:'Arial',fontSize:21,fill:C.muted},majorGridlines:{fill:C.light,width:1}},legend:{position:'bottom',overlay:false,textStyle:{typeface:'Arial',fontSize:18,fill:C.ink}}});
 const table=s.tables.add({rows:4,columns:4,left:584,top:242,width:627,height:264,columnWidths:[205,151,138,133],
  values:[['','Precision','Recall','F1'],...research.map((r,i)=>[labels[i],...['precision','recall','f1'].map(key=>(100*r[key]).toFixed(2)+'%')])]});
 table.styleOptions={headerRow:false,bandedRows:false};table.borders.assign({fill:'none',width:0});
 for(let r=0;r<4;r++)for(let c=0;c<4;c++){
  const cell=table.getCell(r,c);cell.fill=C.paper;cell.text.style={typeface:'Arial',fontSize:24,bold:r===0,color:r===0?C.muted:C.ink};
 }
 text(s,'Raw analogue lowers MAE. False alarms rise from 15 to 16.',68,570,1135,47,28,true);
 foot(s,'Model-derived reference. Previously inspected test. Historical forecast publication time unverified.',641);
}
{
 const s=slide(9,'Business hypotheses');
 text(s,'Potential customers',68,176,560,54,35,true);text(s,'Water and plant operators\nHotels and managed gardens',68,272,555,126,32);
 text(s,'Commercial model',698,176,510,54,35,true);text(s,'Setup and integration\nSubscription and support',698,272,510,126,32);
 text(s,'Customer interviews and a measured pilot',68,493,1110,100,42,true);
 foot(s,'Pricing, willingness to pay and margins remain untested. No customer agreements claimed.');
}
{
 const s=slide(10,'What the model does not establish');
 text(s,'Declared scenario',68,178,550,62,38,true);
 text(s,'100–400 m³/h production\n4,000 m³ tank\n800 m³ minimum\n3.4 kWh per m³',68,283,555,245,34);
 text(s,'Operator evidence needed',696,178,512,62,38,true);
 text(s,'Pressure and water quality\nFlushing and maintenance\nRamps and operating states\nPlant access to curtailed power',696,283,512,245,31);
 foot(s,'Retrospective demand uses recorded target-day temperature. No plant control or measured savings.');
}
{
 const s=slide(11,'Next evidence');
 text(s,'Submission',68,180,365,63,42,true);text(s,'Confirm the intended\nschedule version\n\nRehearse the offline demo',68,285,345,244,30);
 text(s,'V2 + correction',470,180,350,63,42,true);text(s,`P ${(100*current.precision).toFixed(2)}%  R ${(100*current.recall).toFixed(2)}%\nF1 ${(100*current.f1).toFixed(2)}%\n\n3,566 validation hours`,470,285,350,244,30);
 text(s,'Pilot',873,180,345,63,42,true);text(s,'One operator\nOne data contact\n\nAgreed measurement plan',873,285,335,244,30);
 foot(s,'Versus 008: 4 fewer false alarms, 1 extra miss. Historical validation, not an unseen-data result.');
}
{
 const s=slide(12,'The team and the ask');
 text(s,'A Paphos operator\nand a data contact',64,166,1140,175,66,true,C.white);
 text(s,'Loukas Louka',68,414,550,47,30,false,C.white);
 text(s,'Stefanos Bordea',68,508,550,47,30,false,C.white);
 text(s,'Andreas Nikolaides',715,414,494,47,30,false,C.white);
 text(s,'Cleopas Cleopa',715,508,494,47,30,false,C.white);
 text(s,'aktina-pafos-2026.vercel.app',68,657,1010,30,22,false,C.light);
}

const stage=path.join(app,'build/aktina-deck'),preview=path.join(dir,'previews');
await fs.mkdir(stage,{recursive:true});await fs.mkdir(preview,{recursive:true});
const candidate=path.join(stage,'candidate.pptx');
await(await PresentationFile.exportPptx(p)).save(candidate);
execFileSync(path.join(runtime,'python/bin/python3'),[path.join(dir,'set_metadata.py'),candidate]);
const validation=await finalizePresentation({workspaceDir:app,candidatePath:candidate,finalPath:output,
 pythonExecutable:path.join(runtime,'python/bin/python3'),
 integrityValidatorPath:path.join(skill,'container_tools/inspect_presentation_package_integrity.py'),
 layoutValidatorPath:path.join(skill,'container_tools/inspect_presentation_layout_geometry.py'),
 layoutArgs:['--expected-slide-size-emu','12192000,6858000','--validate-bullet-geometry','--validate-heading-fit','--require-native-table-slide','8'],
 explicitTotalSlideCount:12,requiredNativeChartOwnerSlides:[5,7,8],requiredNativeTableOwnerSlides:[8],materializeLiteralChartWorkbooks:true,
 fontPolicy:{basis:'reference',families:['Arial'],referencePath:path.join(dir,'template.pptx'),referenceSha256:provenance['delivery/Aktina-Deck-Source/template.pptx']},
 verifyArtifactToolImport:true,receiptPath:path.join(stage,`${path.basename(output)}.validation.json`)});
const final=await PresentationFile.importPptx(await FileBlob.load(output));
for(let i=0;i<final.slides.items.length;i++){
 const s=final.slides.items[i],blob=await final.export({slide:s,format:'png',scale:1});
 await fs.writeFile(path.join(preview,`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
 await fs.writeFile(path.join(preview,`slide-${String(i+1).padStart(2,'0')}.layout.json`),await(await s.export({format:'layout'})).text());
}
await fs.writeFile(path.join(dir,'facts.json'),JSON.stringify({source_days:data.days.length,source_rows:data.days.reduce((n,d)=>n+d.rows.length,0),date:day.date,production_m3:sum('aktina'),flat_production_m3:sum('flat'),energy_kwh:energy,cost_eur:{supplied:cost('aktina'),flat:cost('flat')},illustrative_reduction_percent:reduction,start_tank:day.start_tank,end_tank:rows.at(-1).tank,native_charts:4,native_tables:1,slide8_fixed_test_comparison:research},null,2)+'\n');
console.log(JSON.stringify({output,slides:final.slides.items.length,validation},null,2));
