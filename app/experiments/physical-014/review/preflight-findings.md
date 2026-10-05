# Independent 014 preflight findings

Before historical execution, static review found that `references()` interpreted `is_missing` as textual `true`/`false`. The pinned joined-reference source uses `0`/`1`, already reconstructed in the independent 013 audit. Missing satellite rows would therefore fail the run after planning. The reviewer required strict binary parsing and a synthetic missing-reference fixture before clearance.

The same review requested checks of both reference `feature_time` fields and the satellite interval start, explicit use of the original CSV `time` key, and the Apple native-library thread limit alongside the existing three thread controls. This record preserves the preflight defect and requested changes. It is not historical execution evidence or final clearance.
