"""Retain archived forecast inputs and timestamp checks; never fit or modify a model."""
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIELDS = [f'{name}_previous_day{lead}' for lead in (1, 2) for name in ('shortwave_radiation', 'cloud_cover')]
LOCATION = {'latitude': 34.7744, 'longitude': 32.4229}
START = datetime(2024, 9, 14, tzinfo=timezone(timedelta(hours=3)))
END = datetime(2026, 9, 29, tzinfo=timezone(timedelta(hours=3)))
SOURCES = ['data/paphos_weather_data.csv', 'data/download_weather_data.py', 'data/features.py']
LIMITS = [
    'Previous-day offsets are provider-declared lead times, not verified historical API publication times.',
    'At target=origin+24h, day2 provides a nominal 24h margin before origin; this is not proof of live availability.',
    'Original CSV labels have no retained UTC metadata. Fixed +03:00 is recovered from sample equality, not inferred with DST rules.',
    'Radiation is a preceding-hour mean; cloud is instantaneous. Do not shift radiation to interval starts.',
    'Pinned IFS 0.25 degree forecast and unpinned historical reconstruction use different grid cells and potentially related models; truth is not independent station measurement.',
    'Archive availability does not authenticate original operational issue vintages or exclude reconstructed hindcasts.',
    'The test period was previously inspected. This archive is exploratory model support, not a fresh holdout or claimed improvement.',
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def request(label, host, params):
    url = f'https://{host}.open-meteo.com/v1/' + ('archive' if host == 'archive-api' else 'forecast') + '?' + urlencode(LOCATION | params, safe=',')
    body, headers = HERE / f'{label}.json', HERE / f'{label}.headers.txt'
    if body.exists() or headers.exists():
        raise FileExistsError(f'Refusing to overwrite {label}')
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(['curl', '--silent', '--show-error', '--max-time', '90', '--user-agent', 'Aktina-research/1.0', '--dump-header', str(headers), '--output', str(body), '--write-out', '%{http_code}', url], capture_output=True, text=True)
    entry = {'label': label, 'url': url, 'started_at_utc': started, 'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'curl_exit': result.returncode, 'http_status': result.stdout, 'stderr': result.stderr, 'body': body.name, 'sha256': sha(body) if body.exists() else None, 'headers': headers.name, 'headers_sha256': sha(headers) if headers.exists() else None}
    requests.append(entry)
    save('requests.json', requests)
    if result.returncode or result.stdout != '200':
        raise RuntimeError(f'{label} failed; response and request retained: {entry}')
    data = json.loads(body.read_text())
    if data.get('error'):
        raise RuntimeError(f'{label}: {data}')
    time.sleep(1)
    return data

if __name__ == '__main__':
    if (HERE / 'protocol.json').exists():
        raise FileExistsError('This retained run is immutable; use a new experiment directory for a rerun.')
    original = {name: sha(ROOT / name) for name in SOURCES}
    requests = []
    save('protocol.json', {'schema': 1, 'kind': 'archived_weather_feature_intake', 'created_at_utc': datetime.now(timezone.utc).isoformat(), 'location': LOCATION, 'forecast_model': 'ecmwf_ifs025', 'fields': FIELDS, 'supplied_label_start': '2024-09-14 00:00:00', 'supplied_label_end': '2026-09-28 23:00:00', 'recovered_fixed_offset_seconds': 10800, 'target_utc_start': START.astimezone(timezone.utc).isoformat(), 'target_utc_end_exclusive': END.astimezone(timezone.utc).isoformat(), 'request_utc_dates': ['2024-09-13', '2026-09-28'], 'padding': 'All 24 UTC padding hours remain in the raw response; no target hour is filtered.', 'input_sha256': original, 'fetch_source_sha256': sha(Path(__file__)), 'selection': 'Pinned model and all four variables fixed before any full-period scoring. No model comparison or training here.', 'prior_research': 'Tiny day1/day2 samples and three historical timestamp comparisons were inspected before this full intake; no metric gain was measured.', 'limits': LIMITS, 'sources': ['https://open-meteo.com/en/docs/previous-runs-api', 'https://open-meteo.com/en/docs', 'https://open-meteo.com/en/docs/single-runs-api', 'https://open-meteo.com/en/docs/model-updates']})
    with (ROOT / SOURCES[0]).open() as handle:
        supplied = {row['time']: row for row in csv.DictReader(handle)}
    checks = []
    for day in ('2025-12-10', '2026-07-03', '2025-03-30'):
        data = request('time-check-' + day, 'archive-api', {'start_date': day, 'end_date': day, 'hourly': 'shortwave_radiation,cloud_cover', 'timezone': 'auto'})
        hourly = data['hourly']
        errors = {key: [abs(float(supplied[t.replace('T', ' ') + ':00'][key]) - value) for t, value in zip(hourly['time'], hourly[key])] for key in ('shortwave_radiation', 'cloud_cover')}
        checks.append({'date': day, 'utc_offset_seconds': data['utc_offset_seconds'], 'timezone': data['timezone'], 'hours': len(hourly['time']), 'max_absolute_differences': {key: max(values) for key, values in errors.items()}})
    data = request('time-check-winter-utc', 'archive-api', {'start_date': '2025-12-09', 'end_date': '2025-12-10', 'hourly': 'shortwave_radiation,cloud_cover', 'timezone': 'GMT', 'timeformat': 'unixtime'})
    hourly = data['hourly']; index = {stamp: i for i, stamp in enumerate(hourly['time'])}
    winter = [(stamp, values) for stamp, values in supplied.items() if stamp.startswith('2025-12-10')]
    for offset in (2, 3):
        errors = {key: [] for key in ('shortwave_radiation', 'cloud_cover')}
        for stamp, values in winter:
            utc = int(datetime.fromisoformat(stamp).replace(tzinfo=timezone(timedelta(hours=offset))).timestamp())
            for key in errors:
                errors[key].append(abs(float(values[key]) - hourly[key][index[utc]]))
        checks.append({'winter_assumed_offset_hours': offset, 'hours': len(winter), 'max_absolute_differences': {key: max(values) for key, values in errors.items()}, 'mean_absolute_differences': {key: sum(values)/len(values) for key, values in errors.items()}})
    save('time-checks.json', checks)
    if any(check['utc_offset_seconds'] != 10800 or check['hours'] != 24 or any(check['max_absolute_differences'].values()) for check in checks[:3]) or any(checks[-1]['max_absolute_differences'].values()):
        raise RuntimeError('Fixed-offset validation failed; retained checks require review before joining.')
    for day in ('2024-09-14', '2026-09-28'):
        request('forecast-sample-' + day, 'previous-runs-api', {'start_date': day, 'end_date': day, 'hourly': ','.join(FIELDS), 'models': 'ecmwf_ifs025', 'timezone': 'GMT', 'timeformat': 'unixtime'})
    data = request('archive', 'previous-runs-api', {'start_date': '2024-09-13', 'end_date': '2026-09-28', 'hourly': ','.join(FIELDS), 'models': 'ecmwf_ifs025', 'timezone': 'GMT', 'timeformat': 'unixtime'})
    hourly = data['hourly']; stamps = hourly['time']
    selected = [i for i, stamp in enumerate(stamps) if START.timestamp() <= stamp < END.timestamp()]
    result = {'schema': 1, 'model': 'ecmwf_ifs025', 'raw_metadata': {key: value for key, value in data.items() if key not in ('hourly', 'generationtime_ms')}, 'raw_hours': len(stamps), 'target_hours': len(selected), 'expected_target_hours': int((END-START).total_seconds()/3600), 'padding_hours': len(stamps)-len(selected), 'first_target_utc': datetime.fromtimestamp(stamps[selected[0]], timezone.utc).isoformat(), 'last_target_utc': datetime.fromtimestamp(stamps[selected[-1]], timezone.utc).isoformat(), 'duplicate_timestamps': len(stamps)-len(set(stamps)), 'non_hourly_steps': sum(b-a != 3600 for a,b in zip(stamps, stamps[1:])), 'field_lengths': {key: len(hourly[key]) for key in FIELDS}, 'nulls_all_hours': {key: sum(value is None for value in hourly[key]) for key in FIELDS}, 'nulls_target_hours': {key: sum(hourly[key][i] is None for i in selected) for key in FIELDS}, 'source_files_unchanged': all(sha(ROOT/name) == digest for name,digest in original.items()), 'limits': LIMITS}
    save('intake-summary.json', result)
    assert result['target_hours'] == result['expected_target_hours'] and not result['duplicate_timestamps'] and not result['non_hourly_steps']
    assert all(length == len(stamps) for length in result['field_lengths'].values()) and result['source_files_unchanged']
    print(json.dumps({key: result[key] for key in ('raw_hours', 'target_hours', 'padding_hours', 'nulls_target_hours', 'source_files_unchanged')}, indent=2))
