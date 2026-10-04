# Uncertainty of the frozen 009 event comparison

Declared after inspecting the point results, before resampling. This is an exploratory sensitivity check of the three changed test calls, not a new holdout, model selection procedure or proof of improvement.

Use all original 3,567 test hours. Score weather on every hour and satellite on its same 3,517 available hours. Missing satellite rows remain unscored. Compare the already-selected joint BQN policy with raw NWP and the frozen selected 008 policy. Check timestamps, labels and NWP calls agree between saved files. No fitting, margin changes or new data.

Aggregate TP, FP and FN by fixed UTC+03 target calendar day. Use the same sampled day weights for every method and reference. Retain partial days and days with no available satellite observations. Pool counts before computing precision, recall and F1.

Run 20,000 paired circular moving-block resamples for each declared block length, one and seven days, using seed 20261004. Draw ceil(number of days / block length) uniformly distributed start days, concatenate their circular blocks and truncate to the original number of days. The seven-day choice is a fixed sensitivity check for dependence across adjacent days, not a fitted dependence model.

Report candidate-minus-control point differences and marginal 2.5/97.5 percentile endpoints using NumPy's linear percentile rule. Count undefined draws rather than filling them. Report the fraction of draws with all six differences strictly positive only as a resampling diagnostic. It is not a posterior probability or generalization guarantee.

The fixed historical test has influenced the research sequence. These intervals do not undo that selection, account for all attempted experiments, establish station truth or verify historical publication times. Seven-day blocks also do not preserve all seasonal or longer dependence. Retain both block lengths regardless of result.
