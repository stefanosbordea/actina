import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('audit009',Path(__file__).with_name('check.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class ReplayTests(unittest.TestCase):
    def test_last_bit_coefficient_and_probability_roundoff(self):
        error=audit.verify_replay([[.123]],[[np.nextafter(.123,1)]],[.123],[np.nextafter(.123,1)])
        self.assertGreater(error,0)

    def test_changed_coefficient_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([[.123]],[[.123+2e-12]],[.123],[.123])

    def test_changed_probability_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([[.123]],[[.123]],[.123],[.123+2e-11])

    def test_crossing_any_frozen_threshold_is_rejected(self):
        for step in range(21):
            threshold=step/20
            with self.subTest(threshold=threshold),self.assertRaises(AssertionError):
                audit.verify_replay([[.123]],[[.123]],[threshold],[np.nextafter(threshold,np.inf)])

    def test_invalid_values_are_rejected(self):
        for coefficient,probability in [(np.nan,.123),(.123,np.nan),(np.inf,.123),(.123,np.inf)]:
            with self.subTest(coefficient=coefficient,probability=probability),self.assertRaises(AssertionError):
                audit.verify_replay([[.123]],[[coefficient]],[.123],[probability])


if __name__=='__main__':unittest.main()
