const $ = id => document.getElementById(id);
const data = window.ACTINABENCH;
const percent = value => value == null ? '—' : (100 * value).toFixed(2) + '%';
const names = {persistence:'Same as yesterday',calibrated_persistence:'Calibrated persistence',purged_regression:'Retrained regression',direct_classifier:'Direct classifier',history_classifier:'History classifier',deep_classifier:'Neural network'};
const svg = (body,height,title,width=510) => `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${title}">${body}</svg>`;
function errorChart(rows,label) {
  const width=Math.min(510,$('monthly-errors').getBoundingClientRect().width || 510), plotWidth=width-122;
  const max = Math.max(1,...rows.flatMap(r=>[r.model.mae_w_m2,r.persistence.mae_w_m2]));
  return svg(rows.map((r,i)=>{const y=i*43+7;return `<text x="0" y="${y+16}">${r[label]}</text><rect x="72" y="${y}" width="${plotWidth*r.model.mae_w_m2/max}" height="8" fill="#58d9ef"/><rect x="72" y="${y+12}" width="${plotWidth*r.persistence.mae_w_m2/max}" height="8" fill="#8793a5"/><text class="value" x="${width-8}" y="${y+10}" text-anchor="end">${r.model.mae_w_m2.toFixed(1)}</text><text x="${width-8}" y="${y+24}" text-anchor="end">${r.persistence.mae_w_m2.toFixed(1)}</text>`}).join(''),rows.length*43,'Monthly mean absolute error: LightGBM and persistence',width);
}
function hourlyChart(rows) {
  const width=Math.min(510,$('hourly-errors').getBoundingClientRect().width || 510);
  const max=Math.max(1,...rows.flatMap(r=>[r.model.mae_w_m2,r.persistence.mae_w_m2]));
  const x=i=>35+i*(width-60)/23,y=v=>210-175*v/max;
  const lines=['model','persistence'].map((name,i)=>`<polyline points="${rows.map((r,j)=>`${x(j)},${y(r[name].mae_w_m2)}`).join(' ')}" fill="none" stroke="${i?'#8793a5':'#58d9ef'}" stroke-width="2.5"/>`).join('');
  const ticks=[0,.5,1].map(k=>`<line x1="35" x2="${width-25}" y1="${y(max*k)}" y2="${y(max*k)}" stroke="#303642"/><text x="26" y="${y(max*k)+4}" text-anchor="end">${(max*k).toFixed(0)}</text>`).join('');
  const hours=[0,6,12,18,23].map(i=>`<text x="${x(i)}" y="235" text-anchor="middle">${String(i).padStart(2,'0')}</text>`).join('');
  return svg(ticks+lines+hours+`<text x="${width-25}" y="263" text-anchor="end">Cyprus local hour</text>`,285,'Mean absolute error for each of the 24 target hours; LightGBM and persistence',width);
}
function render(stage) {
  const split=data.original.splits.find(s=>s.split===stage),m=split.model,b=split.persistence;
  document.querySelectorAll('[data-split]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.split===stage)));
  $('period').textContent=`${split.target_start.slice(0,10)} to ${split.target_end.slice(0,10)}, ${m.hours.toLocaleString('en')} hourly predictions`;
  $('verdict').textContent=stage==='test'?'Persistence leads on F1, precision and recall.':'The model’s F1 is slightly higher; its recall is lower.';
  $('metric-comparison').innerHTML=[['f1','F1'],['precision','Precision'],['recall','Recall']].map(([key,name])=>`<section><h3>${name}</h3><dl><div><dt>LightGBM</dt><dd>${percent(m[key])}</dd></div><div><dt>Persistence</dt><dd>${percent(b[key])}</dd></div></dl></section>`).join('');
  $('confusion').innerHTML=[['LightGBM',m],['Persistence',b]].map(([name,r])=>`<section><h3>${name}</h3><dl><dt>Correct sunny calls</dt><dd>${r.true_positive}</dd><dt>False sunny calls</dt><dd>${r.false_positive}</dd><dt>Missed sunny hours</dt><dd>${r.false_negative}</dd><dt>Correct other hours</dt><dd>${r.true_negative}</dd></dl></section>`).join('');
  $('monthly-errors').innerHTML=errorChart(split.monthly,'month');
  $('hourly-errors').innerHTML=hourlyChart(split.hourly);
  $('experiment-caption').textContent=`${stage==='test'?'Full test':'Validation'} period, ${m.hours.toLocaleString('en')} hours per method`;
  $('experiment-rows').innerHTML=Object.entries(data.experiment.methods).map(([key,r])=>{const v=r[stage].selected,selected=key===data.experiment.selected_on_validation;return `<tr data-selected="${selected}"><th scope="row">${names[key]}${selected?'<small>Selected on validation</small>':''}</th><td>${percent(v.f1)}</td><td>${percent(v.precision)}</td><td>${percent(v.recall)}</td><td>${v.fp}</td><td>${v.fn}</td></tr>`}).join('');
}
try {
  if(!data?.original?.splits?.length || data?.experiment?.status!=='COMPLETE')throw Error('Missing report');
  $('bench-results').hidden=false;
  render('test');
  document.querySelectorAll('[data-split]').forEach(button=>button.addEventListener('click',()=>render(button.dataset.split)));
  window.addEventListener('resize',()=>render(document.querySelector('[data-split][aria-pressed=true]').dataset.split));
} catch { $('bench-error').hidden=false; $('bench-results').hidden=true; }
