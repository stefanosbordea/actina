# Aktina delivery, 4 October

The original work split and updated demo instructions both apply. The full Grid/Sites pitch is the longer-term direction; the current supplied model and schedule cover the Grid demonstration.

| Loukas's deliverable | State |
|---|---|
| MAE, RMSE, precision, recall, F1, confusion counts | Full original validation/test results retained; no favorable-day substitution |
| Month and hour breakdowns, slide figures | Included in ActinaBench and experiment exports |
| Leakage and feature checks | Chronological boundary audit complete; experimental training purges 24 hours; original native model inspected against retained predictions |
| Help improve the predictor | Six fixed experiments run, including neural network; all predictions and losses retained; no all-metric test win over persistence |
| Date picker, sun/production/tank plots, costs | Connected to original files, with three requested showcase dates |
| Model-to-schedule connection | Supplied export reproduced byte for byte using persistence; unchanged model-driven scheduler also reproduced separately for review |
| Offline operation | Site data, scripts and fonts packaged locally; internet-free presentation assets |
| Naming | Current demo and benchmark use Aktina; legacy workspace and older delivery pack still need reconciliation |
| Updated backup video | [Version 2](../delivery/Aktina-Backup-v2.mp4) includes the rebuilt ActinaBench; 60 seconds, 1080p, 30 fps, no audio; full decode and final-shot visual checks passed |
| Updated submission documents | Older editable materials retained; final Aktina results and naming still need to be incorporated |
| Rehearsal | Two rehearsals with the team remain; no rehearsal claimed |

The original roadmap prioritizes precision because false surplus predictions can increase costs. A classifier with higher recall and lower precision is a tradeoff, not an automatic improvement. The 600 W/m² label is a radiation proxy, not observed curtailment.

The v2 video is a screenshot walkthrough, not a live interaction recording. Its original 1600 × 900 captures are explicitly upscaled for BridgeClip's 1080p landscape output. [Captures, source and verification](../delivery/Aktina-Backup-v2-Source/README.md) are retained; [version 1](../delivery/Aktina-Backup.mp4) remains unchanged. The [benchmark publication record](benchmark-redesign-publication.json) identifies the verified website assets.

Before submission: confirm the intended schedule with Stefanos, finish the current-name document pack, and rehearse the verified demo. The current website/video retain his supplied schedule. The model-driven reproduction is ready in [scheduler-reproduction](scheduler-reproduction/README.md). Keep the baseline loss visible in all evaluation claims. Any further model research remains separate from Stefanos's root files.
