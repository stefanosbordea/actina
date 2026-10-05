# Original model inspection

The native LightGBM model embedded in Stefanos's saved file reproduces all 3,567 retained test forecasts to a maximum absolute difference of 1.14 × 10⁻¹³ W/m². It contains 148 trees and the seven expected input features in the correct order.

Current radiation accounts for 89.86% of training split gain; yesterday's radiation accounts for 9.26%. These two inputs dominate this particular fitted model. Gain measures how its training splits reduced the objective; it does not establish causality or each feature's contribution on unseen weather. Cloud cover's lower gain is not proof it is unhelpful in another model.

`inspect_original_model.py` parses the pickle's native model string without executing the pickle object. It loads that string with LightGBM and compares every test prediction. Source and evaluator hashes are in `report.json`; individual feature values are in `feature-importance.csv`.

From the repository root, in the experiment's recorded Python environment:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 python3 app/tools/inspect_original_model.py --output app/build/original-model-inspection-check
```

The destination must not already exist. This check does not modify the model or original forecasts.
