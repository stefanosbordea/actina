# Bernstein quantile network 009

Frozen before new fitting or scores. Implement a small CPU adaptation of Bernstein quantile networks: ordered Bernstein coefficients, separate quantile losses and no crossing by construction. Credit Bremnes (2020), and Mayer et al., arXiv:2508.15508, §3.2.3; their Hungarian PV results do not imply Cyprus irradiance skill. This hypothesis follows already-inspected results and is not a fresh holdout or novelty claim.

## Fixed model and objective

Use all 27 unchanged features from experiment 008 and its exact original target rows. Each split fits feature means using nonmissing TRAIN values only, imputes missing values with those means, then divides by TRAIN population standard deviation after imputation. Zero standard deviations become 1; an entirely absent training column is an error. No indicators or other features are added. Preserve scaler values and missing counts.

One architecture only: 27 inputs, one tanh hidden layer of width 16, 13 linear outputs, Bernstein degree 12. Internal irradiance units are W/m² divided by the fixed constant 1000. The location is raw ECMWF/1000 plus output z0. Outputs z1..z12 yield positive increments softplus(zj); their cumulative sums c0=0,cj=sum(increments1..j) are centered by their Bernstein value at tau=.5. Coefficient aj = location + cj - sum(Bj,12(.5)*cj). Quantiles are max(0,sum(aj*Bj,12(tau))). This retains ECMWF as a location skip, enforces ordered coefficients and adds a zero atom through lower censoring. No upper or clear-sky cap.

Seed 17 independently for each fit. W1 is normal with standard deviation 1/sqrt(27); both hidden biases and W2 start at zero. Location bias starts at zero; every increment bias is inverse-softplus(0.1/12), giving a 100 W/m² total initial coefficient range. All arrays float64. L2 is 0.5e-6 times the sum of squared W1 and W2 entries; no bias penalty.

Fixed 51 levels tau=k/52, k=1..51. Minimize mean row/level pinball loss. Weather arm uses the weather reference. Joint arm averages the TWO separate reference losses with weights .5/.5 where satellite exists; missing satellite uses weather loss with weight1. Never average irradiance before applying the nonlinear loss. Every row has unit aggregate weight. References need not be independent or equally accurate; this learns their mixture, not latent truth. Use explicit gradients, a zero subgradient at exact pinball equality and zero censor derivative at uncensored quantile<=0.

Optimize with installed SciPy L-BFGS-B: maximum200 iterations, maximum1000 evaluations, maxls40, ftol1e-10, gtol1e-6, two CPU threads. Keep the returned finite iterate and complete convergence status even if the iteration budget or line search stops; no restart or optimizer/architecture/seed search. Four fits only: two arms × validation/test. Test fitting uses exactly the corresponding purged TRAIN targets strictly before the first test origin, matching 008. No outcome-driven revisions.

## Predictions and decision policy

Save coefficients, weights, scalers and every quantile. Median evaluates tau=.5. Distribution mean integrates the censored Bernstein polynomial analytically with incomplete beta functions above its zero crossing; clamp only a negative rounding residue within1e-12 internal units to zero, otherwise fail. Event probability P(Y>600) uses monotone bisection of the uncensored polynomial at0.6 for60 iterations, including endpoint/degenerate handling. Censoring at zero does not alter this positive-threshold event. Keep the zero-atom mass, .05/.95 interval, mean and median.

Apply exactly 008's121 decision pairs: lower0..0.50 step.05 and upper.50..1 step.05. Policy is (ECMWF positive and p>lower) or (ECMWF negative and p>upper). Require no regression of P/R/F1 on BOTH weather-full and satellite-common validation and at least one strict gain; otherwise retain ECMWF. Use exact fractions and unchanged008 ranking/ties. Choose one of the two BQN arms with that rank, favor weather on a tie. Freeze policies and selected arm before new test prediction/scoring. No-GFS ablation is outside this bounded experiment.

Retain original, persistence and ECMWF controls, plus experiment008's already-selected frozen augmented policy. Its selection/thresholds remain unchanged. Report both BQN arms including rejected candidates and their default p>.5 decisions. Test admission requires all six P/R/F1 metrics no worse than ECMWF and at least one strict gain. Report all-six-strictly-better separately and compare against the frozen008 policy; a reference or metric tradeoff is not an upgrade.

## Scores, evidence and limits

For both periods, use weather-full, weather-common and satellite-common on identical available-reference hours; keep every missing row. Event counts, P/R/F1, Brier score of raw distribution probabilities and correction counts are retained. Quantile scores: mean51-level pinball and twice that value as a labelled finite-grid CRPS approximation; median MAE; distribution-mean RMSE; .05/.95 interval coverage/width; zero mass and numerical crossing diagnostics. Point controls are explicitly degenerate distributions when scored. Do not invent distribution metrics for008's event-only model.

Before fitting, test explicit gradients by finite differences away from kinks, pinball arithmetic, coefficient/quantile monotonicity, inversion and zero-mass cases. Save checks and input/code identities. Retain training origins, mean/scale, all models/predictions, optimization status and resource measurements. Refuse existing outputs and changed inputs. Replay from saved weights/hashes without fitting; independent review checks quantile probabilities, scores, memberships, policy grids and model replay.

No installation, GPU allocation, new dataset retrieval, original model/data/scheduler/UI/deck changes, future scheduling or implied operational publication availability. It remains a retrospective adaptation on estimates rather than local ground measurements, with no calibration, live superiority, physical-curtailment or savings claim.

Source: https://arxiv.org/pdf/2508.15508 (Bernstein construction §3.2.3; implementation §4.1; comparative results Table3).
