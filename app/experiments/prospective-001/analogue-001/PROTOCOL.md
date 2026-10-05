# Prospective residual-analogue lock 001

Design frozen for review before inference. Research only: experiment 004 selected the raw day2 forecast, not either analogue. This capture adds two fixed research candidates; it does not promote them or change the product.

## Fixed source and future hours

Read and verify `../capture-001/selected-targets.json`, its raw response, prediction CSV, capture manifest and byte-verification record. Preserve its exact primary and secondary 24-hour sets, UTC intervals and raw forecast values. Capture completion is 2026-10-04T08:58:50.739698+00:00. No replacement request, value-based filtering or target reselection is allowed. All other returned hours remain in the original capture.

The raw captured forecast is the comparison control, using radiation strictly >600 W/m². These live, observed capture-to-valid leads differ from the nominal archived day2 lead used for training; model initiation/publication times remain unknown. Report each exact observed lead and the vintage difference. This is an explicit transfer test, not a replication at identical issuance lead.

## Historical bank and fixed methods

Use only original `data/features.csv`, `data/paphos_weather_data.csv` and the pinned `nwp-archive-001/archive.json`. Original targets are historical model/reanalysis reference values, not satellite or station measurements. Admit a training origin only when its target, converted from the recorded fixed UTC+03 labels, is strictly before capture completion. Target-before-capture is necessary timing evidence, not proof of original provider publication availability. No reference-sensitivity or satellite file is a training input.

Refit only the fixed experiment-004 cloud median and six-input mean/population-standard-deviation transform on these eligible historical rows. Keep its K=64, equal squared distance and earlier-source-origin tie break. Inputs are radiation/geometrical scale, cloud with training-median imputation, missing indicator, mean coszen and solar-hour sine/cosine. Reuse the exact frozen NOAA geometry code and preceding-hour six-midpoint convention. A live UTC valid timestamp is converted to fixed UTC+03 only for this calculation.

Lock both 004 variants: raw residual scenarios max(0,q+r_neighbor), and solar-scaled scenarios max(0,q+s_target*r_neighbor/s_neighbor). They share the same 64 neighbours. Point prediction is their median; event probability is their fraction strictly >600; the fixed decision is probability>.5. Store empirical 5th/95th percentiles. No grid, fitted threshold, calibration update, Ridge model or model selection runs. No night override or upper irradiance cap. These are marginal hourly scenarios, not full-day trajectories.

Keep every selected hour. Missing radiation produces an explicit unknown prediction; missing cloud uses the declared training-median rule and retains its flag. Malformed, repeated or absent timestamps, invalid values/units or changed source hashes stop the lock. Never insert future truth or silently replace unknown inputs.

## Lock evidence and boundary

Save input/protocol/adapter/004-geometry hashes, actual UTC lock start/end, historical memberships and latest target, fitted preprocessing, all 64 source-hour IDs/distances/scenario values, every control/candidate prediction and observed lead. Record the unchanged original capture identity. Refuse existing output directories. Before inference and before finalizing, require the local clock to precede the earliest selected interval start; a late attempt remains a failed lock. Local times/hashes are evidence, not trusted timestamp attestation.

A separate check must reconstruct joins, the strict training cutoff, transforms, neighbours/scenarios and fixed decisions from retained bytes, preserve every selected hour and confirm the raw control exactly matches the original capture. No accuracy is scored in this task. Future comparison uses the already declared SARAH3 reference, original target sets and its retrieval waiting rule; this adapter neither retrieves it nor schedules retrieval. Do not compare future original-model or persistence predictions without separately establishing their available inputs.

No changes to experiment 004, original model/data/evaluation, existing capture, website, plan or external messages. Execution waits for review of this protocol.
