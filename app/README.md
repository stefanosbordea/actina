# Aktina application

Website, review tools, evaluation fixtures and editable presentation materials by Loukas Louka.

Stefanos's authoritative model, predictions and scheduler remain at the repository root in `model/`, `eval/` and `data/`. The earlier AquaShift reference experiment is retained separately inside this application directory; it is not Stefanos's model.

## Current model demo

```sh
cd app
node build.mjs
python3 -m http.server 8527 --bind 127.0.0.1 --directory dist
```

Open `http://127.0.0.1:8527/` in a browser. All charts, fonts and input files are local; the demo needs no internet connection or external API. Deploy `app/` with its included Vercel configuration.

`site/` presents the supplied schedule and the separately retained LightGBM predictions. `tools/prepare_demo.py` packages the source CSVs without fitting a model or changing a schedule.

The supplied `eval/schedule_hourly.csv` at commit `2a093ab` is reproduced byte for byte by selecting persistence in the scheduler. The unchanged model-driven scheduler has also been run separately: it changes 469 production hours. See [the reproduction and both outputs](handoff/scheduler-reproduction/README.md). The website keeps the supplied plans unchanged and distinguishes them from the LightGBM forecast; confirmation of the intended export is pending.

## ActinaBench

Open `/benchmark.html` for the full original forecast comparison and six fixed improvement experiments, including a neural classifier. Both periods, all monthly/hourly errors and downloadable slide figures are included. No candidate improves F1, precision and recall together over test persistence. Original model files remain untouched.

See [the experiment](experiments/f1-001/README.md) and [remaining delivery work](handoff/DELIVERY-STATUS.md). Repackage retained results with `python3 app/tools/package_benchmark.py` from the repository root.

The [silent 60-second Aktina backup](delivery/Aktina-Backup.mp4) shows the current demo and full-period evaluation. It uses actual screenshots; [source, checks and reproduction instructions](delivery/Aktina-Backup-Source/README.md) are included.

## Existing review workspace

```sh
cd app
python3 scripts/serve_workspace.py --no-browser
```

Open the printed localhost address. The workspace needs only Python 3; no model packages or internet connection are required. It contains plan reviews, water accounting, prediction intake, supplied-file validation and observation review.

Run its full release checks with Node 24 and Python 3:

```sh
cd app
python3 scripts/verify_release.py --install --output build/release-check
```

`web/` contains the website and tests. `delivery/` contains the earlier AquaShift slides, PDFs, video, editable LaTeX and Blender sources. These retain their original dates and reference-data basis; they are not the updated Aktina submission. `results/` contains retained reference results and independent test inputs. Third-party licenses remain alongside their assets.

The application is a historical, illustrative demonstration. It has no plant control connection. Imported review files stay in the browser unless a user exports and shares them.
