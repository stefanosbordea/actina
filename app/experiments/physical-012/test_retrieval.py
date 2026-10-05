import importlib.util
from pathlib import Path
import unittest
import numpy as np
import pandas as pd
from retrieval import descriptor, distances, choose, eligible_pool

spec = importlib.util.spec_from_file_location('physical011_optimizer', Path(__file__).resolve().parent.parent / 'physical-011/optimizer.py')
optimizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimizer)


class RetrievalFixtures(unittest.TestCase):
    def test_analytical_supply_timing(self):
        zero = np.zeros(24)
        early = zero.copy()
        late = zero.copy()
        early[0] = late[-1] = 200.
        d = lambda a, b: distances(descriptor(a)[None, :], descriptor(b))[0]
        self.assertEqual(d(early, early), 0.)
        self.assertEqual(d(early, zero), 100.)
        self.assertAlmostEqual(d(late, zero), 25 / 6, places=12)
        self.assertAlmostEqual(d(early, late), 575 / 6, places=12)
        self.assertEqual(d(np.full(24, 1000.), np.full(24, 2000.)), 0.)
        self.assertEqual(d(np.full(24, -1.), zero), 0.)

    def test_left_to_right_and_common_demand(self):
        ghi = np.array([1.e-12, 900., 7., 4., 1.e-8, 320.] * 4)
        expected, total = [], 0.
        for v in ghi:
            total += min(1700., 1.7 * max(float(v), 0.))
            expected.append(total / 3.4)
        np.testing.assert_array_equal(descriptor(ghi), expected)
        a, b = descriptor(ghi), descriptor(ghi[::-1])
        demand = np.arange(1, 25) * 120.
        self.assertAlmostEqual(distances(a[None, :], b)[0], distances((a-demand)[None, :], b-demand)[0], places=10)

    def test_exact_ties_and_chronological_canonical_order(self):
        days = [str(d.date()) for d in pd.date_range('2024-01-01', periods=65)][::-1]
        selected, rank = choose(days, np.zeros(65))
        self.assertEqual([days[i] for i in selected], sorted(days)[:64])
        self.assertEqual(rank[0], 65)
        values = np.zeros(65)
        values[-1] = np.nextafter(0., 1.)
        selected, rank = choose(days, values)
        self.assertNotIn(64, selected)
        self.assertEqual(rank[-1], 65)
        with self.assertRaises(ValueError):
            choose(days[:63], np.zeros(63))
        with self.assertRaises(ValueError):
            choose(['same'] * 64, np.zeros(64))

    def test_strictly_past_full_paired_pool(self):
        target = pd.date_range('2024-01-01', periods=72*24, freq='h')
        nwp, weather, satellite = [np.ones(len(target)) for _ in range(3)]
        nwp[24] = np.nan
        weather[2*24] = np.inf
        satellite[3*24] = np.nan
        keep = np.arange(len(target)) != 4*24+5
        cutoff = target[70*24]
        days, positions, ledger = eligible_pool(target[keep], nwp[keep], weather[keep], satellite[keep], cutoff)
        self.assertEqual(len(days), 66)
        self.assertTrue((target[keep][positions.reshape(-1)] < cutoff).all())
        self.assertEqual([r['day'] for r in ledger if not r['eligible']], ['2024-01-02', '2024-01-03', '2024-01-04', '2024-01-05', '2024-03-11', '2024-03-12'])
        self.assertNotIn('2024-03-11', days)
        with self.assertRaises(ValueError):
            eligible_pool(target[keep], nwp[keep], weather[keep], satellite[keep], target[60*24])

    def test_duplicate_and_invalid_rejection(self):
        target = pd.date_range('2024-01-01', periods=70*24, freq='h')
        values = np.ones(len(target))
        duplicate = target.to_numpy().copy()
        duplicate[10] = duplicate[9]
        with self.assertRaises(ValueError):
            eligible_pool(duplicate, values, values, values, target[-1])
        for value in (np.zeros(23), np.full(24, np.nan), np.full(24, np.inf)):
            with self.assertRaises(ValueError):
                descriptor(value)
        with self.assertRaises(ValueError):
            distances(np.zeros((3, 24)), np.full(24, np.inf))

    def test_same_marginals_same_expected_cost_different_tail(self):
        solar = np.full((2, 64, 24), 408.)
        solar[:, :32, :2] = 0.
        permutation = np.tile(np.arange(64), (24, 1))
        permutation[1] = np.roll(permutation[1], 32)
        changed = optimizer.shuffled(solar, permutation)
        np.testing.assert_array_equal(np.sort(solar, axis=1), np.sort(changed, axis=1))
        q = np.full(24, 120.)
        a = optimizer.evaluate(q, solar)['cost']
        b = optimizer.evaluate(q, changed)['cost']
        np.testing.assert_allclose(a.mean(axis=1), b.mean(axis=1), rtol=0, atol=1.e-10)
        self.assertAlmostEqual(a[0].mean(), 53.04)
        self.assertAlmostEqual(optimizer.cvar(a[0]), 106.08)
        self.assertAlmostEqual(optimizer.cvar(b[0]), 53.04)

    def test_matched_gate_uses_declared_control(self):
        from run import compare, old
        rows = [dict(day=str(day), primary=True, method=method, reference=reference, cost_eur=cost, grid_kwh=cost*10)
            for reference in ('weather', 'satellite') for method, cost in
            (('raw_point', 100.), ('recency_coherent', 95.), ('conditional_coherent', 97.)) for day in range(10)]
        frame = pd.DataFrame(rows)
        self.assertTrue(old.gates(frame, 'conditional_coherent')['all_axis_pass'])
        matched = compare(frame, 'conditional_coherent', 'recency_coherent')
        self.assertFalse(matched['all_axis_pass'])
        self.assertFalse(matched['risk_only_pass'])
        self.assertTrue(all(v['cvar90_daily_regret'] == 2. for v in matched['risk']))
        self.assertTrue(all(v['control'] in (95., 950.) for v in matched['axes']))


if __name__ == '__main__':
    unittest.main()
