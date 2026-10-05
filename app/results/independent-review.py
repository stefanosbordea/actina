"""Independent stronger-persistence and schedule-attribution review of frozen predictions.

Run from AquaShift: .venv/bin/python results/independent-review.py
"""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.scheduler import schedule_day
from model.train import load_weather
from eval.evaluate import bootstrap_days, confusion, regression


def run():
    weather = load_weather(ROOT / 'data/paphos_weather.csv')
    p = pd.read_csv(ROOT / 'data/test_predictions.csv')
    p.index = pd.DatetimeIndex(pd.to_datetime(p.time, utc=True)).tz_convert('Asia/Nicosia')
    issue = pd.DatetimeIndex(pd.to_datetime(p.forecast_issue_time, utc=True))
    source = p.index-pd.to_timedelta(np.where(p.index.hour <= 18, 24, 48), unit='h')
    if not (source <= issue).all():
        raise AssertionError('Persistence source exceeds forecast issue')
    p['older_day2_persistence'] = weather.shortwave_radiation.reindex(p.index-pd.Timedelta(hours=48)).to_numpy()
    p['latest_available_persistence'] = weather.shortwave_radiation.reindex(source).to_numpy()
    if not np.isfinite(p.latest_available_persistence).all():
        raise AssertionError('Latest safe persistence has missing source values')
    threshold = 600
    scores = {name: regression(p.actual, p[col]) for name, col in
              [('frozen_model', 'predicted'), ('older_day2_persistence', 'older_day2_persistence'),
               ('latest_available_persistence', 'latest_available_persistence'), ('train_only_climatology', 'climatology')]}
    fresh = p.copy()
    fresh['baseline'] = p.latest_available_persistence
    fresh['baseline_day2'] = p.older_day2_persistence
    strong_ci = bootstrap_days(fresh)['baseline']
    rows = []
    for day, part in p.groupby(p.index.date):
        if len(part) != 24 or list(part.index.hour) != list(range(24)):
            raise AssertionError('Schedule comparison requires exactly 24 ordered local hours')
        actual = part.actual.to_numpy()
        temperature = weather.temperature_2m.reindex(part.index).to_numpy()
        strategies = dict(frozen_model=part.predicted.to_numpy(),
                          latest_available_persistence=part.latest_available_persistence.to_numpy(),
                          train_only_climatology=part.climatology.to_numpy(),
                          price_only=np.zeros(24))
        for name, forecast in strategies.items():
            r = schedule_day(forecast, actual, temperature, threshold=threshold)
            rows.append(dict(date=str(day), strategy=name, **r['totals']))
    runs = pd.DataFrame(rows)
    runs.to_csv(ROOT / 'results/schedule-attribution.csv', index=False)
    aggregated = {}
    for name, group in runs.groupby('strategy'):
        aggregated[name] = dict(days=len(group), total_water_m3=float(group.water_produced_m3.sum()),
                                total_energy_kwh=float(group.energy_kwh.sum()),
                                total_scenario_cost_eur=float(group.cost_eur.sum()),
                                mean_actual_high_radiation_energy_share_pct=float(group.scheduled_solar_proxy_share_pct.mean()),
                                total_safety_violations=int(group.safety_violations.sum()),
                                max_terminal_storage_error_m3=float((group.final_storage_m3-group.initial_storage_m3).abs().max()))
    price_only = runs[runs.strategy == 'price_only'].set_index('date')
    attribution = {}
    for name in ('frozen_model', 'latest_available_persistence', 'train_only_climatology'):
        group = runs[runs.strategy == name].set_index('date')
        attribution[name] = dict(total_scenario_cost_saving_vs_price_only_eur=float((price_only.cost_eur-group.cost_eur).sum()),
                                max_absolute_daily_cost_difference_eur=float((price_only.cost_eur-group.cost_eur).abs().max()),
                                actual_high_radiation_share_difference_vs_price_only_percentage_points=float((group.scheduled_solar_proxy_share_pct-price_only.scheduled_solar_proxy_share_pct).mean()))
    result = dict(scope='Independent retrospective frozen-model review; no operational or measured plant/grid benefit',
                  rows=len(p), days=len(set(p.index.date)), threshold_w_m2=threshold,
                  latest_persistence_rule='Same local hour one date earlier for target hours00–18; two dates earlier for19–23, all source times<=prior18:00issue',
                  regression=scores, latest_available_persistence_bootstrap=strong_ci,
                  proxy_confusion={name:confusion(p.actual,p[col],threshold) for name,col in [('model','predicted'),('latest_available_persistence','latest_available_persistence')]},
                  matched_schedule_scenarios=aggregated, forecast_attribution=attribution,
                  verdicts=['The frozen model does not beat the stronger latest-available persistence baseline on this test period.',
                            'No material AI cost benefit is established: scenario clock tariffs drive the saving; forecasts only rank production inside tied tariff hours.',
                            'Changes in high-radiation allocation are weather-proxy outcomes, not actual curtailed energy or carbon.',
                            'Source-time checks are theoretical temporal cutoffs, not certification of original historical publication vintages.'],
                  command='.venv/bin/python results/independent-review.py',
                  source_sha256={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in
                                 [Path(__file__),ROOT/'model/scheduler.py',ROOT/'model/train.py',ROOT/'eval/evaluate.py',ROOT/'data/test_predictions.csv',ROOT/'data/paphos_weather.csv']})
    (ROOT/'results/independent-review.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'regression':scores,'forecast_attribution':attribution},separators=(',',':')))


if __name__ == '__main__':
    run()
