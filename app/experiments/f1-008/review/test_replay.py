import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('audit008',Path(__file__).with_name('check.py'))
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class ReplayTests(unittest.TestCase):
    def test_roundoff_without_decision_change(self):
        self.assertGreater(audit.verify_replay([.123],[np.nextafter(.123,1.)]),0)

    def test_roundoff_crossing_frozen_threshold_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([.6],[np.nextafter(.6,1.)])

    def test_changed_probability_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([.123],[.1230000001])

    def test_invalid_probability_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([.123],[np.nan])


if __name__=='__main__':unittest.main()
