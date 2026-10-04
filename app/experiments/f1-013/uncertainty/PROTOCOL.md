# Paired uncertainty for the fixed primary 013 arm

Specified before reading the 013 historical scores. Earlier experiments already used these periods, so this remains exploratory and does not restore a fresh holdout.

Compare only the predeclared primary `conditional_robust` with raw ECMWF, Stefanos's original model, persistence and the exact selected 008 and 009 controls. Retain weather-full and satellite-common masks separately, with the original validation and test hours. Recompute pooled precision, recall and F1 from sampled integer confusion counts, never by averaging daily ratios.

Use 5,000 paired circular calendar-block draws for each period and block length 1 and 7. Keep the entire calendar grid, including any reference-missing day, and apply original availability after sampling. Use seed 20261004 and share each draw across methods, references and metrics. Iterate validation then test, block length 1 then 7. Report marginal 95% percentile intervals with linear interpolation, all invalid-denominator draw counts and observed deltas. Do not impute absent references. A draw with an undefined metric remains missing for that metric and is counted explicitly.

Save the input hashes, draws and actual execution receipt. A zero-containing interval does not overturn the original point-score gate. These intervals are descriptive sensitivity to resampling this historical record. They do not adjust for repeated research, establish seasonal exchangeability, validate the reference estimates or prove real-world improvement. No tuning, arm selection or new upgrade criterion follows from them.
