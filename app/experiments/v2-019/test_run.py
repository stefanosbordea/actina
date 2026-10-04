import json
from pathlib import Path
import tempfile
import unittest
import numpy as np
import pandas as pd
import run


class FixedLogisticTests(unittest.TestCase):
    def test_fixed_parameters_and_no_scaler(self):
        model = run.h.head_model("logistic")
        self.assertEqual(model.C, 1)
        self.assertEqual(model.solver, "lbfgs")
        self.assertEqual(model.max_iter, 1000)
        self.assertEqual(model.tol, 1e-8)
        self.assertIsNone(model.class_weight)

    def test_serialized_coefficients_replay_real_estimator(self):
        x = pd.DataFrame({"v2_margin": [-3., -2., -1., 0., 1., 2., 3., 4.]})
        y = np.array([False, False, False, False, True, True, True, True])
        model = run.h.fit_head("logistic", x, y)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            run.save_model(model, x.columns, path)
            saved = json.loads(path.read_text())
        scores = x.to_numpy() @ np.array(saved["coefficients"]) + saved["intercept"]
        replay = 1 / (1 + np.exp(-scores))
        np.testing.assert_allclose(replay, model.predict_proba(x)[:, 1], rtol=0, atol=1e-15)
        self.assertEqual(saved["features"], ["v2_margin"])

    def test_training_fp_cap_unchanged(self):
        chosen, grid = run.m.select(np.array([True, True, False, False]),
            np.array([.9, .7, .8, .1]), np.array([True, False, False, False]))
        self.assertEqual(len(grid), 181)
        self.assertEqual(chosen["fp"], 0)


if __name__ == "__main__":
    unittest.main()
