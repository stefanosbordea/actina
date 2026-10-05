"""Package Stefanos's retained schedule for the website; never fit or schedule."""
import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / 'app/site'
MODEL_COMMIT = '2a093aba97f6ad615c43fa7c514044342af16e3a'
FIELDS = ('actual', 'forecast', 'demand', 'flat', 'aktina', 'tank')


def prepare(root=ROOT):
    schedule = root / 'eval/schedule_hourly.csv'
    forecasts = {}
    for filename, period in [('cv_predictions.csv', 'winter–spring'), ('test_predictions.csv', 'summer')]:
        with (root / 'eval' / filename).open(newline='') as source:
            for row in csv.DictReader(source):
                # Prediction CSV indices identify the feature day. scheduler.py shifts +24 h.
                target = (datetime.fromisoformat(row['time']) + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
                if target in forecasts:
                    raise ValueError('Overlapping prediction periods')
                forecasts[target] = (period, float(row['actual']), float(row['predicted']), float(row['baseline']))
    grouped = defaultdict(list)
    with schedule.open(newline='') as source:
        reader = csv.DictReader(source)
        if tuple(k.strip() for k in reader.fieldnames) != ('time', *FIELDS):
            raise ValueError('Unexpected schedule columns')
        for original in reader:
            row = {k.strip(): v for k, v in original.items()}
            timestamp = datetime.fromisoformat(row['time'])
            if timestamp.tzinfo is not None or timestamp.minute or timestamp.second:
                raise ValueError('Expected hourly Cyprus wall-clock labels')
            parsed = {'time': row['time'], **{k: float(row[k]) for k in FIELDS}}
            if not all(math.isfinite(parsed[k]) and parsed[k] >= 0 for k in FIELDS):
                raise ValueError('Nonfinite or negative schedule value')
            period, actual, predicted, baseline = forecasts[parsed['time']]
            if parsed['actual'] != actual:
                raise ValueError('Schedule actual does not match original predictions')
            parsed['model_forecast'] = predicted
            parsed['baseline'] = baseline
            grouped[timestamp.date().isoformat()].append(parsed)
    days = []
    for date, rows in sorted(grouped.items()):
        if len(rows) != 24 or [r['time'][11:] for r in rows] != [f'{h:02}:00:00' for h in range(24)]:
            raise ValueError(f'Incomplete or duplicate day: {date}')
        start = rows[0]['tank'] - rows[0]['aktina'] + rows[0]['demand']
        inventory = start
        for row in rows:
            inventory += row['aktina'] - row['demand']
            if not math.isclose(inventory, row['tank'], abs_tol=1e-7):
                raise ValueError(f'Water balance mismatch: {row["time"]}')
        days.append({'date': date, 'period': forecasts[rows[0]['time']][0], 'start_tank': start, 'rows': rows})
    rows = [row for day in days for row in day['rows']]
    baseline_matches = sum(math.isclose(row['forecast'], row['baseline'], rel_tol=0, abs_tol=1e-9) for row in rows)
    model_matches = sum(math.isclose(row['forecast'], row['model_forecast'], rel_tol=0, abs_tol=1e-9) for row in rows)
    return {
        'source': {'repository': 'https://github.com/stefanosbordea/actina', 'commit': MODEL_COMMIT,
                   'csv_sha256': hashlib.sha256(schedule.read_bytes()).hexdigest(),
                   'schedule_forecast_matches_baseline': baseline_matches,
                   'schedule_forecast_matches_model': model_matches,
                   'schedule_forecast_status': 'matches_persistence' if baseline_matches == len(rows) else 'matches_model' if model_matches == len(rows) else 'mixed_or_unconfirmed',
                   'time_basis': 'Cyprus local wall-clock labels supplied by the scheduler; no UTC offsets provided.',
                   'forecast': 'LightGBM, trained on two years of Paphos weather from Open-Meteo',
                   'scheduler': 'Aktina scheduler'},
        'assumptions': {'capacity': 4000, 'reserve': 800, 'energy': 3.4, 'threshold': 600,
                        'normal_price': 183, 'surplus_price': 101},
        'days': days,
    }


def main():
    data = prepare()
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / 'data.js').write_text('window.AKTINA_DATA=' + json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + ';\n')
    raw = ROOT / 'eval/schedule_hourly.csv'
    (SITE / 'schedule_hourly.csv').write_bytes(raw.read_bytes())
    report = {'source': data['source'], 'days': len(data['days']), 'rows': sum(len(d['rows']) for d in data['days']),
              'first_day': data['days'][0]['date'], 'last_day': data['days'][-1]['date']}
    (ROOT / 'app/handoff/model-data-check.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
