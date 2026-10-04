import io
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from link import POSITIVE, compare, forecast_metrics, optimizer, paired, project, water_exact
from run import HERE, ROOT, references, sha, verify_hashes


class LinkFixtures(unittest.TestCase):
    def test_strict_boundary_and_smallest_representable_projection(self):
        before = np.nextafter(600., -np.inf)
        raw = np.asarray([0., before, 600., POSITIVE, 700., 1000.] * 4)
        calls = np.asarray([1, 1, 1, 0, 0, 1] * 4)
        got = project(raw, calls)
        expected = np.asarray([POSITIVE, POSITIVE, POSITIVE, 600., 600., 1000.] * 4)
        np.testing.assert_array_equal(got, expected)
        np.testing.assert_array_equal(got > 600, calls.astype(bool))
        self.assertEqual(float(POSITIVE).hex(), '0x1.2c00000000001p+9')
        self.assertEqual(float(POSITIVE)-600, 2.**-43)
        self.assertEqual(np.nextafter(POSITIVE, -np.inf), 600.)
        self.assertEqual(raw[4], 700.)

    def test_consistent_raw_is_bitwise_unchanged(self):
        raw = np.asarray([0., 100., 599., 600., POSITIVE, 1200.] * 4)
        got = project(raw, raw > 600)
        self.assertEqual(raw.tobytes(), got.tobytes())
        self.assertFalse(np.shares_memory(raw, got))

    def test_npz_roundtrip_preserves_all_boundary_bits(self):
        raw = np.linspace(0, 1200, 24)
        calls = np.asarray([True, False] * 12)
        mapped = project(raw, calls)
        stream = io.BytesIO()
        np.savez_compressed(stream, mapped=mapped, calls=calls)
        stream.seek(0)
        with np.load(stream, allow_pickle=False) as saved:
            self.assertEqual(mapped.tobytes(), saved['mapped'].tobytes())
            np.testing.assert_array_equal(saved['mapped'] > 600, saved['calls'])

    def test_invalid_mapping_inputs_are_refused(self):
        raw, calls = np.full(24, 500.), np.zeros(24, dtype=bool)
        for bad in (raw[:23], np.full(24, np.nan), np.full(24, np.inf), np.full(24, -1.)):
            with self.assertRaises(ValueError):
                project(bad, calls)
        for bad in (calls[:23], np.full(24, 2), np.zeros(24, dtype=float), np.full(24, 'true')):
            with self.assertRaises(ValueError):
                project(raw, bad)

    def test_fractional_tail_negative_values_and_ties(self):
        self.assertAlmostEqual(optimizer.cvar(np.arange(64.)), (sum(range(58,64))+.4*57)/6.4)
        self.assertEqual(optimizer.cvar(np.full(64,-3.)), -3.)
        self.assertEqual(optimizer.cvar(np.asarray([1.,-1.])), 1.)
        with self.assertRaises(ValueError):
            optimizer.cvar([np.nan])

    def test_analytical_water_solve_and_fixed_plan_bounds(self):
        solar = np.zeros(24)
        solar[10:17] = 1700.
        q, result = optimizer.solve(solar)
        self.assertAlmostEqual(float(q.sum()), 2880., places=6)
        self.assertAlmostEqual(result['water']['total_energy_kwh'], 9792., places=5)
        self.assertLess(float(optimizer.evaluate(q, solar)['cost']), 1e-5)
        again, _ = optimizer.solve(solar)
        np.testing.assert_array_equal(q, again)
        changed = solar.copy()
        changed[[3,12,16]] = [60., 1300., 1699.]
        a, b = optimizer.evaluate(q,solar), optimizer.evaluate(q,changed)
        delta = np.abs(changed-solar)
        self.assertLessEqual(abs(float(a['grid_energy']-b['grid_energy'])), float(delta.sum())+1e-9)
        self.assertLessEqual(abs(float(a['cost']-b['cost'])), float(np.dot(optimizer.PRICE,delta))+1e-9)
        with self.assertRaises(AssertionError):
            optimizer.audit(np.zeros(24))

    def test_exact_water_replay_retains_tiny_residual(self):
        q = np.full(24,120.)
        exact = water_exact(q)
        self.assertEqual(exact['maximum_residual'], '0')
        self.assertEqual(exact['total_water_m3'], '2880')
        self.assertEqual(exact['nominal_energy_kwh'], '9792')
        q[0] = np.nextafter(q[0], np.inf)
        exact = water_exact(q)
        self.assertGreater(Fraction(exact['maximum_residual']), 0)
        self.assertLess(float(Fraction(exact['maximum_residual'])), optimizer.AUDIT_TOL)

    def test_aggregate_gate_cannot_hide_daily_regret(self):
        pairs = {r:{m:([1.,99.],[0.,100.]) for m in ('cost_eur','grid_kwh')} for r in ('weather','satellite')}
        result = compare(pairs)
        self.assertTrue(result['all_axis_pass'])
        self.assertFalse(result['risk_only_pass'])
        self.assertEqual(result['paired_differences']['weather']['cost_eur']['worse'],1)
        self.assertEqual(result['paired_differences']['weather']['cost_eur']['cvar90'],1.)
        self.assertEqual(len(result['axes']),8)

    def test_unchanged_candidate_is_not_an_upgrade(self):
        pairs = {r:{m:([0.,100.],[0.,100.]) for m in ('cost_eur','grid_kwh')} for r in ('weather','satellite')}
        result = compare(pairs)
        self.assertFalse(result['all_axis_pass'])
        self.assertFalse(result['risk_only_pass'])
        self.assertEqual(result['paired_differences']['weather']['cost_eur']['equal'],2)
        pairs['weather']['cost_eur'] = ([-1.,99.],[0.,100.])
        self.assertTrue(compare(pairs)['all_axis_pass'])
        self.assertTrue(compare(pairs)['risk_only_pass'])
        pairs['satellite']['cost_eur'] = ([1.,101.],[0.,100.])
        self.assertFalse(compare(pairs)['all_axis_pass'])
        with self.assertRaises(ValueError):
            compare({'weather':pairs['weather']})
        with self.assertRaises(ValueError):
            paired([1.,2.],[1.])

    def test_event_counts_keep_strict_threshold_and_nulls(self):
        result = forecast_metrics([600.,POSITIVE,700.,500.],[POSITIVE,POSITIVE,600.,500.])
        self.assertEqual([result[k] for k in ('tp','fp','fn','tn')],[1,1,1,1])
        self.assertEqual(result['f1']['numerator'],1)
        self.assertEqual(result['f1']['denominator'],2)
        zero = forecast_metrics([0.,0.],[0.,0.])
        self.assertIsNone(zero['precision'])
        self.assertIsNone(zero['recall'])
        self.assertIsNone(zero['f1'])

    def test_source_hash_change_and_escape_refusal(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            path = Path(directory)/'fixture.txt'
            path.write_text('first\n')
            pins = {str(path.relative_to(ROOT)):sha(path)}
            verify_hashes(pins)
            path.write_text('second\n')
            with self.assertRaises(ValueError):
                verify_hashes(pins)
        with self.assertRaises(ValueError):
            verify_hashes({'../outside':'0'*64})

    def test_reference_missingness_and_all_clocks(self):
        origins = [datetime(2025,1,1,h) for h in (0,1)]
        targets = [v+timedelta(hours=24) for v in origins]
        observed, joined = [], []
        for h,(origin,target) in enumerate(zip(origins,targets)):
            utc = target.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)
            observed.append(dict(feature_time=str(origin),target_time=str(target),actual='700'))
            joined.append(dict(feature_time=str(origin),target_time=str(target),valid_time_utc=utc.isoformat(),
                interval_start_utc=(utc-timedelta(hours=1)).isoformat(),weather_actual_w_m2='700',satellite_w_m2='' if h else '690',is_missing=str(h)))
        with patch('run.rows',side_effect=[observed,joined]):
            weather,satellite = references(origins,targets)
        np.testing.assert_array_equal(weather,[700.,700.])
        self.assertEqual(satellite[0],690.)
        self.assertTrue(np.isnan(satellite[1]))
        for table,key,value in ((1,'is_missing','true'),(1,'is_missing','0'),(0,'feature_time','2020-01-01'),
                                (1,'feature_time','2020-01-01'),(1,'interval_start_utc','2020-01-01T00:00:00+00:00')):
            modified = [deepcopy(observed),deepcopy(joined)]
            modified[table][1][key] = value
            with patch('run.rows',side_effect=modified), self.assertRaises(ValueError):
                references(origins,targets)


if __name__=='__main__':
    unittest.main()
