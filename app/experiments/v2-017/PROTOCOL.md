# 017: Additional weather forecasts around the v2 prediction

016 did not beat 008. This experiment tests one specific information change: adding pinned ECMWF day2 and GFS day2 radiation to a correction that explicitly consumes the frozen 016 refit of Stefanos's v2. No base model is retrained, and no original model, data, evaluation or demo file changes.

## Fixed inputs and matched arms

Reuse 016's base out-of-fold predictions and its frozen final validation radiation predictions. Intersect OOF origins with the existing 008 feature table and verified GFS radiation-only table. This preserves 10,675 training OOF origins from 2024-09-15 00:00 through 2025-12-03 18:00, with fold sizes 384, 2208, 2160, 2184, 2208 and 1531. Retain the 1,824 excluded early OOF origins explicitly. Use every original validation origin, 3,566 hours. This is the fixed existing-table coverage choice, not a search for a favorable mask.

Verify every retained ECMWF and GFS value against the raw archive epoch. Target = origin +24h. Interpret the original labels at fixed +03:00 and join to UTC epochs. Do not use seasonal Europe/Nicosia offsets or shift radiation to interval starts. Radiation is a preceding-hour mean ending at its target label. Requests pin `ecmwf_ifs025` and `gfs_global`. GFS cloud is wholly excluded because its prior intake failed range checks. Day1 cloud comes from Stefanos's complete original feature.

Both arms use the same rows, targets, forward folds and fixed binary LightGBM configuration: 150 trees, learning rate .03, depth 3, seven leaves, minimum leaf size 100, L2=10, deterministic column-wise mode, seed 0 and two threads. There is no parameter search or early stopping for the heads.

The matched core arm has eight features: (v2−600)/100, (supplied day1−v2)/100, supplied day1 cloud/100, v2/solar_scale, sine/cosine of target clock hour and sine/cosine of target season. The expanded arm adds only three: (ECMWFday2−v2)/100, (GFSday2−v2)/100 and abs(GFSday2−ECMWFday2)/100.

Reconstruct `solar_scale` with the locked existing geometry function and compare it with the retained feature. The scale is max(100 W/m², 1000 times mean positive solar-zenith cosine over six midpoints in the preceding hour). Its nighttime floor is fixed at 100 and it is an astronomical scaling feature, not a measured or calibrated clear-sky irradiance forecast. Retained cyclic target-season features are inputs known from the calendar, not learned labels.

The core geometry differs from 016. Attribute only the matched expanded-versus-core comparison to the new forecast inputs. Neither arm may use 008 predictions, probabilities, learned model outputs or satellite labels as a feature.

## Chronology and training-only selection

Use OOF folds three through six as forward head holds. Train each head only on earlier common-coverage OOF rows whose target timestamps are strictly before the first held origin. Abort a fit with one class. Save each intermediate fitted head, memberships and probabilities so it can be replayed without refitting.

For each arm, retain the fixed 181 threshold ticks 10..190 divided by 200 with strict probability > threshold. On the same pooled forward training hours, count false positives from the raw ECMWF day2 >600 control. A threshold is eligible only when its false positives do not exceed that control's count. Among eligible thresholds, maximize exact F1, then prefer the tick closest to 100, then the higher tick. If no threshold qualifies, preserve the arm as inadmissible and do not substitute another policy. The other arm still completes. Refit admissible heads once on all 10,675 common OOF rows.

The training false-positive constraint is not a promise about future or validation false positives. It does not use 008 validation counts or any validation outcome for selection.

## Fixed validation and reporting

Freeze final head files, probabilities, selected thresholds and decisions before parsing validation outcome files. Score once on the same original 3,566 validation hours. Include the unchanged 016 v2 refit, supplied v2 at 600 and its previously selected 562, supplied raw day1, retained ECMWF day2, persistence, and fixed 008 bits. Both heads retain the same radiation curve and MAE as the 016 base.

Report confusion counts, precision, recall, exact F1, Brier score, log loss, and readable head feature importance. Retain both arms whether they pass or fail. The user's reported success gate requires strictly higher F1 than 008 and no additional false positives, and all precision/recall differences remain visible. Also report whether F1 exceeds both supplied v2 cutoffs. These validation gates do not select a threshold or change the demo.

After decisions are fixed, use 2,000 paired target-date bootstrap samples with seed 17017. Report F1 differences versus the matched core, unchanged base, supplied v2 cutoffs and 008. Undefined comparisons remain null. These descriptive historical-day intervals do not correct repeated validation inspection or selection bias.

## Scope and reproducibility

The validation data, 008 and several prior methods have been inspected already. This remains exploratory research, not a fresh holdout, unbiased new benchmark or scientific breakthrough claim. Additional forecasts have different model provenance and nominal lead offsets. Their original operational issue/publication times remain unverified. No original test outcomes are read or scored.

Freeze sources and inputs before fitting. Use the existing Python environment, a maximum of two threads, serial fits and a 30-minute limit. Refuse existing output directories and preserve failed attempts. Keep all 016 artifacts unchanged. No post-validation tuning or automatic deployment.

## Primary basis

[Schulz et al. (2021)](https://arxiv.org/pdf/2101.06717), §§3.1–3.3, PDF pp. 6–11, connects forecast-distribution parameters to available numerical weather forecasts and evaluates statistical post-processing of solar irradiance. It motivates using forecast information and periodic context. Its ensemble/EMOS setting differs from our two deterministic model archives and binary LightGBM head. We neither reproduce its method nor assume its gains transfer to this data. [Wolpert (1992)](https://cafri-labs.github.io/lab-manual/papers/wolpert1992.pdf), pp. 242–244, motivates training a correction on held-out predictions from the underlying v2 learner. This is a small engineering extension of those established ideas.
