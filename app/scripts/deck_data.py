"""Derive pitch numbers from the frozen evaluation and selected historical day."""
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.scheduler import schedule_day
from model.sites import sites_day

predictions = pd.read_csv(ROOT / 'data/test_predictions.csv')
weather = pd.read_csv(ROOT / 'data/paphos_weather.csv')
for frame in [predictions, weather]:
    frame['time'] = pd.to_datetime(frame.time, utc=True).dt.tz_convert('Asia/Nicosia')
chosen = predictions[predictions.time.dt.date == pd.Timestamp('2026-07-15').date()].sort_values('time')
if len(chosen) != 24:
    raise ValueError('Deck example needs the complete 15 July 2026 test day')
day_weather = weather.set_index('time').reindex(chosen.time)
grid = schedule_day(chosen.predicted.tolist(), chosen.actual.tolist(), day_weather.temperature_2m.tolist())
sites = sites_day(day_weather.et0_fao_evapotranspiration.sum(), precipitation_mm=day_weather.precipitation.sum())
data = {
    'day': '2026-07-15',
    'grid': grid['totals'],
    'grid_frame': grid['frame'].to_dict(orient='list'),
    'sites': sites['irrigation'],
    'detector': sites['detector'],
    'metrics': json.loads((ROOT / 'results/metrics.json').read_text()),
    'review': json.loads((ROOT / 'results/independent-review.json').read_text()),
}
(ROOT / 'build').mkdir(exist_ok=True)
(ROOT / 'build/deck-data.json').write_text(json.dumps(data, indent=2) + '\n')
print('Prepared build/deck-data.json from frozen evidence inputs.')
