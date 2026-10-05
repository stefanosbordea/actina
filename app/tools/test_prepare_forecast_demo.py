import csv
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import prepare_forecast_demo as demo


class ForecastPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = demo.prepare()
        cls.rows = [row for day in cls.data['days'] for row in day['rows']]
        cls.metrics = {metric['id']: metric for metric in cls.data['metrics']}

    def test_exact_package_and_all_partial_boundary_hours(self):
        self.assertEqual((demo.ROOT / demo.OUTPUT).read_text(), demo.serialize(self.data))
        self.assertEqual(len(self.rows), 3566)
        self.assertEqual(len(self.data['days']), 150)
        self.assertEqual([r['hour'] for r in self.data['days'][0]['rows']], list(range(19, 24)))
        self.assertEqual([r['hour'] for r in self.data['days'][-1]['rows']], list(range(9)))
        self.assertEqual(self.rows[0]['time'], '2025-12-05 19:00:00')
        self.assertEqual(self.rows[-1]['time'], '2026-05-03 08:00:00')
        for a, b in zip(self.rows, self.rows[1:]):
            self.assertEqual(datetime.fromisoformat(b['time']) - datetime.fromisoformat(a['time']), timedelta(hours=1))

    def test_no_curve_substitution_and_exact_v2_cloud_join(self):
        with (demo.ROOT / demo.SOURCES['incoming']).open() as handle:
            incoming = list(csv.DictReader(handle))
        with (demo.ROOT / demo.FEATURES).open() as handle:
            features = list(csv.DictReader(handle))
        with (demo.ROOT / demo.CORRECTION / 'result/validation-decisions.csv').open() as handle:
            correction = list(csv.DictReader(handle))
        with (demo.ROOT / demo.BASE / 'validation-decisions.csv').open() as handle:
            base = list(csv.DictReader(handle))
        for row, original, feature, corrected, anchor in zip(self.rows, incoming, features, correction, base):
            self.assertEqual(row['v2'], float(original['predicted']))
            self.assertEqual(row['raw_v2'], float(original['forecast']))
            self.assertEqual(row['nwp_cloud'], float(feature['nwp_cloud']))
            self.assertEqual(row['raw_v2'], float(feature['nwp_radiation']))
            self.assertEqual(row['v2_refit'], float(corrected['base_prediction']))
            self.assertAlmostEqual(row['v2_refit'], float(anchor['base_prediction']), places=11)
            self.assertEqual(row['event_019'], int(corrected['expanded_call']))
            self.assertEqual(row['event_019'], float(corrected['expanded_probability']) > .49)
        self.assertTrue(any(r['raw_v2'] != r['ecmwf_day2'] for r in self.rows))
        self.assertTrue(any(r['v2'] != r['raw_v2'] for r in self.rows))
        self.assertTrue(any(r['v2'] != r['v2_refit'] for r in self.rows))

    def test_full_period_confusion_counts_match_retained_evidence(self):
        expected = {
            'v2_600': (262, 25, 44, 3235), 'v2_562': (287, 51, 19, 3209),
            'v1': (241, 55, 65, 3205), 'persistence': (244, 62, 62, 3198),
            'raw_v2': (253, 34, 53, 3226), 'ecmwf_day2': (268, 21, 38, 3239),
            'event_008': (271, 21, 35, 3239),
            'event_019': (270, 17, 36, 3243),
        }
        for name, counts in expected.items():
            metric = self.metrics[name]
            self.assertEqual(tuple(metric[k] for k in ('tp', 'fp', 'fn', 'tn')), counts)
            self.assertEqual(metric['hours'], 3566)
        self.assertEqual(self.metrics['v2_600']['mae_w_m2'], self.metrics['v2_562']['mae_w_m2'])
        self.assertNotIn('mae_w_m2', self.metrics['event_008'])
        self.assertGreater(self.metrics['event_008']['f1'], self.metrics['v2_562']['f1'])
        self.assertLess(self.metrics['v2_562']['precision'], self.metrics['v2_600']['precision'])
        self.assertAlmostEqual(self.metrics['event_019']['mae_w_m2'], 18.700675310908366, places=10)
        self.assertAlmostEqual(self.metrics['v2_600']['mae_w_m2'], 18.69734271860889, places=10)
        self.assertGreater(self.metrics['event_019']['f1'], self.metrics['event_008']['f1'])
        self.assertLess(self.metrics['event_019']['recall'], self.metrics['event_008']['recall'])

    def test_event_boundary_is_strict_and_research_remains_binary(self):
        score = demo.scores([600, 600.01], [True, True])
        self.assertEqual((score['tp'], score['fp']), (1, 1))
        self.assertEqual({row['event_008'] for row in self.rows}, {0, 1})
        self.assertIsNone(self.metrics['event_008']['threshold'])
        self.assertEqual(self.data['source']['research_policy'], {'kind': 'correction', 'lower': .5, 'upper': .6})

    def test_source_tampering_stops_packaging(self):
        real_digest = demo.digest
        for filename in ('cv_predictions_v2.csv', 'review.json', 'completion.json', 'summary.json', 'validation-decisions.csv'):
            with self.subTest(filename=filename), patch.object(demo, 'digest', side_effect=lambda path: '0' * 64 if path.name == filename else real_digest(path)):
                with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                    demo.prepare()

    def test_correction_cannot_be_paired_with_another_curve_or_event_rule(self):
        real_loader = demo.load_rows
        for key, value, message in [('base_prediction', '999', 'curve differs'), ('expanded_call', '1', 'frozen threshold')]:
            def corrupt(path, time_key):
                rows = real_loader(path, time_key)
                if path == demo.ROOT / demo.CORRECTION / 'result/validation-decisions.csv':
                    rows[min(rows)][key] = value
                return rows
            with self.subTest(key=key), patch.object(demo, 'load_rows', side_effect=corrupt):
                with self.assertRaisesRegex(ValueError, message):
                    demo.prepare()

    def test_timestamp_corruption_stops_packaging(self):
        real_loader = demo.load_rows
        def corrupt(path, key):
            rows = real_loader(path, key)
            if path.name == 'validation-nwp_day2.csv':
                first = rows[min(rows)]
                first['target_time'] = '2025-12-05 18:00:00'
            return rows
        with patch.object(demo, 'load_rows', side_effect=corrupt):
            with self.assertRaisesRegex(ValueError, 'Target timestamp mismatch'):
                demo.prepare()

    def test_missing_hour_and_invalid_values_stop_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'missing.csv'
            source.write_text('time,value\n2025-12-04 19:00:00,0\n')
            with self.assertRaisesRegex(ValueError, 'expected 3566'):
                demo.load_rows(source, 'time')
        for value in ('nan', 'inf', '-inf'):
            with self.assertRaises(ValueError):
                demo.number(value)
        with self.assertRaises(ValueError):
            demo.bit('True')


if __name__ == '__main__':
    unittest.main()
