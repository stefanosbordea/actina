"""Offline independent reconstruction of retained GFS and SARAH joins; no fit or request."""
import csv
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import math
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
ROOT = EXP.parents[2]
SARAH = EXP.parent/'satellite-reference-001'
JOIN = EXP.parent/'reference-training-001'
SIX = EXP.parent/'f1-006/result'
checks = 0


def require(ok, label):
    global checks
    checks += 1
    if not ok: raise AssertionError(label)


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def js(p): return json.loads(p.read_text())
def rows(p): return list(csv.DictReader(p.open()))
def dt(s): return datetime.fromisoformat(s.replace('Z', '+00:00'))
def number(s): return None if s == '' else float(s)


def source(folder, host, model, radiation, first, last):
    request, receipt, raw = [js(folder/'result'/name) for name in ('request.json','response-metadata.json','response.json')]
    parsed = urlparse(request['url']); query = {k:v[0] for k,v in parse_qs(parsed.query).items()}
    require(parsed.scheme == 'https' and parsed.hostname == host, 'source host')
    require(receipt['status'] == 200 and receipt['url'] == request['url'], 'HTTP identity')
    require(query['models'] == model and query['timezone'] == 'GMT' and query['timeformat'] == 'unixtime', 'fixed source selection')
    require(query['latitude'] == '34.7744' and query['longitude'] == '32.4229', 'requested location')
    require(query['start_date'] == first and query['end_date'] == last, 'complete date request')
    require(raw['utc_offset_seconds'] == 0 and raw['timezone'] == 'GMT', 'UTC response')
    require(raw['hourly_units']['time'] == 'unixtime' and raw['hourly_units'][radiation] == 'W/m²', 'units')
    begin, finish = dt(request['started_at_utc']), dt(receipt['finished_at_utc'])
    require(begin <= finish and begin-timedelta(seconds=2) <= parsedate_to_datetime(receipt['http_date']) <= finish+timedelta(seconds=2), 'acquisition clocks')
    h = raw['hourly']; times = h['time']
    start = int(datetime.fromisoformat(first).replace(tzinfo=timezone.utc).timestamp())
    end = int((datetime.fromisoformat(last)+timedelta(days=1)).replace(tzinfo=timezone.utc).timestamp())
    require(times == list(range(start,end,3600)), 'complete unique ordered hours')
    require(all(type(t) is int for t in times) and all(len(v) == len(times) for v in h.values()), 'array membership')
    require(all(v is None or type(v) in (int,float) and math.isfinite(v) and v >= 0 for v in h[radiation]), 'radiation domain')
    require(datetime.fromtimestamp(times[-1],timezone.utc) < finish, 'historical targets')
    return dict(zip(times,h[radiation])), raw, finish


def main():
    pins = {}
    for folder in (EXP, JOIN):
        for name, identity in js(folder/'inputs.json').items():
            require(name not in pins or pins[name] == identity, 'consistent overlapping pin')
            pins[name] = identity
    for name, identity in pins.items(): require(sha(ROOT/name) == identity, 'pinned '+name)
    tracked = set(ROOT/name for name in pins)
    for folder in (EXP, JOIN, SARAH):
        tracked.update(p for p in folder.glob('*.py'))
        tracked.update(p for p in folder.glob('*.md'))
        tracked.update(p for p in folder.glob('*.json'))
        tracked.update(p for p in folder.glob('*.log'))
        tracked.update(p for p in (folder/'result').iterdir() if p.is_file())
    before = {str(p.relative_to(ROOT)):sha(p) for p in tracked}
    gfs, raw_gfs, gfs_finished = source(EXP, 'previous-runs-api.open-meteo.com', 'gfs_global', 'shortwave_radiation_previous_day2','2024-09-15','2026-09-28')
    sat, raw_sat, sat_finished = source(SARAH, 'satellite-api.open-meteo.com', 'eumetsat_sarah3', 'shortwave_radiation','2024-09-13','2026-10-01')
    request = js(EXP/'result/request.json')
    for field, file in [('protocol_sha256','PROTOCOL.md'),('fetch_sha256','fetch.py'),('input_manifest_sha256','inputs.json')]:
        require(request[field] == sha(EXP/file), field)
    radiation_receipt = js(EXP/'result/radiation-only-receipt.json')
    for field, file in [('source_raw_sha256','result/response.json'),('source_diagnostic_join_sha256','result/diagnostic-join.csv'),('radiation_only_protocol_sha256','RADIATION-ONLY.md'),('script_sha256','radiation_only.py'),('radiation_only_csv_sha256','result/radiation-only.csv')]:
        require(radiation_receipt[field] == sha(EXP/file), field)
    require(js(EXP/'result/failure.json')['status'] == 'FAILED' and js(EXP/'result/integrity.json')['intake_success'] is False, 'preserved failed cloud intake')
    require(radiation_receipt['status'] == 'RADIATION_ONLY_READY' and radiation_receipt['original_two_variable_intake_status'] == 'FAILED', 'distinct statuses')
    require(raw_gfs['hourly_units']['cloud_cover_previous_day2'] == '%', 'cloud units')
    cloud = dict(zip(raw_gfs['hourly']['time'],raw_gfs['hourly']['cloud_cover_previous_day2']))
    require(all(v is not None and math.isfinite(v) for v in cloud.values()), 'cloud numeric domain')
    invalid = {t:v for t,v in cloud.items() if not 0 <= v <= 100}
    require(len(invalid) == 8 and list(invalid.values()).count(101) == 5 and list(invalid.values()).count(-1) == 3, 'exact retained cloud failures')
    flags = rows(EXP/'result/quality-flags.csv')
    require({int(r['target_epoch_utc']):float(r['gfs_day2_cloud_percent_raw']) for r in flags} == invalid, 'complete cloud flags')
    full_reference = rows(SARAH/'result/reference-full.csv')
    require(len(full_reference) == len(sat), 'full raw satellite membership')
    for r,(epoch,value) in zip(full_reference,sat.items()):
        valid = datetime.fromtimestamp(epoch,timezone.utc)
        require(dt(r['valid_time_utc']) == valid and dt(r['interval_start_utc']) == valid-timedelta(hours=1), 'satellite valid interval')
        require(number(r['shortwave_radiation_w_m2']) == value and int(r['is_missing']) == (value is None), 'raw satellite value preservation')
    radiation = rows(EXP/'result/radiation-only.csv')
    require(set(radiation[0]) == {'feature_time','target_time','target_epoch_utc','valid_time_utc','radiation_interval_start_utc','gfs_day2_radiation_w_m2'}, 'cloud fully excluded')
    diagnostic, joined, targets = rows(EXP/'result/diagnostic-join.csv'), rows(JOIN/'result/joined-reference.csv'), rows(SIX/'feature-targets.csv')
    original = rows(ROOT/'data/features.csv'); origin_key = next(iter(original[0]))
    require(len(radiation) == len(diagnostic) == len(joined) == len(targets) == len(original) == 17832, 'every original hour retained')
    six_report = js(SIX/'report.json')
    cutoffs = {stage:dt(six_report['splits'][stage]['first_evaluation_origin']) for stage in ('validation','test')}
    selected = {stage:[] for stage in cutoffs}
    missing, used_gfs = [], set()
    for rr,dd,jj,tt,oo in zip(radiation,diagnostic,joined,targets,original):
        origin = dt(oo[origin_key]); target = origin+timedelta(hours=24)
        valid = (target-timedelta(hours=3)).replace(tzinfo=timezone.utc)
        epoch = int(valid.timestamp()); interval = valid-timedelta(hours=1)
        require(all(r['feature_time'] == oo[origin_key] and dt(r['target_time']) == target for r in (rr,dd,jj,tt)), 'fixed origin/target mapping')
        require(int(rr['target_epoch_utc']) == int(dd['target_epoch_utc']) == int(tt['target_epoch_utc']) == epoch, 'fixed +03 epoch')
        require(dt(rr['valid_time_utc']) == dt(dd['valid_time_utc']) == dt(jj['valid_time_utc']) == valid, 'UTC join')
        require(dt(rr['radiation_interval_start_utc']) == dt(dd['radiation_interval_start_utc']) == dt(jj['interval_start_utc']) == interval, 'preceding-hour means')
        require(valid < gfs_finished and valid < sat_finished, 'historical join')
        require(float(rr['gfs_day2_radiation_w_m2']) == float(dd['gfs_day2_radiation_w_m2']) == gfs[epoch] and gfs[epoch] is not None, 'GFS radiation unchanged')
        require(float(dd['gfs_day2_cloud_percent_raw']) == cloud[epoch] and int(dd['cloud_out_of_range']) == (epoch in invalid), 'raw cloud unchanged')
        require(int(dd['radiation_missing']) == 0 and int(dd['cloud_missing']) == 0, 'raw missing indicators')
        require(float(jj['weather_actual_w_m2']) == float(tt['actual']) == float(oo['target']), 'original target unchanged')
        require(number(jj['satellite_w_m2']) == sat[epoch] and int(jj['is_missing']) == (sat[epoch] is None), 'satellite join unchanged')
        if sat[epoch] is None: missing.append(jj)
        for stage,cut in cutoffs.items():
            expected = target < cut
            require(int(jj[stage+'_training']) == expected, 'strict target-before-origin purge')
            if expected: selected[stage].append(jj)
        used_gfs.add(epoch)
    require(len(used_gfs) == 17832 and len(gfs)-len(used_gfs) == 24, 'no GFS dropped target / exact padding')
    require(rows(JOIN/'result/missing-reference.csv') == missing and len(missing) == 197, 'complete missing satellite ledger')
    report = js(JOIN/'result/report.json')
    coverage = {}
    for group, subset in [('all_feature_targets',joined),*[(stage+'_training',v) for stage,v in selected.items()]]:
        absent = sum(int(r['is_missing']) for r in subset)
        coverage[group] = {'hours':len(subset),'missing':absent}
        require(report['coverage'][group]['hours'] == len(subset) and report['coverage'][group]['missing_hours'] == absent, 'coverage summary')
        if group.endswith('_training'):
            stage=group.removesuffix('_training')
            require([r['feature_time'] for r in subset] == [r['feature_time'] for r in rows(SIX/f'{stage}-training-origins.csv')], 'retained training membership')
    for name,identity in report['output_sha256'].items(): require(sha(JOIN/'result'/name) == identity, 'join output identity')
    for name,identity in before.items(): require(sha(ROOT/name) == identity, 'unchanged '+name)
    result = {'status':'PASS','checks':checks,'original_files_and_sources_unchanged':True,'tracked_sha256':before,
              'raw_gfs_hours':len(gfs),'raw_satellite_hours':len(sat),'joined_hours':len(joined),'gfs_padding_hours':24,
              'gfs_radiation_missing':sum(v is None for v in gfs.values()),'gfs_cloud_invalid_hours':len(invalid),
              'original_cloud_intake_status':'FAILED','radiation_only_schema_status':'PASS','satellite_coverage':coverage,
              'returned_grid':{name:{k:raw[k] for k in ('latitude','longitude','elevation')} for name,raw in [('GFS',raw_gfs),('SARAH3',raw_sat)]},
              'check_sha256':sha(Path(__file__)), 'network_requests':0,'fits':0,'forecast_scores':0,
              'limits':['Retained bytes and local request receipts establish reconstruction, not independent authentication of provider history.',
                        'Nominal previous_day2 does not verify historical publication/initialization vintage or real-time availability.',
                        'Different model families and satellite-derived products are not proven statistically independent truth.',
                        'Source-label UTC+03 is fixed; returned grids differ from requested coordinates; radiation is a preceding-hour mean.']}
    (HERE/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='tracked_sha256'},indent=2))


if __name__ == '__main__': main()
