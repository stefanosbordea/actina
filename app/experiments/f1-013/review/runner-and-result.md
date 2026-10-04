# Independent runner and historical-result audit

The implementation and retained result pass the review. The forecasting hypothesis does not pass its admission gate. Both conditional arms retain raw forecasts exactly. Both recency arms add two validation false positives under each reference and leave test unchanged. None is recommended as an upgrade.

The reviewer first inspected the runner and independently executed all 23 synthetic core, loader, mask, budget and stage-order tests. They passed. The final reviewed runner SHA256 is `64bdace9f7606d79ed2bd10769dff2e03fa0a058016e3904223ab9e4b23771c9`. `runner-preflight-execution-002.json` pins every reviewed executable. The protocol's status paragraph was then updated to record the freeze. Its frozen hash is `b8cf31b245b5faba48d62396e5c91ca5c47925bef9f381ff348d8383729e6fc5`. Its four arms, safeguards, ranking and admission rules remained unchanged.

The forecast-only diagnostic completed with no outcome scoring. It retained 72,459 canonical subsets and no extra raw vectors across 299 horizons. The fixed input manifest hash is `f07354b9a99a64fcea182d13380c63f061d9ca466c7fc690d8c603da39ad1f82`. Both periods were planned and hashed before the first scoring-reference load. The planning-freeze hash is `4abb2f4364f43fd357a07c067ef2a6152477c2ec37f5432cb9f46bc76a5721b8`.

`result-check.py` imports no production helper. It reconstructs all 72,459 retained candidate actions from the unclipped paths, all exact expected coefficients, scores and failed safeguards, and both ranked optima in each of 598 horizon-bank records. It checks input and result hashes, period-fixed historical cutoffs, source-day identities, 24-hour padding, complete original and common reference masks, saved original/persistence/008/009 decisions, every pooled confusion count and ratio, every daily comparator distribution, additions/removals, changed daily counts and admission gates.

The actual audit exited 0 with 3,721,230 checks. External elapsed time was 23.75 seconds. The checker reports 23.10 wall seconds, 17.03 CPU seconds and peak macOS RSS 359,383,040 bytes. The exact command and log hashes are in `result-execution-001.json`. `result.json` is the retained stdout result. No checker failure occurred in this full-result run.

## Comparison with stronger saved methods

009 has higher precision, recall and F1 under both references than all four 013 arms, in both periods. 008 has all six validation metrics higher. On test, 008 has higher weather recall/F1 and all three satellite metrics, but slightly lower weather precision. These are same-hour context comparisons with later rolling issuance information. They are not matched common-issue experiments.

For the primary conditional robust arm, weather test F1 is 98.4143%, identical to raw, compared with 98.4646% for 009. Satellite test F1 is 96.5938%, identical to raw, compared with 96.6463% for 009. Its six metrics exceed Stefanos's original CSV predictions and persistence in both periods because the unchanged raw control already did so. That difference cannot be credited to the 013 mechanism.

For recency arms, validation weather TP/FP/FN is 268/23/38 versus raw 268/21/38. Satellite is 228/45/66 versus raw 228/43/66. Both lose precision and F1 without improving recall. Every test arm is exactly raw.

The exact safeguards concern supplied daily empirical scenarios. They do not prove pooled realized gains, source publication availability, calibration or field performance. The negative result is retained without changing the frozen constraints or selecting a different arm afterward.
