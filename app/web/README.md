# Aktina review workspace

Production: https://aktina-pafos-2026.vercel.app/workspace/

This browser workspace evaluates supplied plans and evidence for Loucas’s concept: use otherwise curtailed solar to make drinking water, then store water. Stefanos’s model and scheduler remain replaceable team work. There is no live plant connection.

The workspace URL opens its home page: the solar-to-water idea, a real workspace preview, three usage paths and concise answers about files and evidence. Existing workspace links remain available. Reference data loads on entry to the workspace. The opening screen follows actual loading and verification; it adds no artificial delay. Self-contained handoff and observation intake remain available while that reference loads or if its verification fails. IBM Plex Sans and Mono are served locally under the SIL Open Font License; pinned source hashes and the license are in `public/fonts/`.

## Working areas

Plans groups Review, Schedule, Plan testing and Storage comparison. Forecasts groups comparison and separate forecast/plan/handoff intake. Observations groups observation import and site checks. Reference groups the system diagram and source reports. Existing view URLs remain available.

## Views

- Overview: illustrative asset topology and hour-linked inspector.
- Operations: exact retained production, tank reserve, hourly prices and CSV export.
- Plan testing: fixed-plan water replay under declared demand, production loss, outages and initial inventory; same-condition control, exact reserve/stockout/overflow crossings, a 36-case sensitivity table, observation-linked restart and reproducible review export. No replanning or energy-recovery claim.
- Scenarios: matched period storage trade-offs from 62 retained report days, four timing controls, exact daily/source exports and evidence drill-down; missing-report periods remain empty. Existing single-day tank comparison plus separately imported schedule candidates. Explicit plan selection changes the inspection context; the reference remains available.
- Data: local forecast and schedule CSV handoffs, exact raw-file hashes, timestamp/value checks, retained truth/control validation and downloadable findings. Reviewer metadata stays explicit.
- Handoff intake: one review packet retains the roadmap weather, prediction, demo-forecast and paired power-schedule files plus an explicit declaration. Reopening verifies all five hashes and recalculates. Point power is not integrated; missing coverage stays missing. Water equivalence and forecast attribution remain unestablished. Prepare a packet with `node web/review_roadmap.mjs --help` from the project root; see `../results/roadmap-handoff/README.md`.
- The same opener accepts a supplied forecast decision pair: candidate/control forecasts and plans evaluated on one common realization. It compares errors, changed production, exact water adequacy/nonregression and declared tariff cost. Method/timing declarations cannot establish causal forecast attribution. Export/reopen retains raw sources and recalculates; no model or scheduler runs. See `../results/forecast-value-study/README.md` and the analytical delivery example.
- Evaluation: paired MAE/RMSE, all-hours/daylight scopes, retained realized-cloud diagnostics, error by hour/month, weather-proxy classification and feedback CSV.
- Alerts & Sites: reserve/proxy findings, synthetic meter fixture, browser-local review marks and retrospective ET0 irrigation.
- Plan review: browser-local decisions, exact 24-hour plan, data/model identity and JSON handoff export.
- Evidence: 11 primary sources, 2024 monthly PV context, 62 July/August 2026 EAC report windows and per-tank retrospective schedule overlap. Missing reports mean unknown.
- Pilot inputs: a blank source/asset declaration builder or JSON import, observation CSV, review-time coverage, unknown gaps, 96-slot paging, latest known readings and a readiness export. The bundled example is invented and deliberately incomplete.

Forecast imports are analysis inputs only. A schedule import can be explicitly selected as a separate candidate after matched-fixture validation. Neither silently replaces the reference. Browser-local records have no account sync; export them to keep/share them. No notifications or plant commands are sent.

## Reproduce

From the `app/` directory:

```sh
.venv/bin/python web/generate.py
```

From `web/`:

```sh
npm ci --cache .npm-cache
npm test
python3 -m http.server 8788 --bind 127.0.0.1 --directory public
vercel deploy --prod --yes --scope dlukels-projects
python3 check_public.py
```

`generate.py` executes the existing SciPy/HiGHS scheduler for 92 dates × five tank sizes and checks equal production/energy, capacity, reserve and terminal inventory. Target-hour cloud cover is joined from retained weather for diagnostics only; `python3 web/check_cloud_enrichment.py` proves every other payload value matches the immutable 71-test reference by SHA-256. `public/research.json` is a public-only copy of `../data/research_evidence.json`; refresh it when source evidence changes.

`test_core.mjs` tests forecast validation, evaluation math, diagnostic boundaries/missingness and numerical parity with the retained Python evaluator. `test_schedule.mjs` independently validates all 460 retained plans and checks capacity, balance, time and unsupported-assumption failures. `test_pilot.mjs` checks observation declarations, units, numeric bounds, cadence, gaps, first-available cutoffs and DST windows. `test_workspace.mjs` exercises actual app handlers against jsdom, including imports, exports, raw BOM/CRLF hashes, state persistence, hour endpoints, chart gaps, source boundaries, blank/invalid/generated declarations, exact generated identities, 96-slot navigation, cutoff-aware Latest and empty incoming daylight subsets. jsdom is an offline DOM test, not rendered-browser verification. Test/deploy logs and exact public asset hashes are retained under `web/`.

## Scope

Radiation is a weather proxy, not measured grid surplus. Tariffs and plant scale are illustrative. The frozen model has MAE 8.81 W/m² versus strong persistence 7.64 W/m², and adds €0 tariff cost benefit over price-only scheduling in the retained evaluation. EAC windows are retrospective evidence, never scheduler input. Scheduled load during a report window is temporal coincidence, not recovered or allocated solar energy. Site meter anomalies are synthetic.

Only `public/**` and `vercel.json` are uploaded. Private attachments, raw messages, Python sources, result logs, credentials and Vercel project metadata are excluded. Papa Parse 5.7.0 is locally vendored from the official npm registry under MIT; provenance is retained in `vendor/provenance.json` and its license is public. CSV exports enable formula escaping.

## Handoff inputs

Forecast CSV: `time,predicted`; optional `actual,baseline,forecast_issue_time,baseline_source_time`. Times need an explicit offset or Z; retained truth and controls cannot be overwritten. Radiation sanity range is 0–2,000 W/m². Partial data uses paired matching hours only. Manual training/timing review states and issue-provenance flags accompany exported reviews.

Schedule CSV: `time,production_m3`; exactly 24 unique hourly instants from one retained local day. Optional `tank_capacity_m3`; otherwise the selected tank is explicitly assumed. Optional demand, inventory and prices must match the fixture. Supported fixture: unit 500 m³/h, demand 120 m³/h, tank 500/1000/2000/4000/8000 m³, reserve 20%, start/end 50%, uniform hourly flows. Alternative assumptions are reported unsupported rather than judged as a bad model.

For review, use the public Data view to export sample inputs, or use the public-data-only files under `fixtures/`. A valid flat July1/tank1000 candidate, BOM forecast, duplicate forecast and unsupported/capacity plan fixtures are retained with exact hashes. These are QA fixtures, not submissions from a teammate.

A saved review includes the exact selected plan, canonical dataset identity, imported file identity and reviewer-supplied metadata. Export links and an expandable readonly preview stay available in the current browser. Download Blobs retain the serialized UTF-8 bytes; original pilot CSV downloads also preserve BOM and CRLF. Native textarea previews normalize carriage-return line endings to LF, as noted beside those exports. Select content supports manual copying; “ready” does not certify a disk save.

## Evaluation diagnostics

Daylight is retained historical radiation strictly greater than 20 W/m². Cloud groups match the existing evaluator: [0,20), [20,60), [60,101); the retained weather range is 0–100%. These are realized target-weather diagnostics, never new forecast features. Uploaded cloud columns do not replace them. Missing/nonfinite cloud remains unknown. Each comparator uses the same accepted timestamps; empty groups have no error scores. Cloud strata are descriptive, with no computed stratum confidence intervals. Feedback CSV includes the selected all-hours/daylight scope and the diagnostic rows.

## Pilot observation contract

Schema 1 declares `label`, `source_kind` (`synthetic_fixture` or `operator_observations`), `source_label`, `timezone: Europe/Nicosia`, `window: {start,end}`, `cadence_minutes: 15|60`, and `assets`. Each asset declares a unique `asset_id`, label, and `measurements: [{measurement,unit,min,max}]`; an optional `tank_reserve_m3` is a reviewer-declared reference. Optional `review_as_of` sets the information cutoff; otherwise the latest first-available input is used, never the live clock. Use the blank browser builder, example declaration export or `fixtures/pilot-synthetic-declaration.json` for the full shape. Builder fields have no assumed source, capacities or bounds. Drafts use the same strict validator; invalid drafts and exports preserve accepted intake. Applying a valid declaration clears prior observations. Its exact UTF-8 hash is recorded as Form-generated declaration, distinct from an uploaded file identity.

Observation CSV columns are exactly `time,available_at,asset_id,measurement,value,unit`. Times require ISO seconds and an explicit offset or Z; `available_at` cannot precede observation time. The start-inclusive/end-exclusive cadence grid counts absolute instants, including 23/25-hour Cyprus DST days. Supported kinds and exact schema units are `tank_storage_m3` / `m3`, `unit_load_kw` / `kW`, `production_rate_m3_h` and `delivered_flow_m3_h` / `m3/h`, and `available_power_kw` / `kW`. The interface displays friendly names and m³ units without changing the file schema or converting values.

Missing readings and readings first available after the chosen cutoff remain distinct unknown slots. A reading below the declared reserve requires review, even with complete numeric coverage. Source kind, labels and bounds are unverified declarations. These are timestamped point observations; no interval energy, water balance, calibration, quality, safety or curtailed-energy recovery is inferred. Available power grants no dispatch permission. Forecasts, cumulative meters and undeclared extra fields are unsupported; rejection does not prove a reading is false. Limits: 20 assets, 31-day window, 100,000 measurement slots, 256 KB declaration and 10 MB CSV. Pilot inputs stay in memory and disappear on reload; no reference model or plan is rewritten. Previous/Next move through 96 declared slots without compressing missing time; Latest goes to the latest reading known at the selected cutoff, not a withheld late row. Paging does not truncate review or observation exports.

`public/pilot.mjs` exports `validatePilotContract(input)`, `validatePilot(contract,csvText,Papa,reviewOverride?)` and `pilotRecord(contract,report,identity)`. Coverage is `BLOCKED`, `PARTIAL` or `COMPLETE`; `reviewRequired` separately marks gaps or below-reserve observations. The offline wrapper uses this same validator with the retained parser, requires Node 20+, hashes original bytes and preserves existing report files. From the `app/` directory:

```sh
node web/review_pilot.mjs --contract web/fixtures/pilot-synthetic-declaration.json --observations web/fixtures/pilot-synthetic-observations.csv --output results/my-pilot-review.json
node web/check_pilot_cli.mjs
```

The CLI maps partial coverage or reserve warnings to `NEEDS_REVIEW`; complete numeric coverage is not operating approval. Exit 1 means blocked; exit 0 includes incomplete inputs requiring review. `check_pilot_cli.mjs` verifies relocation without npm, file hashes, size/encoding failures, output preservation and parser identity. CLI tools, fixtures and reports are local package files, excluded from public hosting.

Storage comparison: `storage-frontier.mjs` audits the retained reference water balance, equal energy, tariff cost and report-window overlap before aggregating. Its persistence/price-only controls are retained scalar window totals; their hourly plans are not re-audited here. Bigger tanks also begin with more absolute water at the fixed 50% inventory rule. This is a comparison of retained cases, not an investment optimum.

Supplied-file updates: unsupported forecast and schedule headers block acceptance; the documented `cloud_cover` forecast field is ignored in favor of canonical weather. Pilot blocking-findings tables show the first 100 rows while exports retain all findings. Cloud diagnostics accept only 0–100%.

Fixed-plan replay uses consecutive 24-hour inputs and constant hourly water rates, split at fractional outage boundaries. Physical storage remains between zero and capacity; excess spills and unserved demand are separate outputs. Reserve-supporting initial-water/demand bounds exclude the terminal target. The chart joins hourly storage boundaries; exact crossings and within-hour minima are retained in the assessment. Supported pilot mapping uses known hourly tank readings matching the selected reference day, requires explicit mapping, and retains the review cutoff. This is a declared historical scenario, not a live approval.

Observed departures (Plan testing) maps declared pilot streams to the selected immutable plan. Choose the observation day, explicitly map streams, set the review cutoff and compare. Tank points match exact hourly boundaries; production uses the containing hour's declared constant rate. Modeled power requires an explicit specific-energy assumption. Simultaneous unit/available-power readings compare directly; their difference does not identify a grid violation or recovered energy. Unknown readings and unmapped comparisons remain unknown. Tolerances are reviewer settings, not calibrated uncertainty. Exports preserve the source hashes, full ledger, plan and mappings; current review exports include the comparison. Changes to source, plan or comparison settings invalidate that record.

`public/observation-reconciliation.mjs` exports `reconcileObservations({record,plan,mapping,tolerances,review_as_of,specific_energy_kwh_m3?})`. It revalidates normalized observations and checks the supplied nominal plan's declared mass balance/limits. File hashes are carried metadata; the UI computes them from the original uploads. No source authentication, automatic dispatch or new scheduling occurs. Reproduce the independent numerical review with `node results/observation-reconciliation-independent-review.mjs` from the project root.

Warning-method study: `node web/study_warning_methods.mjs --output results/new-warning-study.json` reproduces the predeclared synthetic comparison without overwriting an existing output. It includes all nominal, biased, delayed and missing-reading cases; four-hour horizons, first-available cutoffs and event matching are explicit in the result. Timely held-out cases expose a trade-off: the observation-anchored plan warns fewer events than the simple trend but has fewer false predictive cutoffs. Bias and delay weaken it. These results do not establish deployment readiness or measured pilot benefits.

## Conditional solar-use comparison

Reviews → Returned revision → Solar use compares the original/returned pair with one plant-specific solar profile. Choose a template format, fill its source, plant mapping and values, then import it. The exported review retains exact profile bytes and recalculates them when reopened. Importing, removing or changing profile evidence clears the previous decision.

The JSON contract is `plant_solar_allocation` schema 1, bound to `case_sha256`, with `power_basis: total_plant_eligible_solar`. Each `[start,end)` interval needs explicit-offset timestamps and `available_at`. Two meanings are supported:

- `interval_semantics: constant_power` declares nonnegative `power_kw` or null throughout each interval. The evaluator splits at production, solar and outage boundaries and integrates the lesser of modeled load and supplied power.
- `interval_semantics: interval_energy` declares nonnegative `energy_kwh` and an upper `power_cap_kw`, each nullable. The energy belongs to the entire interval; it is never prorated across plan hours or outages. Aktina bounds each plan's possible use and jointly bounds their difference under the **same** unknown solar timing. Feasible energy cannot exceed the power limit times the duration.

`review_as_of` determines which values were available; a retrospective cutoff is permitted. Intervals must be within the remaining horizon and cannot overlap. Missing, null and later-available periods remain unknown; partial results cover only common known intervals. Unknown specific energy prevents electricity calculations. Source identity, caps and plant eligibility remain declarations.

Raw sources are limited to 2 MiB each; saved reviews may be up to 32 MiB because they retain derived interval rows. Embedded sources keep the raw-source limit. Export checks the exact UTF-8 review bytes against the reopening limit.

The interval-energy ranges allow any timing within the declared power limit, with no ramp or cross-interval coupling. They are not confidence intervals. A constant interval average is not equivalent: it can change the sign of the comparison. The UI reports a possible range and whether timing can reverse the comparison; no single inferred gain is substituted. Marginal ranges cannot be subtracted to obtain the change because their endpoints may require different solar traces. Raw bounds survive export; the direction sentence uses a scale-aware floating-point tolerance.

Both formats preserve existing water outcomes. A regional curtailment report or surplus remaining after baseline consumption is not a total plant allocation. No measured avoided curtailment, renewable procurement, cost, carbon or operating permission is established.

`node results/solar-allocation-study/run.mjs <new-output-directory>` reproduces five constant-power accounting cases. `node results/solar-timing-study/run.mjs <new-output-directory>` reproduces the sign-reversal example and its two feasible endpoint traces. The resulting `*-review.json` files open through the normal returned-review import. These are QA fixtures, not Stefanos submissions. The interval-energy derivation and separate linear-program audit are in `results/solar-timing-study/method.md`.
