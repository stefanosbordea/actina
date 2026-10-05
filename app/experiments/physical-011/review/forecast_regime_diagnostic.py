"""Forecast-only coverage diagnostic. No reference values or outcomes are loaded."""
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

HERE=Path(__file__).resolve().parent
EXP=HERE.parent
ROOT=EXP.parents[2]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream))
def ratio(ghi):return np.minimum(1700.,1.7*np.maximum(np.asarray(ghi,dtype=float),0.)).sum(axis=-1)/9792.
def statistics(x):
    x=np.asarray(x,dtype=float)
    return dict(zip(('min','q25','median','q75','max'),map(float,np.quantile(x,[0,.25,.5,.75,1.],method='linear'))))


def main():
    frozen=json.loads((EXP/'result/planning-freeze.json').read_text())['files_sha256']
    pins=json.loads((EXP/'inputs.json').read_text())
    source_path=ROOT/'app/experiments/f1-008/result/features.csv'
    times_path=ROOT/'app/experiments/f1-006/result/feature-targets.csv'
    for path in (source_path,times_path):
        if sha(path)!=pins[str(path.relative_to(ROOT))]:raise ValueError('Pinned source changed')
    # Read only source forecast and timestamps. No actual or satellite columns are accessed.
    source=np.asarray([float(row['nwp_day2_radiation']) for row in rows(source_path)])
    targets=[datetime.fromisoformat(row['target_time']) for row in rows(times_path)]
    identities={str(p.relative_to(ROOT)):sha(p) for p in (source_path,times_path,EXP/'inputs.json',EXP/'result/planning-freeze.json')}
    output=[];bank_output=[];summary={}
    for stage in ('validation','test'):
        paths=[EXP/'result'/stage/name for name in ('bank.npz','plans.npz','plan-metadata.csv')]
        for path in paths:
            if sha(path)!=frozen[str(path.relative_to(EXP/'result'))]:raise ValueError('Frozen planning artifact changed')
            identities[str(path.relative_to(ROOT))]=sha(path)
        with np.load(paths[0],allow_pickle=False) as bank:
            bank_nwp=bank['nwp'];bank_indices=bank['source_positions']
        with np.load(paths[1],allow_pickle=False) as plans:
            forecast=plans['raw_forecast_ghi'];forecast_indices=plans['target_positions']
        metadata=rows(paths[2]);cutoff=datetime.fromisoformat(metadata[0]['issue_time'])
        if bank_nwp.shape!=(64,24) or forecast.shape!=(len(metadata),24):raise ValueError('Shape mismatch')
        np.testing.assert_array_equal(bank_nwp,source[bank_indices])
        np.testing.assert_array_equal(forecast,source[forecast_indices])
        latest=max(targets[int(p)] for p in bank_indices.reshape(-1))
        if latest>=cutoff:raise ValueError('Historical bank reaches issue')
        bank_ratio=ratio(bank_nwp);forecast_ratio=ratio(forecast)
        if not np.isfinite(bank_ratio).all() or not np.isfinite(forecast_ratio).all():raise ValueError('Nonfinite descriptor')
        for d,indices in enumerate(bank_indices):
            bank_output.append(dict(stage=stage,source_endpoint_day=targets[int(indices[0])].date().isoformat(),
                                    forecast_pv_kwh=float(bank_ratio[d]*9792),supply_to_load_ratio=float(bank_ratio[d])))
        for d,item in enumerate(metadata):
            issue=datetime.fromisoformat(item['issue_time'])
            target=[targets[int(p)] for p in forecast_indices[d]]
            if len(target)!=24 or len(set(target))!=24 or target[0].date().isoformat()!=item['day']:raise ValueError('Horizon identity')
            if any(t-timedelta(hours=48)>=issue for t in target):raise ValueError('Nominal forecast time reaches issue')
            value=float(forecast_ratio[d]);minimum=float(bank_ratio.min());maximum=float(bank_ratio.max())
            output.append(dict(stage=stage,endpoint_day=item['day'],issue_time=item['issue_time'],forecast_pv_kwh=value*9792,
                supply_to_load_ratio=value,bank_min_ratio=minimum,bank_max_ratio=maximum,
                bank_fraction_at_or_below=float(np.mean(bank_ratio<=value)),below_bank_min=value<minimum,above_bank_max=value>maximum,
                nearest_bank_ratio_gap=float(np.min(abs(bank_ratio-value))),
                latest_bank_source_age_hours=(issue-latest).total_seconds()/3600))
        current=[row for row in output if row['stage']==stage]
        summary[stage]=dict(horizons=len(current),bank_horizons=64,bank_ratio=statistics(bank_ratio),forecast_ratio=statistics(forecast_ratio),
            below_bank_min=sum(r['below_bank_min'] for r in current),above_bank_max=sum(r['above_bank_max'] for r in current),
            nearest_bank_ratio_gap=statistics([r['nearest_bank_ratio_gap'] for r in current]),
            latest_bank_source_age_hours=statistics([r['latest_bank_source_age_hours'] for r in current]),months={})
        for month in sorted(set(r['endpoint_day'][:7] for r in current)):
            selected=[r for r in current if r['endpoint_day'].startswith(month)]
            summary[stage]['months'][month]=dict(horizons=len(selected),median_ratio=float(np.median([r['supply_to_load_ratio'] for r in selected])),
                below_bank_min=sum(r['below_bank_min'] for r in selected),above_bank_max=sum(r['above_bank_max'] for r in selected))
    for path,digest in identities.items():
        if sha(ROOT/path)!=digest:raise ValueError('Source changed during diagnostic')
    for name,table in [('forecast-regime-horizons.csv',output),('forecast-regime-bank.csv',bank_output)]:
        with (HERE/name).open('x',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    result=dict(status='COMPLETE',recorded_at_utc=datetime.now(timezone.utc).isoformat(),command=[sys.executable,*sys.argv],code_sha256=sha(Path(__file__)),
        descriptor='Sum of illustrative raw-forecast PV kWh across24 one-hour intervals divided by fixed9792kWh production demand.',
        source_sha256=identities,stages=summary,no_reference_values_or_outcomes_used=True,no_fitting_or_new_scheduling=True,
        limitation='Nominal archive timestamps satisfy issue chronology, but historical publication availability is unverified. Forecast coverage alone does not establish residual-law shift or explain outcome differences.')
    with (HERE/'forecast-regime-diagnostic.json').open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
