# Aktina delivery, 4 October

The original work split and updated demo instructions both apply. The full Grid/Sites pitch is the longer-term direction; the current supplied model and schedule cover the Grid demonstration.

| Loukas's deliverable | State |
|---|---|
| MAE, RMSE, precision, recall, F1, confusion counts | Full original validation/test results retained; no favorable-day substitution |
| Month and hour breakdowns, slide figures | Included in AktinaBench and experiment exports |
| Leakage and feature checks | Chronological boundary audit complete; experimental training purges 24 hours; original native model inspected against retained predictions |
| Help improve the predictor | Four research experiments retained, including neural, purged linear, archived-weather and residual-scenario methods. Fixed archived weather forecasts improve test point scores; no learned candidate passes the stronger control for release. [Full evidence](../experiments/README.md) |
| Date picker, sun/production/tank plots, costs | Connected to original files, with three requested showcase dates |
| Model-to-schedule connection | Supplied export reproduced byte for byte using persistence; unchanged model-driven scheduler also reproduced separately for review |
| Offline operation | Site data, scripts and fonts packaged locally; internet-free presentation assets |
| Naming | Current demo and review workspace use Aktina; the benchmark is AktinaBench. Historical delivery files retain their original names |
| Updated backup video | [Version 2](../delivery/Aktina-Backup-v2.mp4) includes the rebuilt benchmark; 60 seconds, 1080p, 30 fps, no audio; full decode and final-shot visual checks passed |
| Updated submission documents | Current Aktina PowerPoint has 12 slides, editable charts and equal team credit once. Current LaTeX sources compile in the native editor; earlier PDF exports remain historical and are excluded from a current submission |
| Rehearsal | Two rehearsals with the team remain; no rehearsal claimed |

The original roadmap prioritizes precision because false surplus predictions can increase costs. A classifier with higher recall and lower precision is a tradeoff, not an automatic improvement. The 600 W/m² label is a radiation proxy, not observed curtailment.

The v2 video is a screenshot walkthrough, not a live interaction recording. Its captures retain the benchmark name displayed at recording; a final-name video refresh remains pending. Its original 1600 × 900 captures are explicitly upscaled for BridgeClip's 1080p landscape output. [Captures, source and verification](../delivery/Aktina-Backup-v2-Source/README.md) are retained; [version 1](../delivery/Aktina-Backup.mp4) remains unchanged. The [benchmark publication record](benchmark-redesign-publication.json) identifies the verified website assets.

Before submission: confirm the intended schedule with Stefanos, finish the current-name document pack, and rehearse the verified demo. The current website/video retain his supplied schedule. The model-driven reproduction is ready in [scheduler-reproduction](scheduler-reproduction/README.md). Keep the baseline loss visible in all evaluation claims. Any further model research remains separate from Stefanos's root files.
