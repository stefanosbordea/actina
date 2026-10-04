# Repository handoff, 4 October 2026

Loukas Louka's application work is now alongside Stefanos's model on `stefanos-model`.

The original root `model/`, `eval/` and `data/` are unchanged. The application lives under `app/`, avoiding filename collisions with the earlier reference experiment. `transfer-manifest.json` identifies the committed source of the transferred files. Local machine logs, private messages, credentials and runtimes are excluded.

## Supplied export check

At model commit `2a093aba97f6ad615c43fa7c514044342af16e3a`, `eval/schedule_hourly.csv` contains 7,104 rows across 296 complete days. Its `actual` column agrees with the original prediction files after the scheduler's 24-hour date shift. Its `forecast` column equals `baseline` in all 7,104 rows, and equals `predicted` in only nine rows. The largest forecast/model difference is 507.15710006432414 W/m².

The demo therefore shows the LightGBM predictions separately and labels the supplied plan's forecast source. It never substitutes model values into the supplied schedule or claims the displayed cost change was caused by the model. Stefanos has been asked to confirm the intended export. His original model and scheduler remain unchanged; Loukas's separately authorized improvement experiments are in `app/experiments/`.

On 3 July the retained plan costs €2,628.2476 versus €2,994.5908 for flat production, under the illustrative price rule: a 12.2335% decrease, with both plans producing 5,658 m³ and Aktina ending at its initial 966 m³. On 16 March the retained model has MAE 48.4776 W/m² versus 156.3333 for persistence. These are different comparisons.

Reproduce the packaging and checks from the repository root:

```sh
python3 app/tools/prepare_demo.py
python3 -m unittest discover -s app/tools -p 'test_*.py' -v
python3 app/scripts/verify_release.py --install --output app/build/release-check
node app/build.mjs
```

The timestamp labels are local wall-clock strings without UTC offsets. The UI preserves them and does not infer elapsed-time behavior across daylight-saving transitions. CSV `tank` values describe hourly endpoints. Plant limits, demand and prices are illustrative, not measurements or a live operating instruction.
