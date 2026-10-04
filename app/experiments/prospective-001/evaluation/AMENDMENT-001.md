# Immutable input package

Approved on 4 October 2026 before future reference retrieval. This narrow amendment changes where the evaluator reads its already frozen bytes. It does not change forecasts, candidates, thresholds, target sets, eligibility times, reference selection or scoring rules in `PROTOCOL.md`.

The original evaluator read 32 hash-pinned files from the working repository. A legitimate v2 update by Stefanos could replace historical inputs and make an already frozen prediction impossible to assess. Preserve the exact bytes identified by the existing `input-lock.json` in `frozen-inputs.zip`, using their repository-relative paths as member names. No additional or replacement input is admitted.

The evaluator must verify the archive's pinned SHA256 before opening it, require exactly the 32 locked member names with no duplicates, read members directly into memory without extraction, and verify every member against the unchanged input-lock map. All existing capture, manifest, source, target and candidate semantic checks still apply to these retained bytes. Working-repository changes outside the evaluation package no longer affect evaluation of this frozen capture. Changed archive bytes or a changed member remain a failure.

The archive identity, byte size and member checks are recorded in a new execution receipt. The original evaluator, notes, tests, input lock, protocol and execution evidence are preserved under `history/v1/`; original run receipts are not rewritten. Tests must establish both durability under changed working inputs and rejection of archive/member corruption, missing or extra members, and duplicate names. Tests use local fixtures only.

Local byte hashes and timestamps do not authenticate provider provenance. No future reference is fetched or scored while preparing this amendment. Future commands and the original October 8/9 eligibility gates remain unchanged.
