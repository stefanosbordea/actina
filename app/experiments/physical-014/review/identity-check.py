"""Exact-identity checks supporting the final 014 summary."""
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'result'
OLD=HERE.parent.parent/'physical-012/result'
raw_count=control_values=0
changes=[]
for stage in ('validation','test'):
    with (OUT/stage/'raw-reproduction.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            assert row['exactly_equal']=='True' and float(row['maximum_difference_m3'])==0
            raw_count+=1
    with (OLD/stage/'daily-outcomes.csv').open(newline='') as stream:
        archived={(r['day'],r['method'],r['reference']):r for r in csv.DictReader(stream)}
    with (OUT/stage/'daily-outcomes.csv').open(newline='') as stream:
        for row in csv.DictReader(stream):
            key=(row['day'],row['method'],row['reference'])
            if key not in archived:
                continue
            for metric,value in archived[key].items():
                if metric not in ('day','method','reference','primary','weather_sensitivity'):
                    assert float(row[metric])==float(value)
                    control_values+=1
    with np.load(OUT/stage/'plans.npz',allow_pickle=False) as archive:
        q,mapped,raw,methods=archive['production'],archive['mapped_forecast_ghi'],archive['raw_forecast_ghi'],archive['methods']
    with (OUT/stage/'plan-metadata.csv').open(newline='') as stream:
        days=[r['day'] for r in csv.DictReader(stream)]
    for d,day in enumerate(days):
        for c,method in enumerate(methods[6:]):
            changed=np.flatnonzero(mapped[d,c]!=raw[d]).tolist()
            if changed:
                changes.append(dict(period=stage,day=day,method=str(method),changed_hours=changed,maximum_production_difference_m3=float(np.abs(q[d,c+6]-q[d,1]).max())))
            else:
                assert q[d,c+6].tobytes()==q[d,1].tobytes()
assert raw_count==299 and control_values==56160 and len(changes)==2
assert all(r['period']=='validation' and r['day']=='2026-05-02' and len(r['changed_hours'])==2 for r in changes)
print(json.dumps(dict(status='PASS',exact_raw_replays=raw_count,exact_archived_numeric_outcomes=control_values,changed_inputs=changes,checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2))
