Synthetic browser review inputs — no plant data or issued forecast.

Pilot inputs
Import long-window-declaration.json, then long-window-observations.csv.
The 121-hour window crosses the Cyprus autumn clock change. Eight readings
are supplied; the final one first becomes available two days after observation.
Review as of 2026-10-26T08:00:00+02:00: four known readings; Latest known
reading selects slots 1–96. Both local 03:00 readings have distinct ISO offsets.
Review as of 2026-10-27T01:00:00+02:00: six known readings; Latest known
reading selects slots 97–121 and shows only the known slot at midnight.
Blank review time: eight known readings, 113 missing slots; no interpolation.

form-generated-source-declaration.json is the 622-byte export actually
inspected in the form. Literal <b> labels test text handling. Applying a new
declaration clears prior observations; a blocked draft preserves them.

Evaluation
Import night-only-forecast.csv in Data & model handoff. Select Imported
handoff, then Daylight in Evaluation: zero rows, no scores, no fallback.
cloud-boundary-forecast.csv contains invented actual-plus-ten predictions
for three retained timestamps. All-hour MAE/RMSE are 10/10 W/m². Daylight
has two rows: cloud 20% enters medium, cloud 70% enters high. Each group has
one row and MAE/RMSE 10/10. These are checks, never model performance evidence.

The real retained daylight data has no row with exactly 60% cloud; that
boundary is exercised by generated module tests, not this browser fixture.
Browser export previews were read and saved manually during review. This
does not claim the browser's download transport wrote a file automatically.
