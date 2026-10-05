# Saved-decision mechanism diagnosis

This is a descriptive follow-up to completed experiment 013. It reads every retained exact candidate ledger for both periods and both banks. It does not open realized references, masks, prediction CSVs or observed-score reports. It does not change, refit, select or evaluate a policy.

For each bank/day/objective, retain all canonical candidates plus raw, then separate the prohibited zero-call action before examining score safeguards. Reconstruct exact P/R/F1 failures and robust/pooled F1 objectives from numerator/denominator pairs and require equality with the saved records.

Count admissible candidates with a strictly positive objective before safeguards, after each guard family alone, after each pair, and after all families. Also report an explicitly ordered precision-then-recall-then-F1 sequence. This ordering is descriptive and does not assign causal importance.

A family independently blocks a day when positive-objective candidates exist before guards but none passes that family alone. A family is necessary for the full-set rejection when removing only that family restores a positive-objective candidate. These definitions differ. Report overlapping failures without assigning each rejected candidate to one family.

For reference conflict, first ask whether each reference separately has a strict F1-improving candidate but no candidate improves both. Separately count days where each reference's own P/R/F1 safeguards permit a strict improvement for that reference, yet their candidate sets have no intersection. For each joint objective, also ask whether each reference separately permits a positive-objective candidate but their conjunction permits none. These finite-set diagnoses do not identify a true physical reference or establish probability calibration.

Report every day. Aggregate by period, bank and objective, including no-gain days, changed actions, feasible action counts, same-count versus changed-count opportunities and raw-zero-call days. Maximum attainable expected objective values are descriptive properties of retained scenarios, not realized gains or a proposed unguarded policy. Do not recommend dropping a guard on these historical data.

Freeze source hashes and diagnostic code before execution. Preserve actual commands, exit status, runtime and output hashes. Keep completed experiment 013 immutable.
