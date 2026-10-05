# NWP event classifier with past residual context 006

Frozen before fitting or selecting this experiment. Experiment003 already tested a direct NWP classifier; this experiment is not presented as the first such test. The change is to add independently reconstructed004 solar geometry and residual history strictly preceding each prediction origin, with three fixed complexity levels and a stronger validation admission rule against raw NWP. No changes to the original model, dataset, supplied schedule, product or competition pack.

Use the exact original 3,566 validation and3,567 test origins, targets and reference values, and the pinned003/004 archive joins. The event is actual radiation strictly greater than600W/m². Original naive labels use the previously verified fixedUTC+03 mapping; no DST inference. The day2 archive remains retrospective, with historical issuance/publication unverified. Original weather features and residual outcomes are archived estimates, not verified operational observations. This already inspected test is not a fresh holdout.

## Inputs and features

Pin the four original CSVs, 003joined features, 004joined inputs and geometry helper, raw NWP archive and satellite reference before training. Reconstruct target epochs and geometry independently and require matching membership. Retain all rows. Day2 cloud and unavailable early history remain NaN; no target-hour realized inputs and no future interpolation.

Features are the fourteen003original/NWP/calendar columns, four004solar geometry columns (solar_scale, mean_coszen, solar_hour_sin, solar_hour_cos), NWP divided by solar_scale, and past residual context. A residual is original actual radiation minus the day2 forecast valid at that hour. For an origin t, use residuals only at valid timestamps strictly less than t: means over [t−24h,t) and[t−168h,t), their nonmissing counts, and the residual at t−24h. Missing histories remain NaN (counts0). These are computed from the original hourly feature/target table, with no fitted transform or reference substitution.

Eligible fitting rows have target timestamp strictly earlier than the first evaluation origin, retaining the original24-hour purge. Refit for test using only this enlarged past window. No early stopping, class weights, oversampling or external data. No evaluation-driven feature changes.

## Three fixed fits and selection

All fits use LightGBM binary cross-entropy, seed17, deterministic column-wise mode,2threads, learning_rate0.03 and lambda_l2=2. Fixed configurations in order:

1. small:200trees,5leaves,max_depth3,min_child_samples80.
2. medium:300trees,9leaves,max_depth4,min_child_samples60.
3. larger:300trees,15leaves,max_depth4,min_child_samples40.

For each validation probability vector, evaluate strict probability>cutoff for every unique predicted probability, plus0and1. Retain the complete grid. A candidate qualifies only if its precision, recall andF1 each meet the fixed raw-day2NWP values on every original validation hour. Use exact confusion-count fractions for gates and ranking; undefined metrics cannot qualify. Within qualifying thresholds rank F1,precision,recall,then closeness to0.5,then larger cutoff. If none qualifies, retain that model's best F1 threshold for diagnostic reporting only. Across qualifying models use the same score order, then earlier/smaller configuration. If no learned model qualifies, select unchanged NWP. Freeze all three thresholds, selection, configuration and input/code hashes before any new test prediction/scoring.

Evaluate each of the three frozen models once on the full test, at its frozen validation threshold; retain every candidate including failures. Compare original,persistence,rawNWP and all three candidates. Report confusion counts,P/R/F1,Brier score for the probability models; no invented W/m² point estimate/MAE for classifiers. Report default0.5 results separately without selection. A selected learned model can pass the retrospective test gate only if all P/R/F1 meet NWP with at least one strict gain. No further tuning.

## Independent reference sensitivity

After selection is frozen, score the same fixed decisions for both periods against pinned SARAH3 on every available exact target UTC. Preserve missing satellite rows as unscored; require all forecast rows. Also retain weather-reference metrics on that identical common subset to distinguish coverage from reference changes. Report full denominators and missing spans. Do not tune or select on satellite outcomes. Satellite is an estimate, not a ground sensor. No significance, live superiority, grid-curtailment or measured-savings claim.

Save fitted model text, exact probability/decision CSVs, training origins, joined features, all validation thresholds, selection before test, all metrics and hashes, execution status and failures. Refuse overwrite; use installed dependencies only. Maximum six fits with two threads. Research results remain separate from the reviewed delivery pack.
