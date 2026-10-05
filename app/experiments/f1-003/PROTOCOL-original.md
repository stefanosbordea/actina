# AktinaBench 003: archived weather forecast information

Frozen before training or scoring. A separate research experiment; Stefanos's original model, input files and published results remain intact.

Hypothesis: an older numerical weather forecast for the target hour can add information about changing clouds that is absent from persistence. Complexity alone is not the proposed improvement.

Use the pinned ECMWF IFS 0.25° archive in `../nwp-archive-001`. Main inputs are **48-hour lead** radiation and cloud forecasts. At our target = origin +24 hours, this provides an issuance margin compared with using 24-hour lead output. The archive does not expose actual publication timestamps, and may contain reconstructed history; this is not proof of live availability or prospective performance. Day1 data are retained for provenance but are not a model input in this experiment.

Keep the original validation and test origin timestamps and actual radiation values. Join weather forecast valid time to origin +24 hours using the source's empirically checked fixed UTC+03 label convention, not a guessed DST conversion. Stop on duplicate joins, non-finite required evaluation inputs, changed labels or missing evaluation hours; do not drop inconvenient rows. Save the raw API response and join audit. Actual radiation >600 W/m² stays the positive label.

Use eligible training rows whose target timestamp is strictly earlier than the first evaluation origin (24-hour boundary purge). Use the same input-complete eligible training rows for all newly fitted models, and disclose any exclusions. Refit for test using only eligible earlier data. Preserve the current seven features; add archived day2 radiation and cloud plus sine/cosine target hour and day-of-year. Fit no transformations on evaluation data.

Fixed comparisons:

1. Previous-day radiation, fixed cutoff600, and Stefanos's retained original predictions.
2. Archived day2 radiation directly, fixed cutoff600.
3. Archived day2 radiation with a validation-selected cutoff from450 to750 in steps of10.
4. LightGBM direct binary classifier with the seven original features, a matched newly fitted control.
5. The same classifier with the added forecast/calendar inputs.
6. LightGBM L1 regression of actual minus archived day2 radiation, using the augmented inputs; prediction = day2 + alpha × residual, clipped at zero. Alpha in {0,.25,.5,.75,1}, cutoff450–750 by10.

All fitted trees: seed17,300 estimators, learning rate.05,15 leaves, minimum40 samples per leaf, at most2 worker threads. No hyperparameter search. Classifier thresholds .05–.95 by .01. At validation, a candidate qualifies only if precision and recall each meet the higher of the original-model and fixed-persistence values; among qualifiers rank F1, then precision, recall, then distance from the natural cutoff(.5 or600), then lower alpha. If none qualifies, use fixed persistence as the fallback. Choose the method and its settings before scoring test. Save the frozen choice and every validation grid.

Report full-period and monthly F1, precision, recall, confusion counts, and MAE/RMSE for radiation-valued methods. Retain every method's test result, including losses. No additional threshold/model adjustment after viewing test.

Promotion is a separate check: the validation-selected candidate must improve F1, precision and recall over Stefanos's original model and be no worse than fixed persistence on all three with at least one strict gain, over the same complete test. Passing this retrospective comparison still requires new independent evidence before a release recommendation. Failure means no replacement. This already-inspected test is exploratory, not a fresh holdout.
