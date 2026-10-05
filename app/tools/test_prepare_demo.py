import hashlib
import json
import math
import unittest
from pathlib import Path
from prepare_demo import ROOT, prepare


class DemoDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = prepare()
        cls.days = {d['date']: d for d in cls.data['days']}

    def test_retained_input_identity_and_complete_days(self):
        self.assertEqual(len(self.days), 296)
        self.assertEqual(sum(len(d['rows']) for d in self.days.values()), 7104)
        self.assertEqual(self.data['source']['csv_sha256'], hashlib.sha256((ROOT / 'eval/schedule_hourly.csv').read_bytes()).hexdigest())
        packaged = (ROOT / 'app/site/data.js').read_text()
        self.assertEqual(json.loads(packaged.removeprefix('window.AKTINA_DATA=').strip().removesuffix(';')), self.data)
        self.assertEqual((ROOT / 'app/site/schedule_hourly.csv').read_bytes(), (ROOT / 'eval/schedule_hourly.csv').read_bytes())

    def test_distinguishes_supplied_forecast_from_model(self):
        self.assertEqual(self.data['source']['schedule_forecast_status'], 'matches_persistence')
        self.assertEqual(self.data['source']['schedule_forecast_matches_baseline'], 7104)
        self.assertEqual(self.data['source']['schedule_forecast_matches_model'], 9)
        rows = self.days['2026-03-16']['rows']
        mae = lambda key: sum(abs(r[key] - r['actual']) for r in rows) / 24
        self.assertAlmostEqual(mae('model_forecast'), 48.47758820873265)
        self.assertAlmostEqual(mae('baseline'), 156.33333333333334)

    def test_summer_costs_and_equal_water(self):
        day = self.days['2026-07-03']
        rows = day['rows']
        cost = lambda key: sum(r[key] * 3.4 / 1000 * (101 if r['actual'] > 600 else 183) for r in rows)
        self.assertAlmostEqual(cost('flat'), 2994.5908)
        self.assertAlmostEqual(cost('aktina'), 2628.2476)
        self.assertAlmostEqual(sum(r['flat'] for r in rows), sum(r['aktina'] for r in rows))
        self.assertAlmostEqual(day['start_tank'], rows[-1]['tank'])
        self.assertEqual(sum(r['actual'] > 600 for r in rows), 8)

    def test_cloudy_day_has_no_discount_and_respects_given_bounds(self):
        rows = self.days['2025-12-10']['rows']
        self.assertEqual(max(r['actual'] for r in rows), 141)
        self.assertEqual(sum(r['actual'] > 600 for r in rows), 0)
        for day in self.days.values():
            for row in day['rows']:
                self.assertGreaterEqual(row['tank'], 800 - 1e-7)
                self.assertLessEqual(row['tank'], 4000 + 1e-7)


if __name__ == '__main__':
    unittest.main()
