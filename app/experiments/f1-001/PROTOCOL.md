# ActinaBench F1 experiment 001

Target: improve recognition of hours with radiation strictly greater than 600 W/m². Report F1, precision and recall together, with all confusion counts and monthly results. An improvement in one metric is not automatically an improvement in all three.

Use Stefanos's original prediction-file timestamps to fix validation and test membership. Features identify an hourly forecast origin; target labels belong 24 hours later. Train only on rows whose target timestamps are earlier than the first evaluation origin. This removes the last 24 hourly training rows at each boundary. Actual data-availability timestamps are absent, so this is a conservative historical timing convention, not a verified live forecast.

Candidates, fixed before training:

1. Original persistence at 600 W/m²; unchanged reference.
2. Persistence with cutoff selected on validation, over 450–750 W/m² in steps of 10.
3. Existing LightGBM regression settings (148 trees, learning rate .05), retrained with the temporal gap; fixed 600 cutoff.
4. Direct LightGBM binary classifier with the seven existing predictors.
5. The same classifier with causal 24-hour weather history and calendar cycles.
6. A standardized feedforward neural classifier with hidden layers 64, 32, 16, using the same history features.

The retained original model predictions are also reported as a reference, without loading or changing its model file.

Classifiers use seed 17. Trees: 300 estimators, learning rate .05, 15 leaves, minimum 40 samples per leaf, two worker threads. Neural model: Adam, learning rate .001, alpha .001, batch 128, at most 200 iterations, no random early-stopping validation. Fit scaling only on the training subset. No automatic class balancing.

Select probability thresholds on the chronological validation block only, on .05–.95 in .01 steps. Rank by F1, precision, recall, then proximity to .5. Report both .5 and selected-threshold outcomes. For the final test, refit using all eligible pre-test rows, preserving the temporal gap. The candidate to recommend is chosen from validation before scoring test outcomes; other candidates remain visible.

The existing test has already been inspected and motivated this experiment. Every resulting test comparison is retrospective exploratory evidence. Do not claim a new independent holdout, prospective accuracy, universal superiority or field savings. No test-driven threshold adjustment or hidden candidate deletion is permitted. A fresh later holdout is needed to establish generalization after development.

Stefanos's root model, scheduler and input files remain unchanged. Experimental artifacts live in this directory. The task is forecast classification; it does not generate a plant schedule.

References: [tree and neural benchmark](https://arxiv.org/abs/2207.08815), [neural tabular baselines](https://arxiv.org/abs/2106.11959), [causal lag evaluation](https://scikit-learn.org/stable/auto_examples/applications/plot_time_series_lagged_features.html), [time-series gap](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html), [decision threshold selection](https://scikit-learn.org/stable/modules/classification_threshold.html).
