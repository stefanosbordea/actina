"""Constrain a numeric correction while retaining the reference forecast's event."""
import math


def constrain_correction(nwp, corrected, threshold=600.0):
    """Nearest allowed binary64 point; the event is strictly greater than threshold."""
    values = []
    for name, value in (('nwp', nwp), ('corrected', corrected), ('threshold', threshold)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f'{name} must be a finite nonnegative number')
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError(f'{name} exceeds binary64 range') from error
        if not math.isfinite(value) or value < 0:
            raise ValueError(f'{name} must be a finite nonnegative number')
        values.append(value)
    nwp, corrected, threshold = values
    return max(corrected, math.nextafter(threshold, math.inf)) if nwp > threshold else min(corrected, threshold)
