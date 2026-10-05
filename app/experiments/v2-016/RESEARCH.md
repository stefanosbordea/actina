# Research basis for a direct v2 extension

Reviewed on 4 October 2026. The sources below were opened as primary PDFs and their method sections inspected. This note proposes an engineering adaptation. It does not report a model fit or establish a new algorithm.

## Connection to Stefanos's model

The starting point is Stefanos's `model/train_modelv2.py` at commit `85097a560769ad8a1459ce55f0b3a4c301202405`. [The retained source copy](../../handoff/v2-validation-2026-10-04/inputs/train_modelv2.py) reads `featuresv2.csv`, fits an `LGBMRegressor` with 1,000 candidate trees and learning rate 0.05, uses validation MAE for early stopping, and clips predicted radiation below zero. `metric='l1'` specifies the evaluation metric. The script does not explicitly set an L1 training objective.

The proposed extension keeps that model configuration and feature schema. A small context correction consumes its predictions, rather than replacing them with the unrelated 008 model. The reviewed plan compares a logistic event head with a bounded shallow LightGBM event head. Both use eight fixed inputs: the prediction's distance from 600, NWP disagreement with the prediction, NWP cloud, the margin–cloud interaction, and sine/cosine hour and month. They predict the event `actual > 600`. The supplied radiation curve remains a separate output.

To train the correction, base predictions must come from expanding chronological folds. Each fold trains only where the target time precedes its held origin. Early stopping must use an inner chronological interval with the same target-time purge. The event head then uses earlier out-of-fold rows under the same availability rule. Otherwise, in-sample base predictions give the correction an unrealistically easy training problem. This is our design recommendation, not a validation guarantee from the papers.

The train-only stopping procedure differs from Stefanos's supplied validation stopping. Its final anchor must therefore be called a refit of his configuration, not an exact reproduction of the received v2 predictions. Keep both as controls and report the head against its own anchor.

## Three relevant papers

**Duan et al. (2020), NGBoost: Natural Gradient Boosting for Probabilistic Prediction.** [Primary PDF](https://proceedings.mlr.press/v119/duan20a/duan20a.pdf), §§3.1–3.4. The method learns conditional distribution parameters by boosting natural gradients of a proper scoring rule. It separates distribution choice, scoring rule and base learner. This supports evaluating uncertainty with log loss or Brier score alongside event decisions. A logistic correction attached to v2 is not an NGBoost implementation. The paper does not establish improved F1 on our solar data.

**Henzi, Ziegel and Gneiting (2021), Isotonic Distributional Regression.** [Primary PDF](https://arxiv.org/pdf/1909.03725), §§2.2–2.3 and §5. The method fits conditional distributions under order constraints. Binary isotonic regression is a special case, with the pool-adjacent-violators solution under a total order. The stated calibration result concerns the empirical training distribution. Their precipitation results motivate calibration as a benchmark, not a solar-performance guarantee. A monotone transform of one radiation score cannot reorder hours. Its thresholded calls remain single-cutoff decisions, although a continuous cutoff may differ from the earlier integer grid. Context is needed to change that ranking.

**Mayer et al. (2025), Post-processing of ensemble photovoltaic power forecasts with distributional and quantile regression methods.** [Primary PDF](https://arxiv.org/pdf/2508.15508), §§3.1–3.2 and §5. The study compares censored distributional models and linear or neural quantile methods. Nonlinear quantile models perform best in their application. Its inputs are 51-member forecasts and several years of measured power from seven Hungarian plants. Our deterministic radiation forecasts and smaller dataset differ. The paper supports testing conditional corrections, but does not justify assuming a large neural model will outperform a small correction here.

## What the comparison needs to show

Retain fixed v2, its earlier 562 threshold, the refitted anchor without the head, supplied raw weather, earlier ECMWF day2 and saved 008 calls. Freeze the correction and threshold selection before external validation scoring. Keep exact hour identities, inner and outer cutoffs, tree counts and model artifacts. Report precision, recall, F1, confusion counts and probability diagnostics without hiding regressions.

The validation period has already been inspected across earlier work. A new protocol freeze cannot turn it into a fresh holdout. No result here authorizes a demo replacement solely because its validation F1 is higher. Test-file scoring and model promotion remain separate decisions.
