# Aktina competition delivery

The original work split and updated demo instructions both apply. The full Grid/Sites pitch is the longer-term direction; the current supplied model and schedule cover the Grid demonstration.

| Loukas's deliverable | State |
|---|---|
| MAE, RMSE, precision, recall, F1, confusion counts | Full original validation/test results retained; no favorable-day substitution |
| Month and hour breakdowns, slide figures | Included in AktinaBench and experiment exports |
| Leakage and feature checks | Chronological boundary audit complete; experimental training purges 24 hours; original native model inspected against retained predictions |
| Help improve the predictor | Six research experiments retained, including neural, purged linear, archived-weather, residual-scenario, constrained-correction and event-classifier methods. The last classifier passes the original-reference gate narrowly but loses on satellite test; no general replacement is recommended. [Full evidence](../experiments/README.md) |
| Date picker, sun/production/tank plots, costs | Connected to original files, with three requested showcase dates |
| Model-to-schedule connection | Supplied export reproduced byte for byte using persistence; unchanged model-driven scheduler also reproduced separately for review |
| Offline operation | Site data, scripts and fonts packaged locally; internet-free presentation assets |
| Naming | Current demo and review workspace use Aktina; the benchmark is AktinaBench. Historical delivery files retain their original names |
| Updated backup video | [Final video](../delivery/Aktina-Backup-Final.mp4): 44 seconds, 1080p, 30 fps, no audio. Full decode and all six scene checks passed |
| Updated submission documents | Current Aktina PowerPoint has 12 slides, editable charts and equal team credit once. Current LaTeX sources compile in the native editor; earlier PDF exports remain historical and are excluded from a current submission |
| Rehearsal | Two rehearsals with the team remain; no rehearsal claimed |

The original roadmap prioritizes precision because false surplus predictions can increase costs. A classifier with higher recall and lower precision is a tradeoff, not an automatic improvement. The 600 W/m² label is a radiation proxy, not observed curtailment.

The final video is a screenshot walkthrough, not a live interaction recording. It uses Aktina and AktinaBench throughout, with no voice or added overlays. Its original 1600 × 900 captures are upscaled for BridgeClip's 1080p landscape output. [Captures, source and verification](../delivery/Aktina-Backup-Final-Source/README.md) are retained; earlier videos remain unchanged. The [publication record](benchmark-research-publication.json) identifies the current verified website assets.

The completed presentation, silent video and offline demo can be reviewed now. Before presenting, confirm the intended schedule with Stefanos and rehearse the demo. The current website/video retain his supplied schedule. The model-driven reproduction is ready in [scheduler-reproduction](scheduler-reproduction/README.md). The archived-weather comparison improves the original test point scores; the learned analogue does not pass the stronger forecast control for release. Future forecast evaluation is separate and does not delay competition delivery. Stefanos's root files remain unchanged.
