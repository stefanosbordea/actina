const $ = id => document.getElementById(id);
const data = window.ACTINABENCH;
const percent = value => value == null ? '—' : (100 * value).toFixed(2) + '%';
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const methods = {
  original: ['Original forecast','LightGBM','Stefanos’s retained day-ahead radiation forecast.'],
  persistence: ['Previous-day forecast','Reference','Predicts radiation by reusing the previous day at the same hour.'],
  nwp_day2: ['Archived weather forecast','Research control','Fixed ECMWF day2 radiation forecast. Retrospective comparison on the original weather-model reference.'],
  analogue_raw: ['Weather + past errors','Research prototype','64 similar historical hours estimate forecast uncertainty. Lower test MAE, but one extra false alarm versus the fixed weather forecast.'],
  calibrated_persistence: ['Adjusted previous-day','Experiment','Previous-day radiation with a decision cutoff selected on validation.'],
  purged_regression: ['Retrained forecast','Experiment','LightGBM regression with a 24-hour gap before evaluation.'],
  direct_classifier: ['Direct classifier','Experiment','Predicts whether radiation will exceed 600 W/m².'],
  history_classifier: ['History classifier','Experiment','A classifier using recent weather observations.'],
  deep_classifier: ['Neural network','Experiment','A three-hidden-layer network trained on the same historical inputs.'],
};
const currentMethods = ['original', 'persistence', 'nwp_day2', 'analogue_raw'];
let stage = 'test', selected = 'nwp_day2', view = 'compare', grouping = 'hourly';
const split = () => data.original.splits.find(s => s.split === stage);
function results(key) {
  if (data.research?.methods[key]) return data.research.methods[key][stage];
  if (key !== 'original') return data.experiment.methods[key][stage].selected;
  const m = split().model;
  return {...m,tp:m.true_positive,fp:m.false_positive,fn:m.false_negative,tn:m.true_negative};
}
function delta(value, baseline) {
  if(value == null || baseline == null) return '<p class="metric-delta">Not defined for these observations</p>';
  const d=100*(value-baseline);
  return `<p class="metric-delta" data-direction="${d>0?'up':d<0?'down':'same'}">${d===0?'Equal to reference':`${d>0?'+':'−'}${Math.abs(d).toFixed(2)} percentage points`}</p>`;
}
function scatter() {
  const rows=[...new Set([...currentMethods,selected])].map(key=>({key,...results(key)})).filter(r=>r.precision!=null&&r.recall!=null);
  const width=Math.max(230,$('tradeoff-chart').getBoundingClientRect().width||460),height=Math.max(250,Math.min(330,width*.79));
  const minimum=Math.min(...rows.flatMap(r=>[r.precision,r.recall]))*100;
  const step=minimum>90?2:5,low=Math.floor((minimum-.5)/step)*step,high=100;
  const left=42,right=width-15,top=24,bottom=height-42;
  const x=v=>left+(100*v-low)/(high-low)*(right-left),y=v=>bottom-(100*v-low)/(high-low)*(bottom-top);
  let drawing='<title>Precision and recall for current comparisons</title><desc>Higher values are better. Earlier experiments remain available in the method selector and full table.</desc>';
  for(let t=low;t<=high;t+=step){const px=x(t/100),py=y(t/100);drawing+=`<path d="M${px} ${top}V${bottom}M${left} ${py}H${right}" stroke="#303030" fill="none"/><text x="${px}" y="${bottom+19}" text-anchor="middle">${t}%</text><text x="${left-10}" y="${py+4}" text-anchor="end">${t}%</text>`;}
  drawing+=`<text x="${left}" y="11">Recall</text><text x="${right}" y="${height-2}" text-anchor="end">Precision</text>`;
  const chosen=rows.find(r=>r.key===selected);
  if(chosen)drawing+=`<path d="M${left} ${y(chosen.recall)}H${x(chosen.precision)}V${bottom}" stroke="#ffffff" opacity=".28" stroke-dasharray="3 4" fill="none"/>`;
  for(const r of rows.sort((a,b)=>(a.key===selected)-(b.key===selected))){
    const px=x(r.precision),py=y(r.recall),active=r.key===selected,baseline=r.key==='persistence';
    const marker=baseline?`<path d="m0 -6 6 6 -6 6 -6-6Z" fill="#aaaaaa"/>`:`<circle r="${active?6:4.5}" fill="${active?'#ffffff':'#6b6b6b'}"/>`;
    drawing+=`<g class="plot-point" data-point="${r.key}" role="button" tabindex="0" aria-label="${escape(methods[r.key][0])}, precision ${percent(r.precision)}, recall ${percent(r.recall)}" aria-pressed="${active}" transform="translate(${px} ${py})"><title>${escape(methods[r.key][0])}: precision ${percent(r.precision)}, recall ${percent(r.recall)}</title><circle class="point-halo" r="17"/>${active?'<circle r="12" fill="#ffffff14" stroke="#ffffff" stroke-opacity=".45"/>':''}${marker}</g>`;
    if(active||baseline){const anchor=px>width*.64?'end':'start',dx=anchor==='end'?-10:10;drawing+=`<text x="${px+dx}" y="${py-13}" text-anchor="${anchor}" style="fill:${active?'#ffffff':'#bbbbbb'};font-size:10px">${baseline?'Previous day':'Selected'}</text>`;}
  }
  $('tradeoff-chart').innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Interactive precision and recall comparison">${drawing}</svg>`;
}
function renderComparison() {
  const m=results(selected),b=results('persistence');
  $('model-title').textContent=methods[selected][0];
  $('model-description').textContent=methods[selected][2];
  $('model-kind').textContent=methods[selected][1];
  $('model-select').value=selected;
  document.querySelectorAll('[data-method]').forEach(button=>{
    button.setAttribute('aria-pressed',String(button.dataset.method===selected));
    button.querySelector('strong').textContent=percent(results(button.dataset.method).f1);
  });
  $('metric-comparison').innerHTML=[['precision','Precision'],['recall','Recall'],['f1','F1']].map(([key,label])=>`<section class="metric"><h3>${label}</h3><div class="metric-values"><strong>${percent(m[key])}</strong><span aria-label="Previous-day ${label}: ${percent(b[key])}">${percent(b[key])}</span></div>${delta(m[key],b[key])}</section>`).join('');
  const all=['precision','recall','f1'];
  $('verdict').textContent=selected==='persistence'?'Reference method: repeat the previous day’s radiation at the same hour.':all.some(k=>m[k]==null||b[k]==null)?'One or more scores are undefined for these observations.':all.every(k=>m[k]>b[k])?'Higher precision, recall and F1 than the previous-day forecast for this period.':all.every(k=>m[k]<b[k])?'The previous-day forecast leads on all three scores for this period.':'A tradeoff against the previous-day forecast. No improvement across all three scores.';
  $('outcome-summary').innerHTML=`<div><strong>${m.fp}</strong><span>false calls<small>${b.fp} with the previous-day forecast</small></span></div><div><strong>${m.fn}</strong><span>missed hours<small>${b.fn} with the previous-day forecast</small></span></div>`;
  $('confusion').innerHTML=[[methods[selected][0],m],['Previous-day forecast',b]].map(([name,r])=>`<section><h3>${escape(name)}</h3><dl><dt>Correct positive predictions</dt><dd>${r.tp}</dd><dt>False positive predictions</dt><dd>${r.fp}</dd><dt>Missed positive hours</dt><dd>${r.fn}</dd><dt>Correct negative predictions</dt><dd>${r.tn}</dd></dl></section>`).join('');
  $('selection-note').textContent=data.research?.methods[selected]?(selected==='analogue_raw'?'Research prototype. It did not pass the stronger weather-forecast control for release.':'Fixed archived forecast. Historical publication timing is unverified. No live-accuracy claim.'):selected===data.experiment.selected_on_validation?'Selected by validation F1. This does not establish lower operating costs.':stage==='test'?'Retrospective test against model-derived weather values.':'Validation informed model and cutoff selection. It is not an untouched test.';
  scatter();
}
function renderErrors() {
  const s=split(),rows=s[grouping],monthly=grouping==='monthly';
  document.querySelectorAll('[data-group]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.group===grouping)));
  $('group-column').textContent=monthly?'Month':'Target hour';
  $('error-caption').textContent='Mean absolute error in W/m². Lower is better. '+(monthly?'Month labels include all available observations.':'Target hour in the source’s fixed UTC+03 clock.');
  $('error-rows').innerHTML=rows.map(r=>`<tr><th scope="row">${escape(monthly?r.month:r.hour+':00')}</th><td>${r.model.hours}</td><td>${r.model.mae_w_m2.toFixed(2)}</td><td>${r.persistence.mae_w_m2.toFixed(2)}</td><td>${r.model.rmse_w_m2.toFixed(2)}</td><td>${r.persistence.rmse_w_m2.toFixed(2)}</td></tr>`).join('');
  $('error-scores').innerHTML=[['mae_w_m2','Mean absolute error'],['rmse_w_m2','Root mean square error']].map(([k,name])=>`<section><h3>${name}</h3><p>${s.model[k].toFixed(2)}<span>${s.persistence[k].toFixed(2)}</span></p><small>Original / previous-day, W/m²</small></section>`).join('');
  const width=Math.max(230,$('error-chart').getBoundingClientRect().width||640),height=monthly?rows.length*42+35:285;
  const max=Math.max(1,...rows.flatMap(r=>[r.model.mae_w_m2,r.persistence.mae_w_m2]));
  let drawing='';
  if(monthly){const plot=width-116;drawing=rows.map((r,i)=>{const y=i*42+8;return `<text x="0" y="${y+14}" style="font-size:10px">${new Date(r.month+'-01T12:00:00').toLocaleDateString('en-GB',{month:'short'})}</text><rect x="49" y="${y}" width="${plot*r.model.mae_w_m2/max}" height="7" rx="2" fill="#ffffff"/><rect x="49" y="${y+12}" width="${plot*r.persistence.mae_w_m2/max}" height="7" rx="2" fill="#888888"/><text x="${width-2}" y="${y+8}" text-anchor="end">${r.model.mae_w_m2.toFixed(1)}</text><text x="${width-2}" y="${y+22}" text-anchor="end">${r.persistence.mae_w_m2.toFixed(1)}</text>`}).join('');}
  else{const x=i=>34+i*(width-49)/23,y=v=>245-v/max*215;
    drawing=[0,.25,.5,.75,1].map(k=>`<path d="M34 ${y(max*k)}H${width-15}" stroke="#303030"/><text x="26" y="${y(max*k)+4}" text-anchor="end">${(max*k).toFixed(0)}</text>`).join('');
    drawing+=['model','persistence'].map((key,i)=>`<polyline points="${rows.map((r,j)=>`${x(j)},${y(r[key].mae_w_m2)}`).join(' ')}" fill="none" stroke="${i?'#888888':'#ffffff'}" stroke-width="2" ${i?'stroke-dasharray="5 4"':''}/>`).join('');
    drawing+=[0,6,12,18,23].map(i=>`<text x="${x(i)}" y="268" text-anchor="middle">${String(i).padStart(2,'0')}</text>`).join('');
  }
  $('error-chart').innerHTML=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Original forecast and previous-day mean absolute error by ${monthly?'month':'hour'}. Exact values in the table below">${drawing}</svg>`;
}
function render() {
  const s=split();
  document.querySelectorAll('[data-split]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.split===stage)));
  const date=value=>new Date(value.replace(' ','T')).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
  $('period').innerHTML=`<span>${escape(date(s.target_start))} – ${escape(date(s.target_end))}</span> <span>${s.model.hours.toLocaleString('en')} hours</span>`;
  $('experiment-caption').textContent=`${stage==='test'?'Test':'Validation'} period. All ${s.model.hours.toLocaleString('en')} retained hours for every method.`;
  $('experiment-rows').innerHTML=Object.keys(methods).map(key=>{const r=results(key);return `<tr data-method-result="${key}"><th scope="row">${escape(methods[key][0])}</th><td>${percent(r.precision)}</td><td>${percent(r.recall)}</td><td>${percent(r.f1)}</td><td>${r.fp}</td><td>${r.fn}</td></tr>`}).join('');
  $('coverage').innerHTML=[['Active period',stage==='test'?'Test':'Validation'],['First target hour',s.target_start],['Last target hour',s.target_end],['Retained hours',s.model.hours.toLocaleString('en')],['Actual positive hours',(s.model.true_positive+s.model.false_negative).toLocaleString('en')],['Clock','Source labels resolve to fixed UTC+03. Not a daylight-saving clock']].map(([k,v])=>`<div><dt>${k}</dt><dd>${escape(v)}</dd></div>`).join('');
  renderComparison();renderErrors();
}
function choose(key){if(!methods[key])return;selected=key;renderComparison();}
function showView(next) {
  view=next;
  document.querySelectorAll('[data-view]').forEach(button=>{const active=button.dataset.view===view;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;$(button.getAttribute('aria-controls')).hidden=!active;});
  if(view==='compare')scatter();if(view==='errors')renderErrors();
}
try {
  if(!data?.original?.splits?.length||data?.experiment?.status!=='COMPLETE')throw Error('Missing report');
  for(const period of ['test','validation'])for(const key of Object.keys(methods)){const s=data.original.splits.find(r=>r.split===period),r=key==='original'?s.model:data.research?.methods[key]?.[period]||data.experiment.methods[key]?.[period]?.selected;if(!r||!Number.isInteger(r.hours)||r.hours<1||r.hours!==s.model.hours||['precision','recall','f1'].some(k=>r[k]!=null&&(!Number.isFinite(r[k])||r[k]<0||r[k]>1)))throw Error('Invalid report');}
  const option=key=>`<button class="model-option" data-method="${key}" aria-pressed="false"><span>${methods[key][0]}</span><strong></strong></button>`;
  $('model-list').innerHTML=currentMethods.map(option).join('')+'<details class="detail-disclosure"><summary>Earlier experiments</summary>'+Object.keys(methods).filter(key=>!currentMethods.includes(key)).map(option).join('')+'</details>';
  $('model-select').innerHTML=Object.entries(methods).map(([key,[name]])=>`<option value="${key}">${name}</option>`).join('');
  $('model-list').addEventListener('click',event=>{const button=event.target.closest('[data-method]');if(button)choose(button.dataset.method);});
  $('model-select').addEventListener('change',event=>choose(event.target.value));
  const pickPoint=event=>{const point=event.target.closest('[data-point]');if(!point)return;if(event.type==='keydown'&&!['Enter',' '].includes(event.key))return;event.preventDefault();const key=point.dataset.point;choose(key);if(event.type==='keydown')document.querySelector(`[data-point="${key}"]`).focus();};
  $('tradeoff-chart').addEventListener('click',pickPoint);$('tradeoff-chart').addEventListener('keydown',pickPoint);
  document.querySelectorAll('[data-split]').forEach(button=>button.addEventListener('click',()=>{stage=button.dataset.split;render();}));
  document.querySelectorAll('[data-group]').forEach(button=>button.addEventListener('click',()=>{grouping=button.dataset.group;renderErrors();}));
  const tabs=[...document.querySelectorAll('[data-view]')];
  tabs.forEach((button,index)=>{button.addEventListener('click',()=>showView(button.dataset.view));button.addEventListener('keydown',event=>{let next;if(event.key==='ArrowRight')next=(index+1)%tabs.length;if(event.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;if(next!==undefined){event.preventDefault();showView(tabs[next].dataset.view);tabs[next].focus();}});});
  $('bench-results').hidden=false;render();
  let resizeFrame;window.addEventListener('resize',()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{if(view==='compare')scatter();if(view==='errors')renderErrors();});});
} catch(error) { $('bench-error').hidden=false;$('bench-results').hidden=true;console.error('AktinaBench:',error.message); }
