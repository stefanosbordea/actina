"""Lock two fixed marginal analogue forecasts. No network or future reference."""
import argparse
import csv
import hashlib
import io
import json
import math
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CAPTURE = HERE.parent / 'capture-001'
PROTOCOL_SHA = 'b21cf821cfdffa00a913e372f445d9ec77dcfb14bb7eac9f58f4fb7ff2790fca'
IDENTITIES_SHA = '73be720d4f9341c8da5cf8bbb951677556c39a344523839c7c3d16b74851b098'
FIXED_ZONE = timezone(timedelta(hours=3))
METHODS = ['nwp_live', 'analogue_raw', 'analogue_solar']


def digest(raw): return hashlib.sha256(raw).hexdigest()


def save(path, value): path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def utc(text):
    stamp = datetime.fromisoformat(text)
    if stamp.utcoffset() != timedelta(0): raise ValueError('Expected explicit UTC')
    return stamp


def require_future(now, start):
    if now >= start: raise ValueError('Too late to lock before the first selected interval')


def nearest(train, query, k=64):
    # Same frozen 004 distance and earlier-origin tie rule; no estimator imports.
    distances = np.sum((train - query) ** 2, axis=1)
    origins = np.arange(len(train))
    boundary = np.partition(distances, k - 1)[k - 1]
    eligible = origins[distances <= boundary]
    chosen = eligible[np.lexsort((eligible, distances[eligible]))][:k]
    return chosen, distances[chosen]


def scenario_summary(values):
    low, high = np.quantile(values, [.05, .95], method='linear')
    probability = float(np.mean(values > 600))
    return {'status': 'known', 'point_w_m2': float(np.median(values)),
            'probability': probability, 'predicted_positive': int(probability > .5),
            'interval_low_w_m2': float(low), 'interval_high_w_m2': float(high)}


def verify_capture(blobs):
    prefix = 'app/experiments/prospective-001/capture-001/'
    selected = json.loads(blobs[prefix + 'selected-targets.json'])
    manifest = json.loads(blobs[prefix + 'capture/manifest.json'])
    verified = json.loads(blobs[prefix + 'byte-verification.json'])
    manifest_sha = digest(blobs[prefix + 'capture/manifest.json'])
    if selected['capture_manifest_sha256'] != manifest_sha or verified['manifest_sha256'] != manifest_sha:
        raise ValueError('Capture identity mismatch')
    if verified['status'] != 'VERIFIED_BYTES' or verified['roles'] != manifest['roles']:
        raise ValueError('Capture verification mismatch')
    if selected['capture_finished_at_utc'] != manifest['capture_finished_at_utc']:
        raise ValueError('Capture time mismatch')
    for role in manifest['roles'].values():
        raw = (CAPTURE / 'capture' / role['payload']).read_bytes()
        if digest(raw) != role['sha256'] or len(raw) != role['bytes'] or raw != (CAPTURE / role['basename']).read_bytes():
            raise ValueError('Capture payload mismatch')
    raw = json.loads(blobs[prefix + 'response.json'])
    if raw['utc_offset_seconds'] != 0 or raw['hourly_units'] != {'time':'unixtime','shortwave_radiation':'W/m²','cloud_cover':'%'}:
        raise ValueError('Invalid live units')
    for key, filename in [('raw_response', 'response.json'), ('predictions_full', 'predictions-full.csv')]:
        data = blobs[prefix + filename]
        if selected[key] != {'bytes': len(data), 'sha256': digest(data)}: raise ValueError('Selected source mismatch')
    hourly = raw['hourly']; times = hourly['time']
    if len(times) != 168 or any(type(t) is not int or t % 3600 for t in times) or any(b-a != 3600 for a,b in zip(times,times[1:])):
        raise ValueError('Invalid live timestamps')
    for field in ['shortwave_radiation', 'cloud_cover']:
        if len(hourly[field]) != len(times): raise ValueError('Array length mismatch')
        if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v < 0 or field == 'cloud_cover' and v > 100) for v in hourly[field]):
            raise ValueError('Invalid live value')
    full = list(csv.DictReader(io.StringIO(blobs[prefix + 'predictions-full.csv'].decode())))
    if len(full) != len(times): raise ValueError('CSV coverage mismatch')
    lookup = {}
    for index, row in enumerate(full):
        end = utc(row['valid_time_utc']); start = utc(row['interval_start_utc'])
        q, cloud = hourly['shortwave_radiation'][index], hourly['cloud_cover'][index]
        expected = [q, cloud, None if q is None else int(q > 600)]
        found = [None if row[k] == '' else float(row[k]) for k in ['shortwave_radiation_w_m2','cloud_cover_percent','event_gt_600']]
        if end.timestamp() != times[index] or end-start != timedelta(hours=1) or found != expected:
            raise ValueError('Raw/CSV disagreement')
        lookup[row['valid_time_utc']] = row
    finished = utc(selected['capture_finished_at_utc']); rows = []
    if set(selected['targets']) != {'primary','secondary'} or selected['threshold_w_m2'] != 600 or selected['event_operator'] != '>':
        raise ValueError('Unexpected target contract')
    for name, lead in [('primary',24),('secondary',48)]:
        group = selected['targets'][name]
        if len(group['intervals']) != 24 or group['minimum_interval_start_lead_hours'] != lead: raise ValueError('Selected coverage mismatch')
        earliest = finished + timedelta(hours=lead)
        first = earliest.replace(minute=0,second=0,microsecond=0)
        if first < earliest: first += timedelta(hours=1)
        for index, row in enumerate(group['intervals']):
            start, end = utc(row['interval_start_utc']), utc(row['valid_time_utc'])
            if start != first+timedelta(hours=index) or end-start != timedelta(hours=1): raise ValueError('Selected interval changed')
            source = lookup.get(row['valid_time_utc'])
            if source is None: raise ValueError('Missing raw interval')
            for key in ['shortwave_radiation_w_m2','cloud_cover_percent','event_gt_600']:
                if row[key] != (None if source[key] == '' else float(source[key])): raise ValueError('Selected value changed')
            if row['start_lead_seconds'] != (start-finished).total_seconds() or row['valid_time_lead_seconds'] != (end-finished).total_seconds():
                raise ValueError('Selected lead changed')
            rows.append({'target_set':name, **row})
    if len({r['valid_time_utc'] for r in rows}) != 48: raise ValueError('Repeated selected hour')
    return selected, rows


def run(out):
    out.mkdir(parents=True, exist_ok=False)
    started = datetime.now(timezone.utc)
    adapter_sha = digest(Path(__file__).read_bytes())
    protocol = (HERE/'PROTOCOL.md').read_bytes(); identities = (HERE/'input-identities.json').read_bytes()
    if digest(protocol) != PROTOCOL_SHA or digest(identities) != IDENTITIES_SHA: raise ValueError('Changed frozen protocol or inputs')
    pins = json.loads(identities); blobs = {name:(ROOT/name).read_bytes() for name in pins}
    if any(digest(blobs[name]) != expected for name,expected in pins.items()): raise ValueError('Changed source bytes')
    selected, rows = verify_capture(blobs)
    cutoff = utc(selected['capture_finished_at_utc']); first = utc(rows[0]['interval_start_utc'])
    require_future(started, first)
    geometry = {}; exec(compile(blobs['app/experiments/f1-004/geometry.py'], 'frozen-004-geometry.py', 'exec'), geometry)
    frame = pd.read_csv(io.BytesIO(blobs['data/features.csv']),index_col=0,parse_dates=True)
    weather = pd.read_csv(io.BytesIO(blobs['data/paphos_weather_data.csv']),index_col=0,parse_dates=True)
    for data in [frame,weather]:
        if data.index.tz is not None or not data.index.is_unique or not np.all(data.index[1:]-data.index[:-1] == pd.Timedelta(hours=1)):
            raise ValueError('Invalid historical hourly coverage')
        if not np.isfinite(data.to_numpy()).all(): raise ValueError('Nonfinite historical input')
    targets = frame.index + pd.Timedelta(hours=24)
    if not np.allclose(frame.target,weather.shortwave_radiation.reindex(targets),atol=1e-9,rtol=0): raise ValueError('Historical target mismatch')
    epochs = np.array([int(t.to_pydatetime().replace(tzinfo=FIXED_ZONE).timestamp()) for t in targets])
    eligible = epochs < cutoff.timestamp()
    frame = frame.loc[eligible]; targets = targets[eligible]; epochs = epochs[eligible]
    if len(frame) < 64: raise ValueError('Insufficient historical bank')
    archive = json.loads(blobs['app/experiments/nwp-archive-001/archive.json'])
    for key,unit in [('time','unixtime'),('shortwave_radiation_previous_day2','W/m²'),('cloud_cover_previous_day2','%')]:
        if archive['hourly_units'][key] != unit: raise ValueError('Historical units mismatch')
    hourly = archive['hourly']; times = hourly['time']
    if any(type(t) is not int or t % 3600 for t in times) or any(b-a != 3600 for a,b in zip(times,times[1:])): raise ValueError('Historical timestamp mismatch')
    lookup = {stamp:i for i,stamp in enumerate(times)}
    positions = [lookup[int(t)] for t in epochs]
    q = np.asarray(hourly['shortwave_radiation_previous_day2'],dtype=float)[positions]
    cloud = np.asarray(hourly['cloud_cover_previous_day2'],dtype=float)[positions]
    if not np.isfinite(q).all() or np.any(q < 0) or np.isinf(cloud).any() or np.any((cloud < 0)|(cloud > 100)): raise ValueError('Invalid historical forecast')
    values = np.array([geometry['solar_features'](t.to_pydatetime()) for t in targets]); scale,coszen,sine,cosine = values.T
    median = float(np.nanmedian(cloud))
    if not math.isfinite(median): raise ValueError('No finite training cloud')
    inputs = np.column_stack([q/scale,np.where(np.isnan(cloud),median,cloud),np.isnan(cloud).astype(float),coszen,sine,cosine])
    mean, std = inputs.mean(axis=0), inputs.std(axis=0); std[std == 0] = 1
    train = (inputs-mean)/std; residual = frame.target.to_numpy()-q
    if not np.isfinite(train).all(): raise ValueError('Invalid training transform')
    pd.DataFrame({'feature_time':frame.index,'target_time_fixed_plus03':targets,'target_epoch_utc':epochs,
        'reference_w_m2':frame.target.to_numpy(),'nwp_day2_w_m2':q,'cloud_percent':cloud,'cloud_missing':np.isnan(cloud).astype(int),
        'solar_scale':scale,'mean_coszen':coszen,'solar_hour_sin':sine,'solar_hour_cos':cosine,'residual_w_m2':residual}).to_csv(out/'training-bank.csv',index=False)
    save(out/'parameters.json',{'cloud_median':median,'feature_mean':mean.tolist(),'feature_std':std.tolist(),
        'feature_order':['nwp_over_solar_scale','cloud_imputed','cloud_missing','mean_coszen','solar_hour_sin','solar_hour_cos'],
        'K':64,'probability_cutoff':.5,'event_threshold_w_m2':600,'event_operator':'>','decision_operator':'>'})
    predictions = []; neighbors = []; scenarios = []; query_rows = []
    unknown = dict(status='unknown_missing_radiation',point_w_m2=None,probability=None,predicted_positive=None,interval_low_w_m2=None,interval_high_w_m2=None)
    for row in rows:
        radiation, cover = row['shortwave_radiation_w_m2'], row['cloud_cover_percent']
        solar = geometry['solar_features'](utc(row['valid_time_utc']).astimezone(FIXED_ZONE).replace(tzinfo=None))
        common = {k:row[k] for k in ['target_set','interval_start_utc','valid_time_utc','start_lead_seconds','valid_time_lead_seconds']}
        query_rows.append({**row,'solar_scale':solar[0],'mean_coszen':solar[1],'solar_hour_sin':solar[2],'solar_hour_cos':solar[3],'cloud_missing':int(cover is None)})
        if radiation is None:
            for name in METHODS: predictions.append({**common,'method':name,**unknown})
            continue
        predictions.append({**common,'method':'nwp_live','status':'known','point_w_m2':radiation,'probability':float(radiation > 600),
            'predicted_positive':int(radiation > 600),'interval_low_w_m2':None,'interval_high_w_m2':None})
        query = np.array([radiation/solar[0],median if cover is None else cover,float(cover is None),*solar[1:]])
        chosen, distances = nearest(train,(query-mean)/std)
        for rank,(index,distance) in enumerate(zip(chosen,distances)):
            neighbors.append({**common,'rank':rank,'source_feature_time':str(frame.index[index]),'source_target_epoch_utc':int(epochs[index]),'distance_squared':float(distance)})
        for name, values in [('analogue_raw',np.maximum(0,radiation+residual[chosen])),
                             ('analogue_solar',np.maximum(0,radiation+solar[0]*residual[chosen]/scale[chosen]))]:
            scenarios.append({**common,'method':name,**{f'scenario_{i}':float(v) for i,v in enumerate(values)}})
            predictions.append({**common,'method':name,**scenario_summary(values)})
    for name, values in [('queries',query_rows),('predictions',predictions),('neighbors',neighbors),('scenarios',scenarios)]:
        save(out/(name+'.json'),values)
    pd.DataFrame(predictions).to_csv(out/'predictions.csv',index=False)
    if any(digest((ROOT/name).read_bytes()) != expected for name,expected in pins.items()): raise ValueError('Inputs mutated during inference')
    ended = datetime.now(timezone.utc); require_future(ended,first)
    if digest(Path(__file__).read_bytes()) != adapter_sha: raise ValueError('Adapter mutated during inference')
    manifest = {'schema':1,'status':'LOCKED_RESEARCH_ONLY','methods':METHODS,'protocol_sha256':PROTOCOL_SHA,'input_identities_sha256':IDENTITIES_SHA,
        'adapter_sha256':adapter_sha,'geometry_sha256':pins['app/experiments/f1-004/geometry.py'],
        'input_sha256':pins,'capture_manifest_sha256':selected['capture_manifest_sha256'],
        'lock_started_at_utc':started.isoformat(),'lock_finished_at_utc':ended.isoformat(),'capture_finished_at_utc':cutoff.isoformat(),
        'earliest_target_interval_start_utc':first.isoformat(),'target_sets':{'primary':24,'secondary':24},
        'training':{'hours':len(frame),'excluded_at_or_after_capture':int((~eligible).sum()),'latest_target_utc':datetime.fromtimestamp(int(epochs[-1]),timezone.utc).isoformat(),
                    'cloud_missing':int(np.isnan(cloud).sum()),'provider_availability':'unverified; only target-time-before-capture checked'},
        'missing_radiation_hours':sum(r['shortwave_radiation_w_m2'] is None for r in rows),
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__},
        'scope':'Fixed research transfer, not a promoted method. Live observed capture leads differ from archived day2; actual NWP issuance/publication unknown. No future truth or scoring. Marginal scenarios are not independent or daily trajectories. Local clock is not trusted attestation.',
        'output_sha256':{p.name:digest(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file()}}
    save(out/'manifest.json',manifest)
    print(json.dumps({k:manifest[k] for k in ['status','lock_started_at_utc','lock_finished_at_utc','training','target_sets']}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    output=parser.parse_args().output.resolve()
    if output.exists(): raise FileExistsError('Refusing existing output directory: '+str(output))
    try: run(output)
    except Exception as error:
        if output.exists() and not (output/'manifest.json').exists() and not (output/'failure.json').exists():
            save(output/'failure.json',{'status':'FAILED_NOT_LOCKED','error':str(error),'at_utc':datetime.now(timezone.utc).isoformat()})
        raise
