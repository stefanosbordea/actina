"""Read LightGBM's native model text without executing the pickle object."""
import argparse
import csv
import hashlib
import json
import pickletools
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def native_model(path):
    strings = [arg for _, arg, _ in pickletools.genops(path.read_bytes())
               if isinstance(arg, str) and arg.startswith('tree\nversion=')]
    if len(strings) != 1:
        raise ValueError('Expected exactly one native LightGBM model')
    return strings[0]

def main():
    import lightgbm as lgb
    import numpy as np
    import pandas as pd

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    source = ROOT / 'model/lgbm_radiation.pkl'
    model = lgb.Booster(model_str=native_model(source))
    frame = pd.read_csv(ROOT / 'data/features.csv', index_col=0, parse_dates=True)
    expected = pd.read_csv(ROOT / 'eval/test_predictions.csv', index_col=0, parse_dates=True)
    features = frame.drop(columns='target')
    if model.feature_name() != list(features.columns):
        raise ValueError('Model feature order differs from the supplied table')
    values = model.predict(features.loc[expected.index], num_threads=2)
    difference = np.abs(values - expected.predicted.to_numpy())
    gain = model.feature_importance('gain')
    splits = model.feature_importance('split')
    importance = sorted([{'feature': name, 'gain': float(g), 'gain_share': float(g/gain.sum()),
                        'splits': int(n)} for name,g,n in zip(model.feature_name(),gain,splits)],
                        key=lambda r: -r['gain'])
    report = {'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'native_model_sha256': hashlib.sha256(native_model(source).encode()).hexdigest(),
              'lightgbm_version': lgb.__version__, 'trees': model.num_trees(),
              'test_hours': len(expected), 'test_max_absolute_difference_w_m2': float(difference.max()),
              'matches_retained_test_at_1e_minus_8': bool(np.all(difference < 1e-8)),
              'importance': importance,
              'interpretation': 'Training split-gain importance, not causal importance or a held-out contribution estimate.',
              'evaluator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    with (out / 'feature-importance.csv').open('w', newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(importance[0])); writer.writeheader(); writer.writerows(importance)
    print(json.dumps(report, separators=(',',':')))
    if not report['matches_retained_test_at_1e_minus_8']:
        raise SystemExit('Native model differs from the retained forecasts; do not claim attribution.')

if __name__ == '__main__':
    main()
