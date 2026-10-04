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

The deck states that persistence beats the original model on the retained test period. Slide 8 compares the original model, fixed archived day2 weather forecast and raw residual analogues on the same 3,567 test hours. The archived forecast improves MAE and event scores. Raw analogues lower MAE further but add one false alarm against that control. Notes retain the harder validation results, satellite-reference sensitivity and missingness. No live superiority or learned-method promotion is claimed. The 3 July comparison uses equal water, energy and ending stock under illustrative tariffs. It makes no measured-saving or curtailment-recovery claim. Model v2 and the intended submitted schedule version remain pending.

All twelve slides were inspected with the bundled renderer, including the revised cover, research comparison, next steps and equal team listing. Package, layout, font, embedded-workbook and re-import checks passed. An earlier draft opened and exported in PowerPoint; native export of the final team-focused revision was stopped because desktop input was changing concurrently. No stale PDF is included in the current delivery. Native interactive chart editing has not been tested.

For the final competition update, slide 8 was re-rendered and visually inspected. The other eleven slides are pixel-identical to the preserved prior version. All twelve embedded note bodies match `Speaker-Notes.md` and the build wrapper. The demo cue uses `Aktina-Backup-Final.mp4`, 44 seconds, silent. Prior deck/source and validation drafts remain under ignored `app/build/`; the delivery folder contains the current artifact.
