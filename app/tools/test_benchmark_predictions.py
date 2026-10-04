import csv
import math
import tempfile
import unittest
from pathlib import Path
from benchmark_predictions import benchmark, metrics, read_rows


class BenchmarkTests(unittest.TestCase):
    def test_strict_threshold_confusion_matrix(self):
        rows = [{'actual': a, 'predicted': p} for a, p in [(700, 800), (700, 500), (500, 700), (600, 600)]]
        r = metrics(rows, 'predicted')
        self.assertEqual([r[k] for k in ('true_positive','false_positive','false_negative','true_negative')], [1,1,1,1])
        self.assertEqual(r['mae_w_m2'], 125)
        self.assertEqual(r['rmse_w_m2'], 150)
        self.assertEqual(r['bias_w_m2'], 25)
        self.assertEqual(r['precision'], .5)
        self.assertEqual(r['recall'], .5)
        self.assertEqual(r['f1'], .5)

    def test_absent_positive_class_is_not_perfect_f1(self):
        r = metrics([{'actual':0, 'predicted':0}], 'predicted')
        self.assertIsNone(r['precision']); self.assertIsNone(r['recall']); self.assertIsNone(r['f1'])

    def test_timestamp_validation_and_target_alignment(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'predictions.csv'
            p.write_text('time,actual,predicted,baseline\n2026-01-01 23:00:00,0,1,0\n2026-01-02 00:00:00,0,0,0\n')
            self.assertEqual(read_rows(p)[0]['target_time'], '2026-01-02 23:00:00')
            p.write_text('time,actual,predicted,baseline\n2026-01-01 23:00:00,0,1,0\n2026-01-01 23:00:00,0,0,0\n')
            with self.assertRaisesRegex(ValueError, 'Nonconsecutive'): read_rows(p)
            p.write_text('time,actual,predicted,baseline\n2026-01-01 23:00:00,0,nan,0\n')
            with self.assertRaisesRegex(ValueError, 'Invalid radiation'): read_rows(p)

    def test_all_rows_retained_and_group_totals_reconcile(self):
        result=benchmark()
        self.assertEqual([s['model']['hours'] for s in result['splits']], [3566,3567])
        for split in result['splits']:
            for method in ('model','persistence'):
                self.assertEqual(sum(d[method]['hours'] for d in split['daily']),split[method]['hours'])
                for count in ('true_positive','false_positive','false_negative','true_negative'):
                    self.assertEqual(sum(d[method][count] for d in split['monthly']),split[method][count])
                weighted=math.fsum(d[method]['mae_w_m2']*d[method]['hours'] for d in split['daily'])/split[method]['hours']
                self.assertAlmostEqual(weighted,split[method]['mae_w_m2'])


if __name__=='__main__': unittest.main()
