import unittest

import numpy as np

from model.sites import sites_day


class SitesTests(unittest.TestCase):
    def test_irrigation_units_and_water_balance(self):
        r = sites_day(5)
        i = r['irrigation']
        self.assertAlmostEqual(i['net_need_mm'], 3.5)
        self.assertAlmostEqual(i['recommended_m3'], 3.5/0.85*5)
        self.assertEqual(i['timer_m3'], 30)
        self.assertAlmostEqual(i['water_difference_m3'], 30-i['recommended_m3'])

    def test_rain_and_soil_reduce_need_without_negative_water(self):
        self.assertEqual(sites_day(5, precipitation_mm=10)['irrigation']['recommended_m3'], 0)
        self.assertEqual(sites_day(5, soil_available_mm=4)['irrigation']['recommended_m3'], 0)
        self.assertGreater(sites_day(20)['irrigation']['recommended_m3'], 30)
        self.assertLess(sites_day(20)['irrigation']['water_difference_m3'], 0)

    def test_no_leak_control_and_injected_detection(self):
        normal = sites_day(5, inject_leak=False)
        leaked = sites_day(5, inject_leak=True)
        self.assertEqual(normal['detector']['alerts'], normal['detector']['no_leak_false_alarms'])
        self.assertEqual(normal['detector']['injected_leak_hours'], 0)
        self.assertEqual(leaked['detector']['injected_leak_hours'], 4)
        self.assertEqual(leaked['detector']['detected_injected_hours'], 4)
        self.assertAlmostEqual(leaked['detector']['synthetic_leak_volume_m3'], 1.2)
        np.testing.assert_allclose(normal['meter_frame'].normal_flow_m3_hour, leaked['meter_frame'].normal_flow_m3_hour)
        self.assertEqual(leaked['detector']['no_leak_false_alarms'], normal['detector']['alerts'])
        # One deterministic fixture is not a field false-alarm guarantee.
        self.assertLessEqual(normal['detector']['alerts'], 1)

    def test_multiple_normal_controls_and_injected_leaks(self):
        for seed in range(10):
            with self.subTest(seed=seed):
                r = sites_day(5, seed=seed)
                self.assertEqual(r['detector']['detected_injected_hours'], 4)
                self.assertEqual(r['detector']['scope'], 'synthetic meter fixture')

    def test_zero_timer_has_no_divide_by_zero(self):
        r = sites_day(5, timer_depth_mm=0)
        self.assertIsNone(r['irrigation']['water_difference_pct'])
        self.assertLess(r['irrigation']['water_difference_m3'], 0)

    def test_invalid_inputs(self):
        for kwargs in (dict(eto_mm=-1), dict(eto_mm=np.nan), dict(eto_mm=True),
                       dict(eto_mm=5, area_m2=0), dict(eto_mm=5, irrigation_efficiency=0),
                       dict(eto_mm=5, crop_coefficient=2), dict(eto_mm=5, seed=-1)):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                sites_day(**kwargs)


if __name__ == '__main__':
    unittest.main()
