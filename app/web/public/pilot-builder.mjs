import {pilotKinds,validatePilotContract} from './pilot.mjs';

const names={tank_storage_m3:'Tank storage',unit_load_kw:'Unit power',production_rate_m3_h:'Production rate',delivered_flow_m3_h:'Delivered flow',available_power_kw:'Reported available power'};
export const builderTemplate=`<details class="panel"><summary>Build a source declaration</summary><p class="micro">Enter your source, window and asset limits. Blank fields have no assumed values. This form uses the same numeric validator as imported declarations.</p><form id="pilot-builder-form"><div class="columns"><label>Declaration label<input id="builder-label" maxlength="200"></label><label>Source kind<select id="builder-source-kind"><option value="">Choose a source kind</option><option value="operator_observations">Operator-declared observations</option><option value="synthetic_fixture">Synthetic fixture</option></select></label><label>Source label<input id="builder-source-label" maxlength="200"></label><label>Cadence<select id="builder-cadence"><option value="">Choose a cadence</option><option value="15">15 minutes</option><option value="60">60 minutes</option></select></label><label>Window start / inclusive ISO time<input id="builder-start" placeholder="YYYY-MM-DDTHH:mm:ss+hh:mm" maxlength="40"></label><label>Window end / exclusive ISO time<input id="builder-end" placeholder="YYYY-MM-DDTHH:mm:ss+hh:mm" maxlength="40"></label><label>Review as of / optional ISO time<input id="builder-review" maxlength="40" placeholder="Blank: latest first-available input"></label></div><p class="micro">Supported display zone: Europe/Nicosia. Times require seconds and an explicit offset. Units follow the selected measurement; limits remain your declaration.</p><div id="builder-assets"></div><button id="builder-add-asset" type="button">Add asset</button><div class="actions"><button type="submit">Validate and apply declaration</button><button id="builder-export" type="button">Validate and export declaration</button></div></form><p id="builder-status" role="status">No draft applied. Accepted intake stays unchanged until a valid declaration is applied.</p></details>`;

export function setupPilotBuilder({$,download,onApply,invalidatePending}){
 const input=(field,label,attrs={})=>{const wrap=document.createElement('label');wrap.textContent=label;const el=document.createElement('input');el.dataset.field=field;Object.assign(el,attrs);wrap.append(el);return wrap;};
 const button=(label,fn)=>{const el=document.createElement('button');el.type='button';el.textContent=label;el.onclick=fn;return el;};
 const number=input=>input.value.trim()===''?null:Number(input.value);
 function measurement(host){
  const row=document.createElement('div');row.className='builder-measurement columns';
  const label=document.createElement('label');label.textContent='Measurement';const select=document.createElement('select');select.dataset.field='measurement';select.add(new Option('Choose a measurement',''));Object.entries(names).forEach(([kind,name])=>select.add(new Option(name,kind)));label.append(select);row.append(label,input('unit','Schema unit',{readOnly:true}),input('min','Declared minimum',{type:'number',step:'any'}),input('max','Declared maximum',{type:'number',step:'any'}));
  select.onchange=()=>row.querySelector('[data-field="unit"]').value=pilotKinds[select.value]??'';
  row.append(button('Remove measurement',()=>{row.remove();limits(host.closest('.builder-asset'));}));host.append(row);
 }
 function limits(asset){
  const rows=asset.querySelectorAll('.builder-measurement');asset.querySelector('[data-add-measurement]').disabled=rows.length>=5;rows.forEach(row=>row.querySelector('button').disabled=rows.length===1);
  const assets=$('builder-assets').querySelectorAll('.builder-asset');$('builder-add-asset').disabled=assets.length>=20;assets.forEach(a=>a.querySelector('[data-remove-asset]').disabled=assets.length===1);
 }
 function addAsset(){
  const asset=document.createElement('fieldset');asset.className='builder-asset';const legend=document.createElement('legend');legend.textContent='Declared asset';asset.append(legend);const fields=document.createElement('div');fields.className='columns';fields.append(input('asset_id','Asset ID',{maxLength:64}),input('label','Asset label',{maxLength:200}),input('tank_reserve_m3','Optional tank reserve / m³',{type:'number',step:'any'}));asset.append(fields);const host=document.createElement('div');host.className='builder-measurements';asset.append(host);measurement(host);
  const add=button('Add measurement',()=>{measurement(host);limits(asset);});add.dataset.addMeasurement='';const remove=button('Remove asset',()=>{asset.remove();const first=$('builder-assets').querySelector('.builder-asset');if(first)limits(first);});remove.dataset.removeAsset='';asset.append(add,remove);$('builder-assets').append(asset);limits(asset);
 }
 function draft(){
  const assets=[...$('builder-assets').querySelectorAll('.builder-asset')].map(asset=>{
   const field=name=>asset.querySelector(`:scope > .columns [data-field="${name}"]`),value={asset_id:field('asset_id').value.trim(),label:field('label').value.trim(),measurements:[...asset.querySelectorAll('.builder-measurement')].map(row=>{const f=name=>row.querySelector(`[data-field="${name}"]`);return {measurement:f('measurement').value,unit:f('unit').value,min:number(f('min')),max:number(f('max'))};})};
   if(field('tank_reserve_m3').value.trim()!=='')value.tank_reserve_m3=number(field('tank_reserve_m3'));return value;
  });
  const value={schema:1,label:$('builder-label').value.trim(),source_kind:$('builder-source-kind').value,source_label:$('builder-source-label').value.trim(),timezone:'Europe/Nicosia',window:{start:$('builder-start').value.trim(),end:$('builder-end').value.trim()},cadence_minutes:number($('builder-cadence')),assets};
  if($('builder-review').value.trim())value.review_as_of=$('builder-review').value.trim();return value;
 }
 function checked(){const value=draft(),r=validatePilotContract(value);if(r.issues.length){$('builder-status').textContent=`Draft blocked / ${r.issues.map(i=>`${i.field}: ${i.message}`).join(' ')} Accepted intake remains unchanged.`;return null;}return {value,text:JSON.stringify(value,null,2)+'\n'};}
 $('builder-add-asset').onclick=addAsset;
 $('pilot-builder-form').onsubmit=async e=>{e.preventDefault();invalidatePending();const candidate=checked();if(!candidate)return;try{const applied=await onApply(candidate.value,candidate.text);if(applied)$('builder-status').textContent='Declaration applied numerically. Prior observations were cleared; import readings for these declared assets.';}catch(e){$('builder-status').textContent=`${e.message} Accepted intake remains unchanged.`;}};
 $('builder-export').onclick=()=>{const candidate=checked();if(!candidate)return;download('aktina-form-source-declaration.json',candidate.text,'application/json');$('builder-status').textContent='Declaration export ready. Accepted intake remains unchanged until you apply a valid declaration.';};
 addAsset();
}
