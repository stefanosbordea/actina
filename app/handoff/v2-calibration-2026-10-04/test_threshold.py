import unittest

from threshold import event_counts, scan, select


class ThresholdTests(unittest.TestCase):
    def test_strict_truth_and_prediction_boundaries(self):
        rows = scan([600, 601, 600, 601], [600, 600, 601, 601])
        edge = next(row for row in rows if row['threshold_w_m2'] == 600)
        self.assertEqual([edge[k] for k in ('tp', 'fp', 'fn', 'tn')], [1, 1, 1, 1])
        self.assertEqual(edge['f1_exact'], '1/2')
        self.assertEqual(len(rows), 151)
        self.assertEqual([rows[0]['threshold_w_m2'], rows[-1]['threshold_w_m2']], [500, 650])

    def test_grid_tie_prefers_nearest_600_then_higher(self):
        self.assertEqual(select(scan([700, 0], [700, 0]))['threshold_w_m2'], 600)
        tied = [dict(threshold_w_m2=t, f1_exact='2/3') for t in (590, 599, 601, 610)]
        self.assertEqual(select(tied)['threshold_w_m2'], 601)
        tied.append(dict(threshold_w_m2=500, f1_exact='667/1000'))
        self.assertEqual(select(tied)['threshold_w_m2'], 500)

    def test_exact_ranking_does_not_round_close_ratios(self):
        rows = [dict(threshold_w_m2=600, f1_exact='999999999999999999/1000000000000000000'),
                dict(threshold_w_m2=650, f1_exact='1')]
        self.assertEqual(select(rows)['threshold_w_m2'], 650)

    def test_undefined_and_unpaired_inputs_fail_closed(self):
        with self.assertRaises(ValueError):
            select(scan([0], [0]))
        with self.assertRaises(ValueError):
            event_counts([True], [])


if __name__ == '__main__':
    unittest.main()
