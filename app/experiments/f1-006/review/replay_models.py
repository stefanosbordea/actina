"""Replay all saved classifiers against saved features, without fitting."""
import hashlib
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / 'result'


def main():
    hashes = {}

    def pin(path):
        hashes[path.relative_to(HERE.parent).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return path

    report = json.loads(pin(OUT / 'report.json').read_text())
    features = pd.read_csv(pin(OUT / 'features.csv'), index_col='feature_time',
                           float_precision='round_trip')
    assert features.index.is_unique
    assert features.columns.tolist() == report['features']
    checks = []
    for split in ('validation', 'test'):
        for name in ('small', 'medium', 'larger'):
            predictions = pd.read_csv(pin(OUT / 'predictions' / f'{split}-{name}.csv'),
                                      float_precision='round_trip')
            model = lgb.Booster(model_file=str(pin(OUT / 'models' / f'{split}-{name}.txt')))
            assert model.feature_name() == report['features']
            replay = model.predict(features.loc[predictions.feature_time], num_threads=2)
            expected = predictions.probability.to_numpy()
            assert np.isfinite(replay).all() and np.all((replay >= 0) & (replay <= 1))
            np.testing.assert_allclose(replay, expected, rtol=0, atol=1e-12)
            assert np.array_equal(replay > predictions.cutoff.to_numpy(), predictions.predicted_positive.to_numpy())
            assert np.array_equal(replay > .5, predictions.default_positive.to_numpy())
            checks.append({'split': split, 'method': name, 'hours': len(replay),
                           'max_probability_abs_error': float(np.abs(replay - expected).max()),
                           'selected_and_default_decisions_match': True})
    for name, expected in hashes.items():
        assert hashlib.sha256((HERE.parent / name).read_bytes()).hexdigest() == expected
    return {'status': 'PASS', 'scope': 'Saved models replayed against retained feature rows; no fit or selection.',
            'lightgbm_version': lgb.__version__, 'checks': checks, 'input_sha256': hashes,
            'code_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(main(), indent=2))
