"""Forecast-error context using only observations strictly before each origin."""
import numpy as np
import pandas as pd

WINDOW = pd.Timedelta(days=14)
NAMES = ["past_v2_bias", "past_v2_mae", "past_ecmwf_bias", "past_ecmwf_mae"]


def build(origins, predictions, observations):
    assert predictions.index.is_unique and observations.index.is_unique
    assert predictions.index.is_monotonic_increasing and observations.index.is_monotonic_increasing
    outputs = pd.DataFrame(index=origins)
    audit = pd.DataFrame(index=origins)
    for model, field in (("v2", "v2_prediction"), ("ecmwf", "ecmwf_prediction")):
        known = predictions[[field]].join(observations[["actual"]], how="inner").dropna()
        assert np.isfinite(known.to_numpy()).all()
        errors = known[field].to_numpy() - known["actual"].to_numpy()
        for origin in origins:
            first = known.index.searchsorted(origin - WINDOW, side="left")
            stop = known.index.searchsorted(origin, side="left")
            values = errors[first:stop]
            times = known.index[first:stop]
            if len(times):
                assert times.min() >= origin - WINDOW and times.max() < origin
            outputs.loc[origin, f"past_{model}_bias"] = float(values.mean()) / 100 if len(values) else 0.
            outputs.loc[origin, f"past_{model}_mae"] = float(np.abs(values).mean()) / 100 if len(values) else 0.
            audit.loc[origin, f"{model}_count"] = len(values)
            audit.loc[origin, f"{model}_latest_target"] = str(times[-1]) if len(times) else ""
    audit["v2_count"] = audit["v2_count"].astype(int)
    audit["ecmwf_count"] = audit["ecmwf_count"].astype(int)
    assert np.isfinite(outputs.to_numpy()).all()
    assert list(outputs) == NAMES
    return outputs, audit
