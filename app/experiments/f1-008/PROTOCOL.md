# Two-source forecast corrections

Freeze this protocol and all input hashes before fitting or scoring the new GFS input. Experiment 007 reduced misses but increased false alarms. Test whether additional forecast information and separate confidence thresholds for the two correction directions resolve that failure. This is an exploratory extension on an already inspected historical test, not a new independent holdout.

## Inputs and controls

Retain experiment 006's 17,832 origins, fixed UTC+03 clock, +24-hour targets, 24 features, 24-hour purged training memberships, original 3,566 validation and 3,567 test hours, and exact satellite missingness. Add only three features: GFS day2 radiation, GFS minus ECMWF radiation, and the absolute difference. They describe disagreement, not calibrated uncertainty. Use the complete radiation-only join from `nwp-alternative-001`; its rejected cloud field is entirely excluded. Both archives' original publication times and historical operational availability remain unverified.

Use only the larger configuration already fixed in 006/007: 300 trees, 15 leaves, depth 4, minimum leaf size 40, learning rate 0.03, L2 2, seed 17, deterministic column-wise mode, two threads. Fit one weather-only binary classifier and one consensus cross-entropy regressor per period: four fits total. The consensus target is exactly 007's mean binary weather/satellite event, falling back to weather alone when satellite is missing. No new label or hyperparameter search.

Matched no-GFS arms reuse the saved larger weather and consensus probabilities from 006/007. Apply the identical new decision policy to all four arms. Retain original, persistence and raw ECMWF controls. Also report raw GFS and the fixed arithmetic mean of ECMWF/GFS as unselected diagnostic baselines; no tuning or post-test substitution.

## Decision policy and selection

The physical event remains reference radiation strictly greater than 600 W/m². Let `b` be raw ECMWF's event and `p` the learned score. The corrected event is `(b and p > lower) or (not b and p > upper)`. Search the fixed 121 pairs: lower in {0, .05, …, .50}, upper in {.50, .55, …, 1}. Thus additions need stronger confidence than removals; raw ECMWF remains an explicit candidate regardless of exact endpoint probabilities.

A pair is eligible only when precision, recall and F1 are each at least ECMWF's on both weather-full and satellite-common validation. Compare exact count fractions. Rank eligible pairs by minimum F1 across the two references, mean F1, minimum precision, minimum recall, fewer changed ECMWF decisions, larger upper threshold, then smaller lower threshold. If no pair strictly improves any of the six metrics, select the raw control for that arm. Retain the complete grid, including failures.

Choose one augmented arm using the same metric rank, then fewer changed decisions, then weather-only on a tie. Freeze all four arm policies and the chosen augmented arm before generating test predictions. Keep matched no-GFS arms separately; they are ablations, not additional post-test winners.

## Fixed evaluation

Perform one test pass. Preserve all probabilities, decisions, weights, source hashes and model files. Report all arms on weather-full, weather-common and satellite-common, with exact counts, precision, recall, F1, Brier scores for the learned scores, and number/direction of corrections. The final decision policy has no invented probability calibration claim. Report point MAE/RMSE only for actual irradiance baselines.

The frozen selected augmented policy passes the retrospective comparison only if none of the six test metrics regresses and at least one improves. Report separately whether every metric strictly improves. Also compare it to its matched no-GFS arm to distinguish extra information from a new decision rule. Equality is not improvement. A failed result stays out of the application and competition claims. Neither a pass nor a fail establishes physical ground truth, live curtailment, water savings, statistical significance or a new scientific discovery.

## Academic basis

[Gneiting, Lerch and Schulz (2023), full PDF](https://publikationen.bibliothek.kit.edu/1000155949/150349405), printed pp. 73–76, §§2–4: distinguish physical forecast inputs, statistical post-processing and verification. Their Table 2 evaluates neural distribution forecasts against analogue ensembles on seven US stations; that result motivates testing useful forecast information, but does not transfer their measured gains to Cyprus. The present event learner is not a reproduction of their BQN architecture.

[Schulz et al. (2021), full PDF](https://arxiv.org/pdf/2101.06717), PDF pp. 6–11, §§3.1–3.4: predictive location and spread may depend on identifiable forecast members, with proper-score fitting. §4.2 and the conclusion show that improved distribution calibration need not improve point forecasts. Our GFS/ECMWF disagreement is a feature, not an ensemble with proven dispersion calibration. Separate correction thresholds are our engineering hypothesis, not a theorem from either paper or a claimed invention.

No original `model/`, `data/`, `eval/`, product UI or delivery-pack changes. Only this experiment's new paths may be written by the runner. Refuse existing output directories and altered input hashes. Retain failed executions. Use independent reconstruction and saved-model replay before committing conclusions.
