"""Build public, deterministic demo data from the retained reference experiment."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.scheduler import schedule_day
from model.sites import sites_day
from model.train import load_weather

OUT = Path(__file__).resolve().parent
weather = load_weather(ROOT / 'data/paphos_weather.csv')
predictions = pd.read_csv(ROOT / 'data/test_predictions.csv')
predictions.index = pd.DatetimeIndex(pd.to_datetime(predictions.time, utc=True)).tz_convert('Asia/Nicosia')
review = json.loads((ROOT / 'results/independent-review.json').read_text())
tanks = [500, 1000, 2000, 4000, 8000]
keys = ['water_produced_m3', 'water_demand_m3', 'unmet_demand_m3', 'energy_kwh', 'baseline_energy_kwh',
        'cost_eur', 'baseline_cost_eur', 'cost_saving_eur', 'cost_saving_percent', 'safety_violations',
        'safety_minimum_m3', 'initial_storage_m3', 'final_storage_m3', 'min_storage_m3', 'max_storage_m3',
        'scheduled_solar_proxy_share_pct', 'baseline_solar_proxy_share_pct', 'co2_saving_kg']
days = []
for day, part in predictions.groupby(predictions.index.date):
    assert len(part) == 24 and list(part.index.hour) == list(range(24))
    w = weather.reindex(part.index)
    entry = dict(date=str(day), times=part.time.tolist(), issues=part.forecast_issue_time.tolist(), baseline_sources=part.baseline_source_time.tolist(), actual=part.actual.tolist(), predicted=part.predicted.tolist(),
                 baseline=part.baseline.tolist(), climatology=part.climatology.tolist(),
                 temperature=w.temperature_2m.tolist(), cloud_cover=[float(v) if pd.notna(v) and np.isfinite(v) else None for v in w.cloud_cover], schedules={})
    for tank in tanks:
        result = schedule_day(part.predicted.to_numpy(), part.actual.to_numpy(), w.temperature_2m.to_numpy(), tank_capacity=tank)
        frame, totals = result['frame'], result['totals']
        assert totals['safety_violations'] == 0 and totals['unmet_demand_m3'] == 0
        assert abs(totals['initial_storage_m3'] - totals['final_storage_m3']) < 1e-6
        assert abs(totals['energy_kwh'] - totals['baseline_energy_kwh']) < 1e-6
        assert abs(frame.scheduled_m3.sum() - frame.demand_m3.sum()) < 1e-6
        assert frame.scheduled_m3.between(-1e-6, 500 + 1e-6).all()
        assert frame.storage_m3.between(tank * .2 - 1e-6, tank + 1e-6).all()
        entry['schedules'][str(tank)] = dict(production=frame.scheduled_m3.tolist(), storage=frame.storage_m3.tolist(),
            storage_start=frame.storage_start_m3.tolist(), totals={key:totals[key] for key in keys})
        entry['prices'] = frame.price_eur_mwh.tolist()
    eto, rain = float(w.et0_fao_evapotranspiration.sum()), float(w.precipitation.sum())
    entry['sites'] = dict(eto=eto, rain=rain)
    for label, leak in [('normal', False), ('leak', True)]:
        fixture = sites_day(eto, precipitation_mm=rain, inject_leak=leak)
        entry['sites'][label] = dict(flow=fixture['meter_frame'].flow_m3_hour.tolist(),
            alerts=fixture['meter_frame'].alert.tolist(), detector=fixture['detector'])
        entry['sites']['irrigation'] = fixture['irrigation']
    days.append(entry)
assert len(days) == 92
payload = dict(schema=1, tanks=tanks, threshold=600, unit_capacity=500, demand=120, kwh_per_m3=3.4,
               weather=dict(rows=len(weather), first=weather.index.min().isoformat(), last=weather.index.max().isoformat(),
                            kind='Open-Meteo ECMWF IFS historical gridded reconstruction', timezone='Asia/Nicosia'),
               quality=dict(rows=len(predictions), duplicate_times=int(predictions.index.duplicated().sum()),
                            nonfinite_values=int((~np.isfinite(predictions[['actual','predicted','baseline','climatology']].to_numpy())).sum()),
                            ordered=bool(predictions.index.is_monotonic_increasing)),
               scores=review['regression'], attribution=review['forecast_attribution'], days=days)
public = OUT / 'public'
public.mkdir(parents=True, exist_ok=True)
target = public / 'data.json'
target.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False)+'\n')
(public / 'manifest.json').write_text(json.dumps(dict(schema=1, data_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    days=len(days), rows=len(predictions), schedules=len(days)*len(tanks),
    method='Canonical SciPy/HiGHS scenario schedules; no measured grid surplus or plant connection',
    nominal_issue='18:00 previous local date', test_period='2026-07-01 through 2026-09-30',
    forecast_scope='Independent frozen reference; team model remains replaceable',
    source_url='https://open-meteo.com/en/docs/historical-weather-api', source_license='CC BY 4.0'),indent=2)+'\n')
paths = ['web/generate.py', 'model/scheduler.py', 'model/sites.py', 'model/train.py',
         'data/test_predictions.csv', 'data/paphos_weather.csv', 'results/independent-review.json']
check = dict(command='.venv/bin/python web/generate.py', status='PASS', days=len(days), schedules=len(days)*len(tanks),
    checks='All canonical schedules: equal water/energy, no unmet demand, safe storage, unit capacity, equal terminal inventory.',
    source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
    public_data_sha256=hashlib.sha256(target.read_bytes()).hexdigest(), public_data_bytes=target.stat().st_size)
(OUT / 'data-check.json').write_text(json.dumps(check, indent=2)+'\n')
print(json.dumps({k:v for k,v in check.items() if k!='source_sha256'}))
