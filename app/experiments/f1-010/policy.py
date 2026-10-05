"""One deterministic paired exchange; probabilities are not calibrated claims."""
import numpy as np

MARGINS = (0., .05, .10, .20, .30, .50)


def best_pair(baseline, weather, satellite, arm):
    b, w, s = np.asarray(baseline), np.asarray(weather), np.asarray(satellite)
    if b.dtype != bool or b.ndim != 1 or len(b) != 24 or w.shape != b.shape or s.shape != b.shape:
        raise ValueError('One complete, ordered 24-hour day required')
    if arm not in ('min', 'mean') or not np.isfinite(w).all() or not np.isfinite(s).all() or np.any((w < 0) | (w > 1) | (s < 0) | (s > 1)):
        raise ValueError('Invalid arm or probability')
    best = None
    for add in np.flatnonzero(~b):
        for remove in np.flatnonzero(b):
            dw, ds = float(w[add] - w[remove]), float(s[add] - s[remove])
            value = min(dw, ds) if arm == 'min' else (dw + ds) / 2
            pair = dict(add=int(add), remove=int(remove), weather_difference=dw,
                        satellite_difference=ds, score=value)
            # Sorted iteration retains earliest add, then earliest remove on an exact tie.
            if best is None or value > best['score']: best = pair
    return best


def apply_pair(baseline, pair, margin):
    if margin not in MARGINS: raise ValueError('Undeclared margin')
    decision = np.asarray(baseline, dtype=bool).copy()
    if pair is not None and pair['score'] > margin:
        if decision[pair['add']] or not decision[pair['remove']]: raise ValueError('Invalid pair direction')
        decision[pair['add']], decision[pair['remove']] = True, False
    if np.sum(decision) != np.sum(baseline): raise AssertionError('Positive-count preservation')
    return decision
