# 019: A small linear correction of the v2 and weather forecasts

Root declared this next experiment before018 completed. The logistic head performed better than the boosted head in016. Test that fixed learner on the multi-forecast inputs, with a paired past-error ablation. This is one bounded two-arm comparison, not permission for continued validation-driven parameter searches.

Reuse017's exact 10,675 common training OOF rows and 3,566 validation rows, its eleven expanded features, and the unchanged016 v2 base predictions. The core arm has those eleven features. The expanded arm adds exactly018's four fixed14-day past-error features. Reuse the frozen018 training and validation context files without changing windows, coverage or scaling. These contexts admit only observed targets t in [origin−336h,origin). Their sequential historical-observation interpretation remains essential.

Replace only the head learner. Both arms use the exact016 logistic configuration: C=1, L2 regularization, LBFGS, tolerance1e-8, maximum1,000 iterations, no class weighting and no scaler. Existing radiation/error features stay divided by100, cloud by100 and cyclic/calendar features retain their existing values. Do not standardize features or tune C.

Use the same forward head folds three through six. A fit may use only earlier OOF rows with target strictly before the held origin. Reject a one-class fit or failure to converge. Save every intermediate coefficient vector, intercept, feature order and class order, as well as final fits.

Select the event threshold using only pooled forward training predictions. Keep the181 ticks10..190 divided by200, strict probability > threshold, eligibility FP no greater than raw ECMWF day2's on those same hours, then highest exact F1, nearest tick100 and higher tick. Preserve all candidates. Retain an inadmissible arm without changing the policy or preventing the other arm from completing.

Freeze final coefficients and training-selected thresholds before loading the validation context file and predicting. Then freeze predictions before full-reference scoring. The contexts were already computed in018 from past validation observations, so this is not fully sealed-outcome validation. It remains a sequential historical simulation with a fixed policy.

Score once on all original validation hours. Report both arms, all confusion counts/P/R/F1, Brier/log loss, unchanged base radiation errors and controls for original supplied v2 at600/562, the refit at600, raw day1/day2, persistence and008. The user gate remains F1 strictly greater than008 with FP no greater than21. Do not promote a model automatically. Retain paired target-date bootstrap differences using the unchanged017 method,2,000 draws and seed17017.

Freeze sources/inputs before any fit. Use at most two threads and serial fits, capped at30minutes. Never overwrite output directories, original models, source data, test files or product defaults. Every previous validation inspection remains a limitation. No unseen-data or breakthrough claim is justified by this comparison alone.

The academic basis remains [Wolpert1992](https://cafri-labs.github.io/lab-manual/papers/wolpert1992.pdf), pp.242–244, for a second learner trained on held-out predictions, and [Schulz et al.2021](https://arxiv.org/pdf/2101.06717), §§3.2–3.3, for conditioning statistical post-processing on forecasts and historical information. The linear-versus-tree choice is a testable engineering hypothesis, not a claimed new method or transferred performance guarantee.
