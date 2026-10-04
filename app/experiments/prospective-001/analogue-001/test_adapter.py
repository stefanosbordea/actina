"""Analytical rules and retained capture identity; no fitting or truth retrieval."""
import copy
import json
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np
import run


class AdapterRules(unittest.TestCase):
    def test_equal_distances_choose_earlier_origins(self):
        index, distance = run.nearest(np.array([[1.],[-1.],[0.],[1.],[-1.]]),np.array([0.]),3)
        self.assertEqual(index.tolist(),[2,0,1]); self.assertEqual(distance.tolist(),[0,1,1])

    def test_more_than_64_ties(self):
        index, _ = run.nearest(np.ones((100,6)),np.zeros(6))
        self.assertEqual(index.tolist(),list(range(64)))

    def test_probability_exact_half_is_negative(self):
        values=np.array([600.]*32+[601.]*32)
        result=run.scenario_summary(values)
        self.assertEqual(result['probability'],.5)
        self.assertEqual(result['predicted_positive'],0)
        self.assertEqual(result['point_w_m2'],600.5)

    def test_strict_threshold_and_interpolated_interval(self):
        result=run.scenario_summary(np.arange(64.)+580)
        self.assertEqual(result['probability'],43/64)
        self.assertEqual(result['predicted_positive'],1)
        self.assertAlmostEqual(result['interval_low_w_m2'],583.15)
        self.assertAlmostEqual(result['interval_high_w_m2'],639.85)

    def test_deadline_includes_start(self):
        start=datetime(2026,10,5,9,tzinfo=timezone.utc)
        run.require_future(start-timedelta(microseconds=1),start)
        for now in [start,start+timedelta(microseconds=1)]:
            with self.assertRaises(ValueError): run.require_future(now,start)

    def test_utc_required(self):
        for text in ['2026-10-04T08:00:00','2026-10-04T08:00:00+03:00']:
            with self.assertRaises(ValueError): run.utc(text)

    def test_capture_complete_and_value_locked(self):
        pins=json.loads((run.HERE/'input-identities.json').read_text())
        blobs={name:(run.ROOT/name).read_bytes() for name in pins}
        selected, rows=run.verify_capture(blobs)
        self.assertEqual(len(rows),48)
        self.assertEqual([r['target_set'] for r in rows].count('primary'),24)
        path='app/experiments/prospective-001/capture-001/selected-targets.json'
        for field, value in [('shortwave_radiation_w_m2',999),('valid_time_lead_seconds',1),('valid_time_utc',rows[1]['valid_time_utc'])]:
            changed=copy.deepcopy(selected); changed['targets']['primary']['intervals'][0][field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                run.verify_capture({**blobs,path:json.dumps(changed).encode()})


if __name__=='__main__': unittest.main()
