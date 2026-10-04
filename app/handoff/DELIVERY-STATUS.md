# Aktina delivery handoff

Updated 4 October 2026. The review pack now includes the current historical forecast viewer, corrected deck and notes, technical-summary LaTeX source and forecast QR assets. Shotter will handle the final presentation. No competition submission or team rehearsal is claimed.

| Deliverable | Current state |
|---|---|
| [Competition pack](../delivery/Aktina-Competition-Pack.zip) | 98 verified entries, including 82 offline site assets. [Per-file and archive hashes](../delivery/Aktina-Competition-Pack.manifest.json) |
| [Technical summary](../delivery/Aktina-Technical-Summary.tex) | Current standalone source, compiled in the native editor. No separate PDF generated or included |
| [Forecast QR](../delivery/Aktina-Forecast-QR.png) | PNG, SVG, slide SVG and usage notes included. Encodes the published forecast URL |
| [Existing PowerPoint](../delivery/Aktina-Pafos-2026.pptx) | 12 slides, four editable charts, equal team credit. Slides 6 and 11 corrected. All native notes match the source. This is a factual reference for the presentation lead |
| Current forecast | Completed v2-based correction. Precision 94.08%, recall 88.24%, F1 91.06% on all 3,566 validation hours |
| Evaluation evidence | Original validation/test results, all confusion counts and earlier failed experiments retained. [019 result and independent audit](../experiments/v2-019/README.md) |
| Original source | Stefanos's v2 additions merged without rewriting them. Original source, data and outputs preserved |
| Supplied schedule | Retained unchanged. Reproduces the persistence export. The separate model-driven scheduler output remains available for team review |
| [Silent backup](../delivery/Aktina-Backup-Final.mp4) | 44 seconds, 1080p, 30 fps, no audio. Historical screenshots before the current forecast view. It does not demonstrate the new event correction |
| Submission and rehearsal | Team must confirm the intended schedule, final presentation, declarations, contacts and upload. No completion is assumed |

The current correction has four fewer false alarms than 008 and misses one extra hour. Its observed validation F1 is higher, but the paired-day interval includes zero and the validation period has been reused. This is not established superiority on unseen data. The correction changes event calls, not the refit radiation curve, supplied schedule or operating costs.

The 44-second video remains the earlier schedule walkthrough. Its verified footage was not replaced or presented as a recording of the current forecast page. [Video source and verification](../delivery/Aktina-Backup-Final-Source/README.md) remain available.

The pack contains no private messages, team-setting captures, private screenshots, historical PDF exports or research datasets. Its public workspace preview images remain bundled dependencies of the offline demo. The earlier proposal LaTeX sources remain review drafts and predate the new forecast comparison. Use the new technical summary for the current model result, and reconcile the proposal before submission.

The prior pack and manifest are preserved in `app/build/competition-pack-before-019-handoff/`. The current pack was opened after creation and every archived entry was compared with its retained source bytes. Ten packaging tests passed, including changed-source, QR, private-screenshot and no-overwrite checks. [Packaging guide](../tools/PACKAGING.md).

No plant-control connection, measured curtailment recovery or field saving is established. The schedule still uses illustrative operating and tariff assumptions. [Scheduler reproduction](scheduler-reproduction/README.md) preserves both outputs for the team to choose the intended submission version.
