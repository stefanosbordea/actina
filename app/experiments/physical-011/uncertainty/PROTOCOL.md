# Paired calendar-block sensitivity

This analysis was specified after inspecting the 011 point results. It is exploratory uncertainty analysis, not independent confirmation or an adjustment for previous experiments.

Keep both candidates, both references and both original periods. Compare coherent and shuffled plans with raw-point plans on each period's identical primary days. For each comparison report differences in mean and empirical CVaR90 of daily grid cost and grid energy. Also report the CVaR90 of paired daily cost regret. That last quantity is different from a difference between two cost tails.

Use circular moving blocks of 1 and 7 consecutive calendar horizons. Sample the original full calendar grid, including days excluded from primary scoring. Retain only primary days after drawing the weights. Thus missing days keep their positions and are never filled with invented outcomes. Use 5,000 draws per period and block length, NumPy default_rng seed 20261004, with the same draw weights for every method, reference and metric. Process validation then test, with block length 1 then 7. The number of primary days in a draw may vary. Report any empty draw explicitly.

Calculate tails from the weighted empirical distribution with exact fractional upper-ten-percent mass, including tied or negative values. Report marginal 2.5th and 97.5th percentiles with linear interpolation. Preserve all point values and counts. The frequency of draws improving all eight aggregate axes is a descriptive resampling frequency, not a probability that the method is superior.

No fitting, solver rerun, new threshold or candidate selection follows from these intervals. These blocks do not establish exchangeability across seasons, correct archive availability or measured physical savings. Preserve source hashes and write a separate result without changing the original experiment.
