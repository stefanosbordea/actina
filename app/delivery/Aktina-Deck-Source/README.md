# Aktina competition deck

Current artifact: `../Aktina-Pafos-2026.pptx`. Twelve slides, with editable PowerPoint text, a native process diagram, four charts backed by embedded workbooks and an editable score table. The product screenshot on slide 6 is an image.

The build imports the historical twelve-slide template and retains its monochrome layout, Arial type and slide numbering. `template.pptx` is an unchanged source copy; its historical text is replaced during the build. `Speaker-Notes.md` contains the current notes embedded in the deck.

## Reproduce

From `app/`, with the bundled Codex workspace runtime and presentations skill installed:

```sh
"$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node" delivery/Aktina-Deck-Source/build.mjs delivery/Aktina-Pafos-2026-rebuilt.pptx
```

Use a new output filename. The finalizer refuses to overwrite an existing result. `RUNTIME_ROOT` and `PRESENTATIONS_SKILL` can point to other installations of the same runtime and skill. No download or network request is needed.

The build checks `inputs.sha256.json` before loading the supplied data, comparison results, notes and template. Review changed sources before updating those hashes. Charts use literal values rounded to six decimal places for Excel workbook compatibility; original source values remain intact. Visible MAE labels use two decimals.

## Evidence and limits

`verification.json` identifies the final file, completed checks and visual review. `previews/` contains rendered slides from the final deck. Private validator receipts and draft artifacts stay under ignored `app/build/`.

The deck states that persistence beats the original model on the retained test period. Slide 8 compares the original model, fixed archived day2 weather forecast and raw residual analogues on the same 3,567 test hours. The archived forecast improves MAE and event scores. Raw analogues lower MAE further but add one false alarm against that control. Notes retain the harder validation results, satellite-reference sensitivity and missingness. No live superiority or learned-method promotion is claimed. The 3 July comparison uses equal water, energy and ending stock under illustrative tariffs. It makes no measured-saving or curtailment-recovery claim. V2 source and validation predictions are merged. Slide 11 now reports the completed historical v2 correction: precision 94.08%, recall 88.24% and F1 91.06% across 3,566 hours. Against 008 it has four fewer false alarms and one additional miss. The uncertainty interval includes zero and no unseen-data win is claimed. The intended submitted schedule remains for the team to confirm.

All twelve slides were inspected with the bundled renderer, including the revised cover, research comparison, next steps and equal team listing. Package, layout, font, embedded-workbook and re-import checks passed. An earlier draft opened and exported in PowerPoint; native export of the final team-focused revision was stopped because desktop input was changing concurrently. No stale PDF is included in the current delivery. Native interactive chart editing has not been tested.

The earlier competition update changed slide 8. The latest factual correction changes slides 6 and 11, preserving all twelve slides and the existing layout. Shotter will handle the final presentation. This deck is a checked reference, not a replacement pitch. All twelve embedded note bodies match `Speaker-Notes.md` and the build wrapper. The demo cue uses `Aktina-Backup-Final.mp4`, 44 seconds, silent. It contains historical screenshots predating the current forecast view and does not show the completed event correction. Prior deck/source and validation drafts remain under ignored `app/build/`; the delivery folder contains the current artifact.

Latest factual-update check: slides 6 and 11 were rendered and inspected. The other ten slides are pixel-identical to the preserved prior deck. Native notes, all four editable charts, four embedded workbooks, twelve-slide count and equal team-name typography pass the existing checker. [Receipt](../../results/deck-019-handoff.json).
