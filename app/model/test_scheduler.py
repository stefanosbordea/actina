"""Functional scheduling checks; no operational energy or carbon claim."""
import unittest

import numpy as np

from model.scheduler import KWH_PER_M3, schedule_day


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.radiation = np.maximum(0, 900 * np.sin(np.pi * (np.arange(24) - 6) / 12))
        self.temperature = np.full(24, 28.0)

    def run_day(self, **kwargs):
        return schedule_day(self.radiation, self.radiation, self.temperature, **kwargs)

    def assert_audit(self, result):
        f, t = result['frame'], result['totals']
        self.assertEqual(len(f), 24)
        np.testing.assert_allclose(f.storage_start_m3 + f.scheduled_m3 - f.demand_m3, f.storage_m3, atol=1e-6)
        self.assertTrue((f.storage_start_m3 >= t['safety_minimum_m3'] - 1e-6).all())
        self.assertTrue((f.storage_m3 <= t['tank_capacity_m3'] + 1e-6).all())
        self.assertTrue((f.scheduled_m3 <= t['unit_capacity_m3_hour'] + 1e-6).all())
        self.assertTrue((f.scheduled_m3 >= -1e-6).all())
        self.assertAlmostEqual(t['water_produced_m3'], t['water_demand_m3'])
        self.assertAlmostEqual(t['final_storage_m3'], t['initial_storage_m3'])
        self.assertAlmostEqual(t['energy_kwh'], t['baseline_energy_kwh'])
        self.assertAlmostEqual(t['energy_kwh'], t['water_produced_m3'] * KWH_PER_M3)
        self.assertEqual(t['unmet_demand_m3'], 0)
        self.assertEqual(t['safety_violations'], 0)
        self.assertEqual(t['energy_saving_kwh'], 0)
        self.assertEqual(t['co2_saving_kg'], 0)

    def test_matched_output_lower_scenario_cost(self):
        r = self.run_day()
        self.assert_audit(r)
        self.assertGreater(r['totals']['cost_saving_eur'], 0)
        self.assertEqual(r['totals']['water_demand_m3'], 2880)

    def test_no_future_actual_weather_in_decisions(self):
        a = self.run_day()
        b = schedule_day(self.radiation, np.zeros(24), np.full(24, 45.0))
        np.testing.assert_allclose(a['frame'].scheduled_m3, b['frame'].scheduled_m3)
        np.testing.assert_allclose(a['frame'].demand_m3, b['frame'].demand_m3)
        self.assertEqual(b['totals']['scheduled_solar_proxy_share_pct'], 0)
        self.assertGreater(b['totals']['false_positive_forecast_hours'], 0)

    def test_no_solar_does_not_invent_carbon_saving(self):
        r = schedule_day(np.zeros(24), np.zeros(24), self.temperature)
        self.assert_audit(r)
        self.assertIsNone(r['totals']['forecast_surplus_precision_pct'])
        self.assertEqual(r['totals']['conditional_co2_saving_kg'], 0)
        self.assertTrue(any('tariff shift only' in x for x in r['assumptions']))

    def test_threshold_boundary_matches_forecast_contract(self):
        r = schedule_day(np.full(24, 600.0), np.full(24, 600.0), self.temperature)
        self.assertEqual(r['totals']['predicted_surplus_hours'], 24)
        self.assertEqual(r['totals']['actual_surplus_hours'], 24)
        self.assert_audit(r)

    def test_full_utilization_cannot_shift(self):
        r = self.run_day(unit_capacity=120)
        self.assert_audit(r)
        np.testing.assert_allclose(r['frame'].scheduled_m3, 120)
        self.assertAlmostEqual(r['totals']['cost_saving_eur'], 0)

    def test_zero_storage_cannot_shift(self):
        r = self.run_day(tank_capacity=0)
        self.assert_audit(r)
        np.testing.assert_allclose(r['frame'].scheduled_m3, 120)
        self.assertAlmostEqual(r['totals']['cost_saving_eur'], 0)

    def test_tiny_and_large_tanks_remain_bounded(self):
        for capacity in (1, 50, 500, 4000, 12000, 1e6):
            with self.subTest(capacity=capacity):
                self.assert_audit(self.run_day(tank_capacity=capacity))

    def test_overloaded_unit_fails_clearly(self):
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            self.run_day(unit_capacity=119)
        with self.assertRaisesRegex(ValueError, 'infeasible'):
            self.run_day(demand_scale=10)

    def test_unavailable_predictions_fall_back(self):
        for prediction in (None, np.full(24, np.nan), np.r_[np.nan, self.radiation[1:]]):
            r = schedule_day(prediction, self.radiation, self.temperature)
            self.assert_audit(r)
            self.assertTrue(r['status'].startswith('fallback'))
            np.testing.assert_allclose(r['frame'].scheduled_m3, 120)
            self.assertAlmostEqual(r['totals']['cost_saving_eur'], 0)

    def test_declared_demand_scenario(self):
        r = self.run_day(season='winter', forecast_temperature_c=34, demand_scale=2)
        self.assertEqual(r['totals']['demand_m3_hour'], 216)
        self.assert_audit(r)

    def test_conditional_displacement_is_separate(self):
        r = self.run_day(renewable_displacement_share=0.5)
        self.assertGreater(r['totals']['conditional_co2_saving_kg'], 0)
        self.assertEqual(r['totals']['co2_saving_kg'], 0)
        self.assertAlmostEqual(r['totals']['baseline_co2_kg'], r['totals']['schedule_co2_kg'])
        self.assertEqual(self.run_day()['totals']['conditional_co2_saving_kg'], 0)

    def test_reject_invalid_inputs(self):
        cases = [dict(tank_capacity=-1), dict(unit_capacity=0), dict(threshold=-1),
                 dict(demand_scale=0), dict(demand_scale=np.nan), dict(unit_capacity=True),
                 dict(season='unknown'), dict(forecast_temperature_c=100),
                 dict(renewable_displacement_share=1.1)]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.run_day(**kwargs)
        for values in (np.zeros(23), np.full(24, np.inf), np.full(24, -1)):
            with self.subTest(values=str(values)), self.assertRaises(ValueError):
                schedule_day(values, self.radiation, self.temperature)
        with self.assertRaises(ValueError):
            schedule_day(self.radiation, np.full(24, np.nan), self.temperature)


if __name__ == '__main__':
    unittest.main()
