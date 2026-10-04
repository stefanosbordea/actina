from fractions import Fraction as F
import time
import unittest
import numpy as np
from decision import events, solve, direct_scores, failures


class ExactDecisions(unittest.TestCase):
    def test_strict_radiation_boundary_and_bad_values(self):
        self.assertEqual(events([-30, 600, np.nextafter(600., np.inf)]).tolist(), [False, False, True])
        for values in ([np.nan], [np.inf]):
            with self.assertRaises(ValueError):
                events(values)

    def test_can_add_and_remove_without_fixed_count(self):
        truth = np.asarray([[[1, 1, 0]], [[1, 1, 0]]])
        for raw in ([1, 0, 0], [1, 1, 1], [0, 0, 0]):
            answer = solve(truth, raw)
            for arm in answer['arms'].values():
                self.assertEqual(arm['decision'], [True, True, False])
                self.assertGreater(arm['objective'], 0)
                self.assertEqual(arm['metrics'], [dict(precision=F(1), recall=F(1), f1=F(1))] * 2)

    def test_empty_and_prohibited_last_removal(self):
        empty = np.zeros((2, 2, 3), dtype=int)
        self.assertEqual(direct_scores(empty, [0, 0, 0]),
                         [dict(precision=None, recall=None, f1=F(1))] * 2)
        for raw in ([0, 0, 0], [1, 0, 0]):
            for arm in solve(empty, raw)['arms'].values():
                self.assertEqual(arm['decision'], [bool(v) for v in raw])
                self.assertEqual(arm['objective'], 0)
        mixed = np.asarray([[[0, 0], [1, 0]], [[0, 0], [1, 0]]])
        scores = direct_scores(mixed, [1, 0])
        self.assertEqual(scores[0], dict(precision=F(1, 2), recall=F(1), f1=F(1, 2)))

    def test_dependence_matters_with_identical_marginals(self):
        a = np.asarray([[[0, 0], [1, 1]]] * 2)
        b = np.asarray([[[1, 0], [0, 1]]] * 2)
        np.testing.assert_array_equal(a.mean(axis=1), b.mean(axis=1))
        self.assertEqual(direct_scores(a, [1, 0])[0]['f1'], F(1, 3))
        self.assertEqual(direct_scores(b, [1, 0])[0]['f1'], F(1, 2))

    def test_exact_safeguards_reject_sub_float_violation(self):
        previous = [dict(precision=F(1, 2), recall=F(1), f1=F(1, 2))] * 2
        candidate = [dict(v) for v in previous]
        candidate[0]['precision'] -= F(1, 10**40)
        self.assertEqual(float(candidate[0]['precision']), float(previous[0]['precision']))
        self.assertIn('0/precision', failures(candidate, previous, 1, 1))

    def test_permutation_repeatability_and_conflicting_references(self):
        y = np.asarray([[[1, 0, 1], [1, 1, 0], [0, 0, 0]],
                        [[0, 1, 0], [1, 0, 1], [0, 0, 0]]])
        answer = solve(y, [1, 0, 0])
        self.assertEqual(answer, solve(y, [1, 0, 0]))
        self.assertEqual(answer, solve(y[:, [2, 0, 1]], [1, 0, 0]))
        for arm in answer['arms'].values():
            self.assertFalse(failures(arm['metrics'], answer['raw_metrics'], arm['positive_calls'], 1))

    def test_daily_improvement_does_not_imply_pooled_precision(self):
        score = lambda tp, fp, fn: (F(tp, tp + fp), F(tp, tp + fn), F(2 * tp, 2 * tp + fp + fn))
        before = [(1, 0, 1), (1, 1, 9)]
        after = [(2, 0, 0), (10, 10, 0)]
        for a, b in zip(before, after):
            self.assertTrue(all(v >= u for u, v in zip(score(*a), score(*b))))
        self.assertEqual(score(*map(sum, zip(*before)))[0], F(2, 3))
        self.assertEqual(score(*map(sum, zip(*after)))[0], F(12, 22))
        self.assertLess(F(12, 22), F(2, 3))

    def test_invalid_dimensions_binary_values_and_deadline(self):
        for y, raw in [(np.zeros((1, 2, 3)), [0] * 3),
                       (np.zeros((2, 0, 3)), [0] * 3),
                       (np.zeros((2, 1, 25)), [0] * 25),
                       (np.zeros((2, 1, 3)), [0]),
                       (np.full((2, 1, 3), .5), [0] * 3),
                       (np.zeros((2, 1, 3)), [0, 0, np.nan])]:
            with self.assertRaises(ValueError):
                solve(y, raw)
        with self.assertRaises(TimeoutError):
            solve(np.zeros((2, 1, 3)), [0] * 3, deadline=time.monotonic() - 1)


if __name__ == '__main__':
    unittest.main()
