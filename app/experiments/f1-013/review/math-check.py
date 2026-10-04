"""Exact synthetic enumeration only. No historical inputs or production imports."""
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
from itertools import product
import json
from pathlib import Path
import random
import time

HERE = Path(__file__).resolve().parent
start = time.perf_counter()
checks = 0


def check(ok, label):
    global checks
    checks += 1
    if not ok:
        raise AssertionError(label)


def score(paths, action):
    k = action.bit_count()
    pairs = [((truth & action).bit_count(), truth.bit_count()) for truth in paths]
    positive = [(tp, s) for tp, s in pairs if s]
    return (F(sum(tp for tp, s in pairs), len(paths)*k) if k else None,
            sum((F(tp, s) for tp, s in positive), F(0))/len(positive) if positive else None,
            sum((F(2*tp, k+s) if k+s else F(1) for tp, s in pairs), F(0))/len(paths))


def coefficient_score(paths, action, hours):
    k = action.bit_count()
    nplus = sum(bool(v) for v in paths)
    p = [F(sum(bool(v & (1 << h)) for v in paths), len(paths)) for h in range(hours)]
    c = [sum((F(1, v.bit_count()) for v in paths if v & (1 << h)), F(0))/nplus if nplus else None for h in range(hours)]
    a = [sum((F(2, k+v.bit_count()) for v in paths if v & (1 << h)), F(0))/len(paths) for h in range(hours)] if k else None
    selected = [h for h in range(hours) if action & (1 << h)]
    return (sum((p[h] for h in selected), F(0))/k if k else None,
            sum((c[h] for h in selected), F(0)) if nplus else None,
            sum((a[h] for h in selected), F(0)) if k else F(sum(v == 0 for v in paths), len(paths)))


def compare_case(refs, raw, hours):
    scores = {a:tuple(score(paths, a) for paths in refs) for a in range(1 << hours)}
    base = scores[raw]
    for action, values in scores.items():
        for paths, value in zip(refs, values):
            check(value == coefficient_score(paths, action, hours), 'direct ratios match coefficients')
    def feasible(action):
        if raw and not action:
            return False
        for values, original in zip(scores[action], base):
            for i in range(3):
                if original[i] is not None and (values[i] is None or values[i] < original[i]):
                    return False
        return True
    full = [a for a in scores if feasible(a)]
    check(raw in full, 'raw is always feasible')
    positive = (1 << hours)-1
    possible = 0
    for paths in refs:
        for truth in paths:
            positive &= truth
            possible |= truth
    ambiguous = possible ^ positive
    canonical = [a for a in scores if a & positive == positive and not a & ~possible]
    reduced = sorted({raw, *canonical} & set(full))
    result = {}
    for objective in ('minimum','mean'):
        def rank(action):
            gains = [v[2]-b[2] for v,b in zip(scores[action],base)]
            gain = min(gains) if objective == 'minimum' else sum(gains,F(0))/2
            selected = tuple(h for h in range(hours) if action & (1 << h))
            return (-gain, (action ^ raw).bit_count(), action.bit_count(), selected)
        best, restricted = min(full,key=rank), min(reduced,key=rank)
        check(best == restricted and rank(best) == rank(restricted), 'full lexicographic optimum preserved')
        check(rank(best)[0] < 0 or best == raw, 'zero-gain fallback is raw')
        result[objective] = best
    return result


# All two-reference, two-scenario distributions on two hours, all raw vectors.
distribution_cases = 0
for values in product(range(4), repeat=4):
    refs = (values[:2], values[2:])
    for raw in range(4):
        compare_case(refs,raw,2)
        distribution_cases += 1

# Larger synthetic cases use four equally weighted patterns, repeatable16x to64.
rng = random.Random(20261004)
random_cases = 0
for _ in range(128):
    refs = tuple(tuple(rng.randrange(16) for _ in range(4)) for _ in range(2))
    for raw in range(16):
        compare_case(refs,raw,4)
        random_cases += 1

check(score((0,0),0) == (None,None,F(1)), 'empty action and truth')
check(score((0,0),1) == (F(0),None,F(0)), 'positive call with empty truth')
check(compare_case(((0,0),(0,0)),1,2) == {'minimum':1,'mean':1}, 'sole negative cannot become prohibited empty action')
check(compare_case(((0,0),(0,0)),0,2) == {'minimum':0,'mean':0}, 'empty raw remains optimal')
check(compare_case(((0,1),(0,1)),0,2) == {'minimum':0,'mean':0}, 'recall-only gain cannot override zero F1 gain')
check(compare_case(((3,3),(3,3)),1,3) == {'minimum':3,'mean':3}, 'optimal call count increases')
check(compare_case(((1,1),(1,1)),3,3) == {'minimum':1,'mean':1}, 'optimal call count decreases')
check(compare_case(((1,1),(2,2)),1,2) == {'minimum':1,'mean':1}, 'reference safeguards reject conflict')
check(score((0,3),1) == (F(1,2),F(1,2),F(1,3)), 'dependent empty/full distribution')
check(score((1,2),1) == (F(1,2),F(1,2),F(1,2)), 'same marginals but different F1')
check(not F(1,2)-F(1,10**30) >= F(1,2), 'strict rational safeguard without tolerance')

result = dict(status='PASS',scope='Synthetic mathematics only, no saved forecast or realized outcome read',checks=checks,
    exhaustive_two_hour_distributions=256,exhaustive_two_hour_raw_cases=distribution_cases,
    seeded_four_hour_distributions=128,seeded_four_hour_raw_cases=random_cases,
    objectives=['minimum F1 uplift','mean F1 uplift'],tie_order=['objective','fewer changes','smaller K','selected-hour tuple'],
    conclusions=['Coefficient formulas equal direct scenario ratios, including K0 and empty-truth cases','Reduction plus raw retains exact full lexicographic optimum on every checked case','Daily empirical safeguards do not establish pooled realized improvement'],
    code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),completed_at_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start)
(HERE/'math-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
