# 016: Context corrections built on Stefanos's v2 model

This bounded experiment retains Stefanos's nine input features and LightGBM regression configuration from commit `85097a560769ad8a1459ce55f0b3a4c301202405`. The supplied pipeline includes **two NWP features**, `nwp_radiation` and `nwp_cloud`, shifted 24 rows toward the target. `metric=l1` selects the evaluation metric. The regression objective remains LightGBM's default squared-error objective.

The extension learns event decisions from the v2 model's predictions and forecast context. It is not 008 under another name. No GFS, satellite labels, 008 probabilities or 008 training code enter these fits. The point radiation curve stays unchanged by the correction.

## Fixed data and chronology

Capture the source once with `prepare.py`. Preserve the original source hashes and training code. Training contains 16,444 origins from 2024-01-18 15:00 through 2025-12-03 18:00. The validation feature file contains the original 3,566 origins from 2025-12-04 19:00 through 2026-05-02 08:00, with its target column removed. No test rows are retained. Target labels refer to origin +24h. The naive source clock is preserved, with no new timezone interpretation.

Base out-of-fold periods start on 2024-07-01, 2024-10-01, 2025-01-01, 2025-04-01, 2025-07-01 and 2025-10-01. Each runs until the next boundary, with the last ending at the training cutoff. An outer training row is eligible only if its target timestamp is strictly before the first held origin. For each outer training set, reserve its final 28 days for internal early stopping. Inner fitting rows must also have their targets strictly before the first inner stopping origin. Fit up to 1,000 trees at learning rate 0.05, evaluation metric L1 and early stopping 50. Refit the entire eligible outer training set at the selected tree count. Save actual memberships and tree counts.

Fit the final base model through the original v2 training cutoff using the same training-only inner stopping procedure. This is a chronology-safe refit of Stefanos's configuration, not a reproduction claim for his saved predictions. His original training used the now-reused validation set for early stopping. Keep his supplied predictions as a separate comparator.

## Two fixed correction heads

Both use eight features: `(base_prediction-600)/100`, `(nwp_radiation-base_prediction)/100`, `nwp_cloud/100`, the product of the first and third features, sine and cosine of the original hour, and sine and cosine of the original month. Hour uses a 24-hour cycle and month a 12-month cycle beginning at month one. These contextual features can change event ranking, unlike a scalar monotone calibration.

The linear head is logistic regression with C=1, L2 regularization, LBFGS, tolerance 1e-8, 1,000 iterations and no class weighting. The nonlinear head is a binary LightGBM classifier with 150 trees, learning rate 0.03, depth 3, seven leaves, minimum leaf size 100 and L2=10. It has no early stopping or hyperparameter search. Both heads use only out-of-fold base predictions, never in-sample base predictions.

For head forward validation, hold each of base folds three through six in order. Train the head on earlier OOF rows whose targets are strictly before the held origin. Abort if any head fit has a single class. Save every forward head score. Independently for each head, choose its event threshold from integer ticks 10 through 190 divided by 200. The rule is strict probability > threshold. Maximize exact count-based F1 over pooled forward head predictions, then prefer the tick closest to 100, then the higher tick. This selection uses training-period outcomes only. Preserve all 181 candidates per head. Refit each head on all base OOF rows once its threshold is selected.

## Validation, controls and uncertainty

Save the final models, validation probabilities, decisions and a policy freeze before parsing validation outcomes. Then score once on the exact original 3,566 validation targets. Compare both corrections with the matched base model at >600, supplied v2 at >600 and its already selected >562, supplied NWP day1 at >600, retained pinned ECMWF day2 at >600, persistence, and frozen 008 event bits. These raw NWP sources are distinct and are not substituted for each other.

Retain TP, FP, FN, TN, precision, recall and exact F1 for every method. Report MAE, RMSE and bias only for genuine radiation predictions. The corrected event heads retain their base model's radiation errors without implying regression improvement. Report Brier score and binary log loss for the two probability heads. Do not infer calibration from the model family.

After all decisions are fixed, use 2,000 paired daily-block bootstrap samples with seed 16016. Sample observed target dates with replacement and use the same date multiplicities for every method. Report 2.5% and 97.5% quantiles of F1 differences against the matched base, supplied v2 thresholds and frozen 008. Include undefined replicate counts. These intervals describe variation across these historical days. They do not correct validation-selection bias or authenticate issuance times.

Report whether each head exceeds all three retained validation F1 values for supplied v2 at 600, supplied v2 at 562 and 008. Also report the full precision/recall tradeoff and its gain against its own base model. No automatic demo promotion or follow-up tuning is permitted in this run. A negative result remains in place.

## Reproduction and resources

Use existing project Python and dependencies. Set BLAS, OpenMP and LightGBM threads to at most two. Fit serially. Cap the run at 1,800 seconds and refuse any existing output directory. Freeze source and input hashes before fitting. Save environment versions, stdout, exit status, wall/CPU time, model files and output hashes. No original model, data, eval, UI or delivery files change.

## Primary-paper basis and limits

[Wolpert (1992), Stacked Generalization](https://cafri-labs.github.io/lab-manual/papers/wolpert1992.pdf), printed pp. 242–244 and Figures 1–2, trains a second learner on held-out predictions from an underlying learner. That supports using OOF v2 predictions, including a single underlying model. The chronological purge and the specified logistic/boosted heads are engineering choices for this data. The paper does not guarantee an improvement here.

[Lipton, Elkan and Narayanaswamy (2014)](https://arxiv.org/pdf/1402.1892), PDF pp. 7–8, Theorem 1 and Corollary 1, explain the dependence of F1 decisions on the score distribution. The F1/2 result assumes calibrated conditional probabilities. We do not assume that property and instead freeze a finite training-only threshold grid. This is standard event post-processing, not a claimed new algorithm.

The validation period, 008 and supplied v2 have already been inspected and used in previous research. This is an exploratory comparison, not fresh holdout evidence. Reproducibility across LightGBM versions is unverified. The unpinned source NWP request and its historical publication timing retain their existing provenance limitations.
