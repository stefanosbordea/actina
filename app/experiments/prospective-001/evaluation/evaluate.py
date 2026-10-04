#!/usr/bin/env python3
"""Evaluate frozen forecasts against the declared satellite reference, after eligibility."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import sys
import time
import types
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
UTC = timezone.utc
CANDIDATES = ('captured_raw', 'analogue_raw', 'analogue_solar')
GATES = {'primary': datetime(2026, 10, 8, 9, tzinfo=UTC),
         'secondary': datetime(2026, 10, 9, 9, tzinfo=UTC)}
PROTOCOL_SHA = '46f60449efec769e87005568cbea45a8c10b7b1b802be58281b0dc6841a38888'
SELECTION_SHA = '7df57cce3cb4ab37b5700906aa507f1216aa186dfa7c1160ffb82f94f5843815'
LOCK_SHA = '0b223e0d99316c63db6e1f5b08e989249802f20d2d3a5af951c0236c14fa8bc3'
ARCHIVE_SHA = '294ecf9541ba5ca3520528e593d871cc63b598e5c6c61fe415f7260d3c570c83'
AMENDMENT_SHA = '585a25603efcca4b3b883c69f2c80d94652bef675e9201074611b97476c00183'
MAX_RESPONSE = 2 * 1024 * 1024


def now():
    return datetime.now(UTC)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(raw)
    return {'bytes': len(raw), 'sha256': sha(raw)}


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'Duplicate JSON key: {key}')
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError(f'Invalid JSON number: {value}')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def utc(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError('Expected explicit UTC timestamp')
    return result


def gate(name, at):
    if name not in GATES:
        raise ValueError('Expected primary or secondary target set')
    if at.tzinfo is None or at.utcoffset() != timedelta(0):
        raise ValueError('Clock must be explicit UTC')
    if at < GATES[name]:
        raise ValueError(f'Not eligible before {GATES[name].isoformat()}')


def number(value, maximum=None):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Expected a finite nonnegative number, excluding booleans')
    if maximum is not None and value > maximum:
        raise ValueError('Number exceeds allowed maximum')
    return value


def parse_reference(raw):
    data = decode(raw)
    if type(data.get('utc_offset_seconds')) is not int or data['utc_offset_seconds'] != 0:
        raise ValueError('Reference must declare UTC offset zero')
    if data.get('hourly_units', {}).get('time') != 'unixtime' or data['hourly_units'].get('shortwave_radiation') != 'W/m²':
        raise ValueError('Unexpected reference units')
    hourly = data.get('hourly', {})
    times, values = hourly.get('time'), hourly.get('shortwave_radiation')
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        raise ValueError('Invalid reference arrays')
    result = {}
    for stamp, value in zip(times, values):
        if type(stamp) is not int or stamp % 3600 or stamp in result:
            raise ValueError('Invalid or duplicate reference timestamp')
        if value is not None:
            number(value)
        result[stamp] = value
    return result


def validate_candidate(candidate, raw_radiation, name):
    fields = ('point_w_m2', 'probability') + (() if name == 'captured_raw' else ('interval_low_w_m2', 'interval_high_w_m2'))
    if any(field not in candidate for field in fields):
        raise ValueError('Missing candidate fields')
    values = [candidate.get(field) for field in fields]
    if raw_radiation is None:
        if any(value is not None for value in values):
            raise ValueError('Unknown source radiation requires unknown predictions')
        return
    if any(value is None for value in values):
        raise ValueError('Partial or inconsistent candidate nulls')
    for field, value in zip(fields, values):
        number(value, 1 if field == 'probability' else None)
    if name == 'captured_raw':
        if candidate['point_w_m2'] != raw_radiation or candidate['probability'] != int(raw_radiation > 600):
            raise ValueError('Raw control differs from captured forecast')
    elif candidate['interval_low_w_m2'] > candidate['interval_high_w_m2']:
        raise ValueError('Reversed candidate interval')


def metrics(rows, name):
    if not rows:
        return {'n': 0, 'metrics': None, 'reason': 'No common valid hours'}
    predicted = [row['candidates'][name] for row in rows]
    truth = [row['reference_w_m2'] for row in rows]
    positive = [value > 600 for value in truth]
    decisions = [p['probability'] > .5 for p in predicted]
    tp = sum(a and b for a, b in zip(positive, decisions))
    tn = sum(not a and not b for a, b in zip(positive, decisions))
    fp = sum(not a and b for a, b in zip(positive, decisions))
    fn = sum(a and not b for a, b in zip(positive, decisions))
    error = [p['point_w_m2'] - y for p, y in zip(predicted, truth)]
    denominators = {'precision': tp + fp, 'recall': tp + fn, 'f1': 2 * tp + fp + fn}
    values = {'mae_w_m2': math.fsum(abs(e) for e in error) / len(rows),
              'rmse_w_m2': math.sqrt(math.fsum(e * e for e in error) / len(rows)),
              'mean_error_w_m2': math.fsum(error) / len(rows),
              'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
              'precision': tp / (tp + fp) if tp + fp else None,
              'recall': tp / (tp + fn) if tp + fn else None,
              'f1': 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
              'brier': math.fsum((p['probability'] - y) ** 2 for p, y in zip(predicted, positive)) / len(rows)}
    intervals = None if name == 'captured_raw' else {
        'coverage_90': sum(p['interval_low_w_m2'] <= y <= p['interval_high_w_m2'] for p, y in zip(predicted, truth)) / len(rows),
        'mean_width_w_m2': math.fsum(p['interval_high_w_m2'] - p['interval_low_w_m2'] for p in predicted) / len(rows)}
    return {'n': len(rows), 'metrics': values, 'classification_denominators': denominators,
            'undefined_ratios': {key: 'Zero denominator' for key, value in denominators.items() if not value},
            'brier_probability_kind': 'hard 0/1 decision' if name == 'captured_raw' else 'fixed scenario fraction',
            'intervals': intervals, 'interval_status': 'not_applicable' if intervals is None else 'empirical_marginal'}


def assess(targets, candidates, reference):
    keys = [int(utc(row['valid_time_utc']).timestamp()) for row in targets]
    if len(keys) != 24 or any(b - a != 3600 for a, b in zip(keys, keys[1:])):
        raise ValueError('Expected the original 24 consecutive target hours')
    if set(candidates) != set(CANDIDATES) or any(set(candidates[name]) != set(keys) for name in CANDIDATES):
        raise ValueError('Candidate keys must equal all original target keys')
    rows = []
    for target, stamp in zip(targets, keys):
        prediction = {name: candidates[name][stamp] for name in CANDIDATES}
        for name, value in prediction.items():
            validate_candidate(value, target['shortwave_radiation_w_m2'], name)
        reasons = []
        if stamp not in reference:
            reasons.append('reference_absent')
        elif reference[stamp] is None:
            reasons.append('reference_null')
        if target['shortwave_radiation_w_m2'] is None:
            reasons.append('forecast_null')
        rows.append({**target, 'reference_w_m2': reference.get(stamp),
                     'reference_status': 'absent' if stamp not in reference else 'null' if reference[stamp] is None else 'valid',
                     'candidates': prediction, 'common_hour': not reasons, 'exclusion_reasons': reasons})
    common = [row for row in rows if row['common_hour']]
    scores = {name: metrics(common, name) for name in CANDIDATES}
    return {'status': 'COMPLETE' if len(common) == 24 else 'INCOMPLETE', 'expected_hours': 24,
            'reference_valid_hours': sum(row['reference_status'] == 'valid' for row in rows),
            'complete_set_metrics': scores if len(common) == 24 else None,
            'common_hour_diagnostic': {'n': len(common), 'fraction_of_expected': len(common) / 24,
                                      'valid_time_utc': [row['valid_time_utc'] for row in common],
                                      'excluded': [{'valid_time_utc': row['valid_time_utc'], 'reasons': row['exclusion_reasons']} for row in rows if not row['common_hour']],
                                      'candidates': scores}, 'rows': rows,
            'scope': 'Two fixed 24-hour sets cannot establish general superiority; no selection or promotion.'}


def load_frozen(root=HERE.parents[3]):
    prefix = 'app/experiments/prospective-001/'
    capture, analogue = prefix + 'capture-001/', prefix + 'analogue-001/'
    lock_raw = (root / (prefix + 'evaluation/input-lock.json')).read_bytes()
    if sha(lock_raw) != LOCK_SHA:
        raise ValueError('Frozen input lock changed')
    if sha((root / (prefix + 'evaluation/PROTOCOL.md')).read_bytes()) != PROTOCOL_SHA:
        raise ValueError('Evaluation protocol changed')
    if sha((root / (prefix + 'evaluation/AMENDMENT-001.md')).read_bytes()) != AMENDMENT_SHA:
        raise ValueError('Durability amendment changed')
    lock = decode(lock_raw)
    if utc(lock['locked_at_utc']) >= utc(lock['earliest_target_interval_start_utc']):
        raise ValueError('Input lock was not prospective')
    archive_raw = (root / (prefix + 'evaluation/frozen-inputs.zip')).read_bytes()
    if sha(archive_raw) != ARCHIVE_SHA:
        raise ValueError('Frozen input archive changed')
    blobs = {}
    with zipfile.ZipFile(io.BytesIO(archive_raw)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(lock['files_sha256']):
            raise ValueError('Archive must contain the exact locked member set, without duplicates')
        for name, expected in lock['files_sha256'].items():
            if PurePosixPath(name).is_absolute() or '..' in PurePosixPath(name).parts:
                raise ValueError('Invalid locked path')
            raw = archive.read(name)  # No extraction or working-tree input reads.
            if sha(raw) != expected:
                raise ValueError(f'Frozen member bytes changed: {name}')
            blobs[name] = raw
    def document(name):
        return decode(blobs[name])
    selection = document(capture + 'selected-targets.json')
    if sha(blobs[capture + 'selected-targets.json']) != SELECTION_SHA:
        raise ValueError('Selected target identity changed')
    receipt = document(capture + 'receipt.json')
    manifest = document(capture + 'capture/manifest.json')
    verified = document(capture + 'byte-verification.json')
    if receipt['status'] != 'CAPTURED_BYTES_VERIFIED_NO_ACCURACY' or verified['status'] != 'VERIFIED_BYTES':
        raise ValueError('Capture was not successful')
    if verified['roles'] != manifest['roles'] or verified['manifest_sha256'] != selection['capture_manifest_sha256'] or sha(blobs[capture + 'capture/manifest.json']) != selection['capture_manifest_sha256']:
        raise ValueError('Capture manifests disagree')
    for role in manifest['roles'].values():
        raw = blobs[capture + 'capture/' + role['payload']]
        if len(raw) != role['bytes'] or sha(raw) != role['sha256'] or raw != blobs[capture + role['basename']]:
            raise ValueError('Capture payload mismatch')
    for identity, name in [(receipt['selected_targets'], 'selected-targets.json'), (selection['raw_response'], 'response.json'), (selection['predictions_full'], 'predictions-full.csv')]:
        raw = blobs[capture + name]
        if identity != {'bytes': len(raw), 'sha256': sha(raw)}:
            raise ValueError('Capture identity mismatch')
    # Reuse the pinned capture parser against verified in-memory bytes; no network or main call.
    module = types.ModuleType('frozen_capture')
    module.__file__ = str(root / (prefix + 'capture.py'))
    exec(compile(blobs[prefix + 'capture.py'], module.__file__, 'exec'), module.__dict__)
    _, full = module.parse_payload(blobs[capture + 'response.json'])
    if module.csv_bytes(full) != blobs[capture + 'predictions-full.csv'] or module.targets(full, utc(selection['capture_finished_at_utc'])) != selection['targets']:
        raise ValueError('Capture raw, CSV or selected targets disagree')
    am = document(analogue + 'lock-001/manifest.json')
    if am['status'] != 'LOCKED_RESEARCH_ONLY' or am['methods'] != ['nwp_live', 'analogue_raw', 'analogue_solar']:
        raise ValueError('Unexpected analogue lock or candidate set')
    for field, name in [('protocol_sha256', 'PROTOCOL.md'), ('adapter_sha256', 'run.py'), ('input_identities_sha256', 'input-identities.json')]:
        if sha(blobs[analogue + name]) != am[field]:
            raise ValueError('Analogue source identity mismatch')
    if document(analogue + 'input-identities.json') != am['input_sha256']:
        raise ValueError('Analogue input manifests disagree')
    for name, expected in am['input_sha256'].items():
        if sha(blobs[name]) != expected:
            raise ValueError('Analogue input hash mismatch')
    for name, expected in am['output_sha256'].items():
        if sha(blobs[analogue + 'lock-001/' + name]) != expected:
            raise ValueError('Analogue output hash mismatch')
    first = utc(selection['targets']['primary']['intervals'][0]['interval_start_utc'])
    if not utc(selection['capture_finished_at_utc']) <= utc(am['lock_started_at_utc']) <= utc(am['lock_finished_at_utc']) < first:
        raise ValueError('Analogue was not locked before target start')
    candidates = {name: {method: {} for method in CANDIDATES} for name in GATES}
    originals = {name: {row['valid_time_utc']: row for row in group['intervals']} for name, group in selection['targets'].items()}
    records = document(analogue + 'lock-001/predictions.json')
    if len(records) != 144:
        raise ValueError('Expected 144 candidate rows')
    for row in records:
        name, method = row['target_set'], row['method']
        method = 'captured_raw' if method == 'nwp_live' else method
        if name not in candidates or method not in CANDIDATES or row['valid_time_utc'] not in originals[name]:
            raise ValueError('Unexpected candidate row')
        stamp = int(utc(row['valid_time_utc']).timestamp())
        if stamp in candidates[name][method]:
            raise ValueError('Duplicate candidate row')
        original = originals[name][row['valid_time_utc']]
        if any(row[key] != original[key] for key in ('interval_start_utc', 'start_lead_seconds', 'valid_time_lead_seconds')):
            raise ValueError('Candidate changed interval or lead')
        validate_candidate(row, original['shortwave_radiation_w_m2'], method)
        decision = None if row['probability'] is None else int(row['probability'] > .5)
        if row['predicted_positive'] != decision:
            raise ValueError('Candidate decision differs from fixed rule')
        candidates[name][method][stamp] = row
    for name in GATES:
        keys = {int(utc(row['valid_time_utc']).timestamp()) for row in originals[name].values()}
        if any(set(value) != keys for value in candidates[name].values()):
            raise ValueError('Candidate coverage changed')
        if max(keys) + 48 * 3600 != int(GATES[name].timestamp()):
            raise ValueError('Eligibility no longer matches frozen target set')
    return selection, candidates, lock


def run(name, output):
    output.mkdir()  # Never overwrite an earlier attempt, including a refusal.
    started = now()
    request_record = {'target_set': name, 'started_at_utc': started.isoformat(),
                      'eligible_at_utc': GATES[name].isoformat(), 'protocol_sha256': PROTOCOL_SHA,
                      'input_lock_sha256': LOCK_SHA, 'input_archive_sha256': ARCHIVE_SHA,
                      'durability_amendment_sha256': AMENDMENT_SHA, 'script_sha256': sha(Path(__file__).read_bytes())}
    targets = candidates = None
    try:
        gate(name, started)
        selection, all_candidates, lock = load_frozen()
        targets, candidates = selection['targets'][name]['intervals'], all_candidates[name]
        parameters = {'latitude': '34.7744', 'longitude': '32.4229', 'models': 'eumetsat_sarah3',
                      'hourly': 'shortwave_radiation', 'timezone': 'GMT', 'timeformat': 'unixtime',
                      'start_date': utc(targets[0]['valid_time_utc']).date().isoformat(),
                      'end_date': utc(targets[-1]['valid_time_utc']).date().isoformat()}
        url = 'https://satellite-api.open-meteo.com/v1/archive?' + urllib.parse.urlencode(parameters)
        request_record.update(url=url, parameters=parameters, input_files_sha256=lock['files_sha256'])
        save(output / 'request.json', request_record)
        gate(name, now())
        monotonic = time.monotonic()
        request = urllib.request.Request(url, headers={'User-Agent': 'Aktina-prospective-evaluation/1', 'Accept': 'application/json'})
        try:
            response = urllib.request.urlopen(request, timeout=90)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read(MAX_RESPONSE + 1)
            metadata = {'status': response.status, 'url': response.geturl(), 'headers': response.headers.as_string(),
                        'finished_at_utc': now().isoformat(), 'elapsed_monotonic_seconds': time.monotonic() - monotonic}
        save(output / 'reference-response.json', raw)
        save(output / 'reference-metadata.json', metadata)
        if len(raw) > MAX_RESPONSE or metadata['status'] != 200 or metadata['url'] != url:
            raise ValueError('Reference HTTP response unsuccessful, redirected or oversized')
        if utc(metadata['finished_at_utc']) < started:
            raise ValueError('Local clock moved backwards')
        gate(name, utc(metadata['finished_at_utc']))
        result = assess(targets, candidates, parse_reference(raw))
        save(output / 'assessment.json', result)
        save(output / 'rows.json', result['rows'])
        receipt = {'status': result['status'], 'target_set': name, 'request': request_record,
                   'finished_at_utc': now().isoformat(), 'output_sha256': {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}}
        save(output / 'receipt.json', receipt)
        return receipt
    except Exception as error:
        if not (output / 'request.json').exists():
            save(output / 'request.json', request_record)
        if targets is not None and not (output / 'rows.json').exists():
            rows = assess(targets, candidates, {})['rows']
            for row in rows:
                row['reference_status'] = 'invalid_or_unavailable_response'
                row['exclusion_reasons'] = ['invalid_or_unavailable_response']
            save(output / 'rows.json', rows)
        save(output / 'failure.json', {'status': 'REFUSED_EARLY' if started < GATES[name] else 'FAILED',
                                      'at_utc': now().isoformat(), 'error': f'{type(error).__name__}: {error}',
                                      'outputs_sha256': {p.name: sha(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}})
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-set', choices=GATES, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        receipt = run(args.target_set, args.output)
        print(json.dumps(receipt, indent=2))
        if receipt['status'] != 'COMPLETE':
            sys.exit(2)
    except Exception as error:
        print(f'FAILED: {type(error).__name__}: {error}', file=sys.stderr)
        sys.exit(1)
