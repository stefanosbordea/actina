"""Boundary and failed-correction cases for the frozen experiment."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location('corrections008', Path(__file__).with_name('run.py'))
experiment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(experiment)


class PolicyTests(unittest.TestCase):
    def test_separate_directions_and_strict_boundaries(self):
        baseline = np.array([True, True, False, False])
        probability = np.array([.2, .200001, .8, .800001])
        policy = {'kind': 'correction', 'lower': .2, 'upper': .8}
        self.assertEqual(experiment.decide(baseline, probability, policy).tolist(), [False, True, False, True])

    def test_perfect_control_is_retained_even_with_endpoint_scores(self):
        baseline = np.array([True, False, True, False])
        actual = np.array([700., 0., 700., 0.])
        selected, grid = experiment.select(baseline, np.array([0., 1., .3, .8]), actual, actual)
        self.assertEqual(len(grid), 121)
        self.assertEqual(selected['policy'], {'kind': 'control'})
        np.testing.assert_array_equal(experiment.decide(baseline, np.zeros(4), selected['policy']), baseline)

    def test_corrects_miss_and_false_alarm_on_both_references(self):
        baseline = np.array([True, True, False, False])
        actual = np.array([700., 0., 700., 0.])
        probability = np.array([.9, .1, .9, .1])
        selected, _ = experiment.select(baseline, probability, actual, actual)
        np.testing.assert_array_equal(experiment.decide(baseline, probability, selected['policy']), actual > 600)
        self.assertEqual(selected['changed'], 2)
        self.assertTrue(selected['strict_gain'])

    def test_perfect_satellite_control_rejects_weather_only_gain(self):
        baseline = np.array([True, True, False, False])
        weather = np.array([700., 0., 700., 0.])
        satellite = np.array([700., 700., 0., 0.])
        selected, _ = experiment.select(baseline, np.array([.9, .1, .9, .1]), weather, satellite)
        self.assertEqual(selected['policy']['kind'], 'control')

    def test_missing_satellite_not_relabelled_negative(self):
        result = experiment.metrics(np.array([True, False, True]), np.array([700., 0., 700.]), np.array([700., 0., np.nan]))
        self.assertEqual(result['weather_full']['hours'], 3)
        self.assertEqual(result['satellite_common']['hours'], 2)
        self.assertEqual(result['satellite_common']['tp'], 1)
        self.assertEqual(result['satellite_common']['fn'], 0)
        self.assertEqual(result['weather_common']['hours'], 2)


if __name__ == '__main__': unittest.main()
