import importlib.util
import math
from pathlib import Path
import runpy
import unittest

PATH=Path(__file__).with_name('portable.py')
spec=importlib.util.spec_from_file_location('audit010_portable',PATH)
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class PortableTests(unittest.TestCase):
    def test_import_does_not_execute_audit(self):
        loaded=runpy.run_path(str(PATH))
        self.assertEqual(loaded['checks'],0)
        self.assertNotIn('result',loaded)
        self.assertNotIn('pins',loaded)

    def test_roundoff_without_decision_change(self):
        self.assertGreater(audit.verify_replay([.123],[math.nextafter(.123,1)]),0)
        audit.verify_pair_replay([False,True],[.8,.2],[.8,.2],[math.nextafter(.8,1),.2],[math.nextafter(.8,1),.2],'min')

    def test_excessive_probability_error_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([.123],[.123+2e-15])

    def test_default_threshold_crossing_is_rejected(self):
        with self.assertRaises(AssertionError):audit.verify_replay([.5],[math.nextafter(.5,1)])

    def test_invalid_probability_is_rejected(self):
        for value in [math.nan,math.inf,-math.inf]:
            with self.subTest(value=value),self.assertRaises(AssertionError):audit.verify_replay([.123],[value])

    def test_ranked_pair_change_is_rejected_even_without_a_swap(self):
        for arm in ['min','mean']:
            with self.subTest(arm=arm),self.assertRaises(AssertionError):
                audit.verify_pair_replay([False,True,False],[.6,.5,.6],[.6,.5,.6],
                    [.6,.5,math.nextafter(.6,1)],[.6,.5,math.nextafter(.6,1)],arm)

    def test_strict_margin_crossing_is_rejected(self):
        for arm in ['min','mean']:
            with self.subTest(arm=arm),self.assertRaises(AssertionError):
                audit.verify_pair_replay([False,True],[.75,.25],[.75,.25],
                    [math.nextafter(.75,1),.25],[math.nextafter(.75,1),.25],arm)

    def test_no_available_pair_stays_no_action(self):
        for arm in ['min','mean']:
            audit.verify_pair_replay([True,True],[.8,.2],[.8,.2],[.8,.2],[.8,.2],arm)


if __name__=='__main__':unittest.main()
