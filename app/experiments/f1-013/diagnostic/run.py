"""Explain every saved exact 013 decision without opening realized outcomes."""
from collections import Counter
import csv
from datetime import datetime, timezone
from fractions import Fraction as F
import gzip
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
FAMILIES = ('precision', 'recall', 'f1')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p, value):
    p.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def fraction(value):
    if value is None:
        return None
    result = F(value['numerator'], value['denominator'])
    if float(result) != value['value']:
        raise AssertionError('Display fraction mismatch')
    return result


def exact(value):
    return dict(numerator=value.numerator, denominator=value.denominator, value=float(value))


def diagnose(record):
    baseline = [{k: fraction(v) for k, v in ref.items()} for ref in record['raw_metrics']]
    candidates = []
    for c in record['candidates']:
        scores = [{k: fraction(v) for k, v in ref.items()} for ref in c['metrics']]
        failures = {'zero_call_precision'} if c['positive_calls'] == 0 and baseline[0]['precision'] is not None else set()
        for r in range(2):
            for name in FAMILIES:
                if baseline[r][name] is not None and (scores[r][name] is None or scores[r][name] < baseline[r][name]):
                    failures.add(f'{r}/{name}')
        if failures != set(c['failed_constraints']):
            raise AssertionError('Saved guard failure mismatch')
        gains = [scores[r]['f1'] - baseline[r]['f1'] for r in range(2)]
        objectives = dict(robust=min(gains), pooled=sum(gains, F()) / 2)
        if objectives != {k: fraction(v) for k, v in c['objectives'].items()}:
            raise AssertionError('Saved exact objective mismatch')
        candidates.append(dict(c=c, failures=failures, gains=gains, objectives=objectives))
    raw = [c for c in candidates if c['c']['changed_bits'] == 0]
    if len(raw) != 1 or raw[0]['failures'] or raw[0]['objectives'] != dict(robust=F(), pooled=F()):
        raise AssertionError('Raw candidate identity')
    k0 = raw[0]['c']['positive_calls']
    admitted = [c for c in candidates if 'zero_call_precision' not in c['failures']]
    families = lambda c: {f.split('/')[1] for f in c['failures']}
    feasible = [c for c in admitted if not c['failures']]
    own_unguarded = [{i for i,c in enumerate(admitted) if c['gains'][r] > 0} for r in range(2)]
    own_guarded = [{i for i,c in enumerate(admitted) if c['gains'][r] > 0 and not any(f.startswith(str(r) + '/') for f in c['failures'])} for r in range(2)]
    for arm in ('robust', 'pooled'):
        positive = [c for c in admitted if c['objectives'][arm] > 0]
        full_positive = [c for c in positive if not c['failures']]
        selected = record['arms'][arm]
        best = max((c['objectives'][arm] for c in feasible), default=None)
        if best != fraction(selected['objective']):
            raise AssertionError('Saved selected objective mismatch')
        item = dict(stage=record['stage'], day=record['day'], bank=record['bank'], objective=arm,
            raw_calls=k0, raw_zero_calls=int(k0 == 0), uncertain_hours=len(record['uncertain']),
            retained_candidates=len(candidates), admissible_candidates=len(admitted), count_rule_rejected=len(candidates) - len(admitted),
            feasible_candidates=len(feasible), only_raw_feasible=int(len(feasible) == 1),
            feasible_nonraw=len(feasible) - 1, feasible_nonraw_zero_gain=sum(c['c']['changed_bits'] > 0 and c['objectives'][arm] == 0 for c in feasible),
            positive_before_guards=len(positive), positive_after_all=len(full_positive),
            no_positive_before_guards=int(not positive), guards_remove_all_positive=int(bool(positive) and not full_positive),
            selected_changes=selected['changed_bits'], selected_calls=selected['positive_calls'],
            selected_changed_count=int(selected['positive_calls'] != k0),
            positive_same_count=sum(c['c']['positive_calls'] == k0 for c in positive),
            positive_changed_count=sum(c['c']['positive_calls'] != k0 for c in positive),
            reference_f1_conflict_unguarded=int(all(own_unguarded) and not (own_unguarded[0] & own_unguarded[1])),
            reference_f1_conflict_own_guards=int(all(own_guarded) and not (own_guarded[0] & own_guarded[1])))
        for family in FAMILIES:
            alone = [c for c in positive if family not in families(c)]
            without = [c for c in positive if families(c) <= {family}]
            item[f'positive_after_{family}_alone'] = len(alone)
            item[f'positive_after_all_except_{family}'] = len(without)
            item[f'{family}_alone_blocks_day'] = int(bool(positive) and not alone)
            item[f'{family}_necessary_for_rejection'] = int(bool(without) and not full_positive)
            item[f'{family}_failed_positive_candidates'] = sum(family in families(c) for c in positive)
        remaining = positive
        for family in FAMILIES:
            remaining = [c for c in remaining if family not in families(c)]
            item[f'positive_after_ordered_{family}'] = len(remaining)
        permitted = [{i for i,c in enumerate(positive) if not any(f.startswith(str(r) + '/') for f in c['failures'])} for r in range(2)]
        for r in range(2):
            item[f'reference_{r}_alone_permits_positive'] = len(permitted[r])
            item[f'reference_{r}_alone_blocks_day'] = int(bool(positive) and not permitted[r])
        item['reference_guard_intersection_conflict'] = int(all(permitted) and not (permitted[0] & permitted[1]))
        item['maximum_before_guards'] = str(max(c['objectives'][arm] for c in admitted))
        item['maximum_after_all_guards'] = str(best)
        yield item


def execute():
    started, cpu = time.perf_counter(), time.process_time()
    out = HERE / 'result'
    out.mkdir(exist_ok=False)
    receipt = dict(command=sys.argv, started_at_utc=datetime.now(timezone.utc).isoformat(), outcomes_opened=False)
    try:
        pins = json.loads((HERE / 'inputs.json').read_text())
        for relative, value in pins.items():
            if sha(BASE / relative) != value:
                raise AssertionError('Changed diagnostic input: ' + relative)
        freeze = json.loads((BASE / 'result/planning-freeze.json').read_text())['files_sha256']
        outputs = json.loads((BASE / 'result/outputs.json').read_text())
        results = []
        for stage in ('validation', 'test'):
            key = stage + '/decisions.jsonl.gz'
            identity = sha(BASE / 'result' / key)
            if identity != freeze[key] or identity != outputs[key]:
                raise AssertionError('Decision-freeze identity')
            with gzip.open(BASE / 'result' / key, 'rt') as stream:
                for line in stream:
                    record = json.loads(line)
                    if record['stage'] != stage:
                        raise AssertionError('Period identity')
                    results.extend(diagnose(record))
        if len(results) != 1196 or len({(r['stage'],r['day'],r['bank'],r['objective']) for r in results}) != 1196:
            raise AssertionError('Complete day/bank/objective membership')
        with (out / 'every-day.csv').open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(results[0]))
            writer.writeheader()
            writer.writerows(results)
        summary = {}
        for stage in ('validation', 'test'):
            for bank in ('recency', 'conditional'):
                for arm in ('robust', 'pooled'):
                    selected = [r for r in results if (r['stage'], r['bank'], r['objective']) == (stage,bank,arm)]
                    totals = {k: sum(r[k] for r in selected) for k,v in selected[0].items() if isinstance(v,int)}
                    totals.update(days=len(selected), days_with_strict_objective_gain_before_guards=sum(r['positive_before_guards'] > 0 for r in selected),
                        days_with_strict_objective_gain_after_guards=sum(r['positive_after_all'] > 0 for r in selected),
                        days_multiple_feasible_actions=sum(r['feasible_candidates'] > 1 for r in selected),
                        selected_changed_days=sum(r['selected_changes'] > 0 for r in selected),
                        maximum_before_guards=exact(max(F(r['maximum_before_guards']) for r in selected)),
                        maximum_after_all_guards=exact(max(F(r['maximum_after_all_guards']) for r in selected)),
                        feasible_action_count_distribution=dict(sorted(Counter(r['feasible_candidates'] for r in selected).items())))
                    summary[f'{stage}/{bank}/{arm}'] = totals
        dump(out / 'summary.json', dict(scope='Exact retained forecast-scenario ledgers only. No realized scores or policy change.', groups=summary))
        for relative, value in pins.items():
            if sha(BASE / relative) != value:
                raise AssertionError('Input changed during diagnostic: ' + relative)
        receipt.update(status='PASS', exit_code=0, rows=len(results), input_lock_sha256=sha(HERE / 'inputs.json'))
    except BaseException as error:
        receipt.update(status='FAILED', exit_code=1, error_type=type(error).__name__, error=str(error))
        raise
    finally:
        receipt.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.perf_counter()-started,
            cpu_seconds=time.process_time()-cpu, peak_rss_bytes=int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform == 'darwin' else 1024))
        dump(out / 'execution-receipt.json', receipt)
        dump(out / 'outputs.json', {p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file() and p.name != 'outputs.json'})
    print(json.dumps(receipt))


if __name__ == '__main__':
    execute()
