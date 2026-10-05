import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from policy import best_pair, apply_pair, MARGINS
spec = importlib.util.spec_from_file_location('experiment010', HERE / 'run.py')
run = importlib.util.module_from_spec(spec); spec.loader.exec_module(run)


class PairTests(unittest.TestCase):
    def test_full_count_identity_and_mask_exception(self):
        b = np.zeros(24, dtype=bool); b[[0, 1]] = True
        w = np.zeros(24); w[2] = 1
        pair = best_pair(b, w, w, 'min')
        d = apply_pair(b, pair, 0.)
        self.assertEqual(d.sum(), b.sum())
        truth = np.zeros(24, dtype=bool); truth[2] = True
        before = run.prior.score(truth, b); after = run.prior.score(truth, d)
        delta_tp = after['tp'] - before['tp']
        self.assertEqual(after['fp'] - before['fp'], -delta_tp)
        self.assertEqual(after['fn'] - before['fn'], -delta_tp)
        self.assertEqual(d[:2].sum(), 1)  # A partial-day score mask breaks K preservation.

    def test_min_and_mean_disagree(self):
        b = np.zeros(24, dtype=bool); b[0] = True
        w = np.zeros(24); s = np.zeros(24)
        w[:3] = [.5, .95, .6]; s[:3] = [.5, .45, .6]
        self.assertEqual(best_pair(b, w, s, 'min')['add'], 2)
        self.assertEqual(best_pair(b, w, s, 'mean')['add'], 1)

    def test_ties_earliest_added_then_removed(self):
        b = np.zeros(24, dtype=bool); b[[2, 3]] = True
        p = np.full(24, .75); p[[2, 3]] = .25
        pair = best_pair(b, p, p, 'min')
        self.assertEqual((pair['add'], pair['remove']), (0, 2))
        self.assertTrue(np.array_equal(apply_pair(b, pair, .5), b))
        self.assertFalse(np.array_equal(apply_pair(b, pair, .3), b))

    def test_no_pair_and_validation(self):
        p = np.zeros(24)
        for truth in (False, True): self.assertIsNone(best_pair(np.full(24, truth), p, p, 'min'))
        b = np.zeros(24, dtype=bool)
        for invalid in (np.full(24, np.nan), np.full(24, 1.01)):
            with self.assertRaises(ValueError): best_pair(b, invalid, p, 'min')
        with self.assertRaises(ValueError): best_pair(b[:-1], p, p, 'min')
        with self.assertRaises(ValueError): apply_pair(b, None, .25)

    def test_every_margin_preserves_count(self):
        rng = np.random.default_rng(19)
        for _ in range(50):
            b = rng.random(24) > .5; w = rng.random(24); s = rng.random(24)
            for arm in ('min', 'mean'):
                for margin in MARGINS:
                    d = apply_pair(b, best_pair(b, w, s, arm), margin)
                    self.assertEqual(int(d.sum()), int(b.sum()))
                    self.assertIn(int(np.sum(d != b)), (0, 2))

    def test_common_issue_replaces_later_state(self):
        names = ['temperature_2m', 'shortwave_radiation', 'relative_humidity_2m', 'cloud_cover',
            'radiation_yesterday', 'hour', 'month', 'nwp_day2_radiation', 'nwp_day2_cloud', 'target_hour_sin',
            'target_hour_cos', 'target_season_sin', 'target_season_cos', 'nwp_day2_cloud_missing', 'solar_scale',
            'mean_coszen', 'solar_hour_sin', 'solar_hour_cos', 'nwp_over_solar_scale', *run.HISTORY,
            'gfs_day2_radiation', 'gfs_minus_ecmwf', 'gfs_ecmwf_absolute_difference']
        origin = pd.date_range('2024-09-15', periods=24, freq='h')
        f = pd.DataFrame(0., index=range(24), columns=names)
        f.insert(0, 'feature_time', origin.astype(str))
        for name in ('residual_mean_24', 'residual_mean_168', 'residual_lag24'): f[name] = np.nan
        t = pd.DataFrame({'target_time': origin + pd.Timedelta(hours=24), 'actual': np.arange(24.)})
        raw = pd.DataFrame({name: np.arange(72.) for name in run.WEATHER}, index=pd.date_range('2024-09-14', periods=72, freq='h'))
        x, meta = run.issue_features(f, t, raw)
        self.assertEqual(x.lead_hours.tolist(), list(range(24,48)))
        self.assertTrue((x.issue_temperature_2m == 23.).all())
        self.assertTrue((x.issue_radiation_lag24 == 0.).all())
        self.assertTrue((meta.maximum_source_time < meta.issue_time).all())
        raw.loc[raw.index >= pd.Timestamp('2024-09-15')] = 99999
        f.loc[1:, list(run.WEATHER) + list(run.HISTORY)] = 99999
        changed, changed_meta = run.issue_features(f, t, raw)
        pd.testing.assert_frame_equal(changed, x)
        pd.testing.assert_frame_equal(changed_meta, meta)

    def test_undefined_metrics_never_qualify(self):
        undefined = run.prior.metrics(np.zeros(4, dtype=bool), np.zeros(4), np.zeros(4))
        self.assertFalse(run.gate(undefined, undefined)['passes_frozen_gate'])


if __name__ == '__main__': unittest.main()
