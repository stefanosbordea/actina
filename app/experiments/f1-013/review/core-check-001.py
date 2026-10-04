"""Independent synthetic oracle for actual decision.py. Reads no historical data."""
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import importlib.util
from itertools import product
import json
from pathlib import Path
import random
import resource
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'decision.py'
SOURCE_HASH = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('actual_decision', SOURCE)
actual = importlib.util.module_from_spec(spec)
spec.loader.exec_module(actual)
checks = 0
coverage = Counter()
start, cpu = time.perf_counter(), time.process_time()


def check(condition, label):
    global checks
    checks += 1
    if not condition:
        raise AssertionError(label)


def bits(mask, hours):
    return [bool(mask & (1 << i)) for i in range(hours)]


def action_mask(values):
    return sum(int(bool(value)) << i for i, value in enumerate(values))


def scores(paths, mask):
    count = mask.bit_count()
    result = []
    for truth in paths:
        hits = [(mask & y).bit_count() for y in truth]
        nonempty = [F(tp, y.bit_count()) for tp, y in zip(hits, truth) if y]
        result.append(dict(
            precision=sum((F(tp, count) for tp in hits), F()) / len(truth) if count else None,
            recall=sum(nonempty, F()) / len(nonempty) if nonempty else None,
            f1=sum((F(2 * tp, count + y.bit_count()) if count + y.bit_count() else F(1)
                    for tp, y in zip(hits, truth)), F()) / len(truth)))
    return result


def failed(score, baseline, mask, raw):
    result = ['zero_call_precision'] if raw and not mask else []
    for r, (now, before) in enumerate(zip(score, baseline)):
        for metric in ('precision', 'recall', 'f1'):
            if before[metric] is not None and (now[metric] is None or now[metric] < before[metric]):
                result.append(f'{r}/{metric}')
    return result


def objectives(score, baseline):
    uplift = [s['f1'] - b['f1'] for s, b in zip(score, baseline)]
    return dict(robust=min(uplift), pooled=sum(uplift, F()) / len(uplift))


def case(paths, raw, hours, repeat=False):
    y = np.asarray([[bits(mask, hours) for mask in ref] for ref in paths])
    answer = actual.solve(y, bits(raw, hours))
    direct = {mask: scores(paths, mask) for mask in range(1 << hours)}
    baseline = direct[raw]
    check(answer['raw_metrics'] == baseline, 'actual baseline differs from independent exact ratios')
    possible = 0
    positive = (1 << hours) - 1
    for ref in paths:
        for mask in ref:
            possible |= mask
            positive &= mask
    negative = ((1 << hours) - 1) ^ possible
    ambiguous = possible ^ positive
    check(answer['unanimous_positive'] == [i for i in range(hours) if positive & (1 << i)], 'positive reduction')
    check(answer['unanimous_negative'] == [i for i in range(hours) if negative & (1 << i)], 'negative reduction')
    check(answer['uncertain'] == [i for i in range(hours) if ambiguous & (1 << i)], 'uncertain reduction')
    check(answer['canonical_subsets'] == 1 << ambiguous.bit_count(), 'subset count')
    canonical = {m for m in direct if m & positive == positive and not m & negative}
    expected = canonical | {raw}
    ledger = answer['candidates']
    check(len(ledger) == len(expected), 'candidate ledger count')
    check({action_mask(row['decision']) for row in ledger} == expected, 'candidate ledger membership')
    for row in ledger:
        mask = action_mask(row['decision'])
        check(row['metrics'] == direct[mask], 'candidate score differs from oracle')
        check(row['failed_constraints'] == failed(direct[mask], baseline, mask, raw), 'candidate failed safeguards')
        check(row['objectives'] == objectives(direct[mask], baseline), 'candidate objective')
        check(row['positive_calls'] == mask.bit_count(), 'candidate K')
        check(row['changed_bits'] == (mask ^ raw).bit_count(), 'candidate changes')
        coverage['ledger_rows'] += 1
    for r, (table, truth) in enumerate(zip(answer['coefficients'], paths)):
        n, active = len(truth), sum(bool(v) for v in truth)
        check(table['scenarios'] == n and table['positive_scenarios'] == active, 'scenario counts')
        check(table['empty_f1'] == F(n - active, n), 'empty F1 coefficient')
        for i in range(hours):
            mask = 1 << i
            check(table['probability'][i] == F(sum(bool(v & mask) for v in truth), n), 'marginal coefficient')
            if active:
                expected_recall = sum((F(1, v.bit_count()) for v in truth if v & mask), F()) / active
                check(table['recall'][i] == expected_recall, 'conditional recall coefficient')
            else:
                check(table['recall'] is None, 'undefined recall coefficient')
            for k in range(1, hours + 1):
                coefficient = sum((F(2, k + v.bit_count()) for v in truth if v & mask), F()) / n
                check(table['f1'][k][i] == coefficient, 'count-dependent F1 coefficient')
    feasible = [mask for mask in direct if not failed(direct[mask], baseline, mask, raw)]
    check(raw in feasible, 'independent raw feasibility')
    for arm in ('robust', 'pooled'):
        def rank(mask):
            return (-objectives(direct[mask], baseline)[arm], (mask ^ raw).bit_count(), mask.bit_count(),
                    tuple(i for i in range(hours) if mask & (1 << i)))
        best = min(feasible, key=rank)
        chosen = answer['arms'][arm]
        check(action_mask(chosen['decision']) == best, 'actual reduced optimum differs from full-action oracle')
        check(chosen['metrics'] == direct[best], 'selected metrics')
        check(chosen['objective'] == -rank(best)[0], 'selected objective')
        check(chosen['changed_bits'] == (best ^ raw).bit_count(), 'selected changes')
        check(chosen['positive_calls'] == best.bit_count(), 'selected K')
        check(chosen['objective'] > 0 or best == raw, 'strict primary-gain fallback')
        coverage['raw_fallback' if best == raw else 'strict_gain'] += 1
        coverage['count_increase' if best.bit_count() > raw.bit_count() else 'count_decrease' if best.bit_count() < raw.bit_count() else 'count_equal'] += 1
        tied = feasible
        for depth, name in enumerate(('objective', 'changes', 'K', 'tuple')):
            minimum = min(rank(mask)[depth] for mask in tied)
            remaining = [mask for mask in tied if rank(mask)[depth] == minimum]
            if len(remaining) < len(tied) and len(tied) > 1:
                coverage['tie_resolved_' + name] += 1
            tied = remaining
        check(len(tied) == 1 and tied[0] == best, 'total rank')
    if repeat:
        check(answer == actual.solve(y, bits(raw, hours)), 'repeat determinism')
        check(answer == actual.solve(y[:, ::-1], bits(raw, hours)), 'shared scenario permutation')
        check(answer == actual.solve(np.repeat(y, 16, axis=1), bits(raw, hours)) or
              all(answer['arms'][arm] == actual.solve(np.repeat(y, 16, axis=1), bits(raw, hours))['arms'][arm]
                  for arm in ('robust', 'pooled')), 'uniform scenario repetition selected decisions')
    coverage['cases'] += 1


# Every two-reference, two-scenario distribution and raw action at two hours.
for values in product(range(4), repeat=4):
    paths = (values[:2], values[2:])
    for raw in range(4):
        case(paths, raw, 2, repeat=(raw == 0 and values[0] == values[1] == 0))
coverage['exhaustive_two_hour_distributions'] = 256

rng = random.Random(20261004)
for distribution in range(128):
    paths = tuple(tuple(rng.randrange(16) for _ in range(4)) for _ in range(2))
    for raw in range(16):
        case(paths, raw, 4, repeat=(distribution < 3 and raw == 0))
coverage['seeded_four_hour_distributions'] = 128

# Force unanimous hours, including all-empty and sole-negative count restrictions.
for paths, raw, hours in [(((0, 0), (0, 0)), 1, 3), (((0, 0), (0, 0)), 0, 3),
                          (((0, 1), (0, 1)), 0, 3), (((3, 3), (3, 3)), 1, 3),
                          (((1, 1), (1, 1)), 3, 3), (((1, 1), (2, 2)), 1, 3)]:
    case(paths, raw, hours, repeat=True)
for _ in range(64):
    paths = tuple(tuple((rng.randrange(64) << 1) | 1 for _ in range(5)) for _ in range(2))
    case(paths, rng.randrange(256), 8)
coverage['seeded_eight_hour_cases'] = 64

check(actual.events([-5, 600., np.nextafter(600., np.inf)]).tolist() == [False, False, True], 'strict binary64 event boundary')
for invalid in ([float('nan')], [float('inf')], [float('-inf')]):
    try:
        actual.events(invalid)
    except ValueError:
        coverage['malformed_rejections'] += 1
    else:
        raise AssertionError('Nonfinite event data accepted')
for scenario, raw in [(np.zeros((1, 2, 3)), [0] * 3), (np.zeros((2, 0, 3)), [0] * 3),
                      (np.zeros((2, 1, 0)), []), (np.zeros((2, 1, 25)), [0] * 25),
                      (np.zeros((2, 1, 3)), [0]), (np.full((2, 1, 3), .5), [0] * 3),
                      (np.zeros((2, 1, 3)), [0, 0, np.nan])]:
    try:
        actual.solve(scenario, raw)
    except ValueError:
        coverage['malformed_rejections'] += 1
    else:
        raise AssertionError('Malformed solver input accepted')
for metric in ('precision', 'recall', 'f1'):
    previous = [dict(precision=F(1, 2), recall=F(1, 2), f1=F(1, 2)) for _ in range(2)]
    candidate = [dict(row) for row in previous]
    candidate[1][metric] -= F(1, 10**40)
    check(float(candidate[1][metric]) == float(previous[1][metric]), 'fixture is below float resolution')
    check(actual.failures(candidate, previous, 1, 1) == ['1/' + metric], 'exact sub-float safeguard rejected')
try:
    actual.solve(np.zeros((2, 1, 3)), [0, 0, 0], deadline=time.monotonic() - 1)
except TimeoutError:
    coverage['deadline_rejections'] += 1
else:
    raise AssertionError('Expired runtime deadline accepted')
check(SOURCE_HASH == hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'actual source stable during check')
for field in ('tie_resolved_changes', 'tie_resolved_K', 'tie_resolved_tuple', 'strict_gain', 'raw_fallback', 'count_increase', 'count_decrease'):
    check(coverage[field] > 0, 'missing coverage: ' + field)
result = dict(status='PASS', scope='Actual production solver tested against independent full-action synthetic oracle. No historical arrays, predictions or outcomes opened.',
              actual_code_sha256=SOURCE_HASH, checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              checks=checks, coverage=dict(coverage), completed_at_utc=datetime.now(timezone.utc).isoformat(),
              wall_seconds=time.perf_counter() - start, cpu_seconds=time.process_time() - cpu,
              peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              limitations=['Finite synthetic coverage does not prove arbitrary inputs', 'Does not verify historical candidate generation or realized scores'])
print(json.dumps(result, indent=2))
