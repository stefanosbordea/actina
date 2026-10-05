# Aktina speaker notes

Updated 4 October 2026. Rehearsal outline; final running time and speaker assignments need a team rehearsal. The numbered sections match the current Aktina deck. The silent 44-second backup contains historical screenshots that predate the current forecast view. Use it only as a fallback for the earlier schedule demonstration.

## 1. Aktina

Aktina starts with a simple idea: use solar electricity that would otherwise be curtailed to make drinking water, then store the water for later. Our current demonstration shows the retained model and schedule output and the evidence behind it. Recovering curtailed solar still needs a suitable plant, storage and grid coordination.

## 2. Why storage matters

Water demand and available solar do not arrive at the same time. A tank lets an operator move some water production between hours while keeping water available. We need to check both sides: whether the plan supplies water, and whether its electricity use actually helps the grid. Radiation is useful context, but a sunny hour is not proof of curtailed electricity available to a particular plant.

## 3. Grid and Sites

The roadmap has two parts. Grid compares production for a desalination unit and its tank. Sites explores garden water budgets and unusual overnight meter readings. Today's supplied model and schedule cover Grid. Sites remains a separate prototype; its synthetic examples are not field results. Neither part controls equipment.

## 4. What the demonstration loads

The demo loads 7,104 supplied schedule rows, covering 296 complete days from 6 December 2025 to 28 September 2026. Each day shows radiation, production, tank level and illustrative cost. The data, scripts and fonts are local, so the presentation does not need an API or internet connection.

We checked which forecast generated the supplied export. Its forecast column matches persistence in every row, and that version reproduces byte for byte. Stefanos's LightGBM forecast appears separately. The unchanged model-driven scheduler also runs, but produces a different schedule. We have kept both outputs; the intended submission version still needs confirmation.

Source cue: `app/handoff/README.md` and `app/handoff/scheduler-reproduction/README.md`. Do not call the displayed schedule a demonstrated LightGBM saving.

## 5. A matched day

On 3 July, flat and supplied production both make 5,658 cubic metres of water and use 19,237.2 kilowatt-hours. The supplied tank starts and ends at 966 cubic metres. Under the illustrative prices, the supplied plan costs about 2,628 euros versus 2,995 euros for flat production: 12.23 percent less. The comparison moves electricity use between differently priced hours; it does not demonstrate lower energy use or recovered solar.

This equal-stock result is specific to the day. The scheduler carries water between days and does not enforce equal daily ending stock. A cost comparison must retain production and stock change, especially at the separate validation/test resets.

Source cue: original `eval/schedule_hourly.csv`, 3 July 2026. Discount is €101/MWh when actual radiation is strictly above 600 W/m²; otherwise €183/MWh. Specific electricity is 3.4 kWh/m³. These are assumptions, not bills or a market tariff.

## 6. Demo and fallback

We will show three days, then the full benchmark. July 3 shows midday production and the matched daily cost. December 10 has no high-radiation hours; the retained tank still stays at or above its declared minimum. March 16 shows a day when the original model predicts better than persistence. We then return to all test hours so that one good day does not become the headline result.

Live cues:

- Open Aktina locally. Choose **3 July 2026**; inspect sun, production, tank and cost.
- Choose **10 December 2025**; point to low radiation and the tank minimum.
- Choose **16 March 2026**; MAE is 48.48 W/m² for the original model versus 156.33 for persistence.
- Open **AktinaBench**; show the original test comparison, then select **Archived weather forecast** and **Weather + past errors**.

Fallback: `Aktina-Backup-Final.mp4`, 44 seconds, no audio. It is a historical screenshot walkthrough that predates the current forecast view, not a live interaction recording or a showcase of the new event correction. Do not play both sequences. Online address: https://aktina-pafos-2026.vercel.app/.

## 7. What the original model achieves

We evaluated every retained prediction: 3,566 validation hours and 3,567 test hours. Validation MAE is 29.34 watts per square metre for LightGBM versus 32.47 for persistence. On the test period, that reverses: 14.27 versus 12.26. Test precision, recall and F1 also favour persistence. The model's test F1 is 0.9655; persistence reaches 0.9777.

Validation informed early stopping, and the original validation and test files come from different model fits. The adjacent original splits also lack a 24-hour prediction-horizon purge. These limits stay in the benchmark. Radiation above 600 watts per square metre defines the label; it is not observed grid curtailment.

Source cue: `app/handoff/ACTINABENCH.md`; full MAE, RMSE, precision, recall, F1, confusion counts and month/hour breakdowns are retained. Partial boundary days remain in full-period results.

## 8. Research comparison

The earlier original-test comparison examines additional weather information. On the same 3,567 original test hours, the original model has MAE 14.27 W/m². The fixed archived day2 forecast has MAE 8.81, and raw residual analogues reduce it to 6.92. Precision, recall and F1 are 97.57%, 95.54%, 96.55% for the original model; 98.51%, 98.32%, 98.41% for the archived forecast; and 98.41%, 98.32%, 98.37% for the raw analogue. These are retrospective comparisons against the original model-derived reference.

The analogue reuses 64 historical residuals to form hourly scenarios. Its lower MAE comes with one extra false alarm: 16 instead of the archived forecast's 15, with 17 misses for both. Validation retains the fixed archived forecast. On the harder 3,566-hour validation period its F1 is 90.08%, compared with 80.07% for the original model and 89.95% for raw analogues. That archived-weather comparison did not promote a learned candidate. The original model remains intact. Slide 11 covers the later completed v2 validation extension.

We also checked the same fixed forecasts against the SARAH3 satellite estimate. On 3,517 common test hours, with 50 missing reference hours retained as unscored, archived-forecast F1 is 96.59% and raw-analogue F1 is 96.54%. MAE is 19.33 versus 18.23 W/m², while false alarms rise from 42 to 43. The harder satellite validation gives the archived forecast F1 of 80.71% on 3,419 common hours. The reference changes the apparent accuracy, so the near-99% weather-reference scores cannot stand alone.

These tests were already inspected during development. Historical forecast publication times are unverified, and satellite estimates are not local ground-sensor measurements. We have separately locked 48 future forecast hours for later satellite evaluation, with no outcomes scored yet. This is evidence to review with Stefanos, not a claim of live superiority, measured curtailment recovery or field savings.

Source cue: `app/experiments/f1-004/result/comparison.csv` (fixed defaults, full test), `app/experiments/reference-sensitivity-001/result-amended/metrics.csv` (identical common-hour bases), and the frozen prospective capture. The fixed 600 W/m² event remains a radiation proxy. Analogue decisions use scenario probability strictly above 0.5. Keep original, archived-control and synthesis results distinct.

## 9. Business hypotheses

The canvas separates potential Grid customers from Sites customers. Water operators would need integration and evidence that a plan fits their operations. Hotels or managed gardens would need usable meters and a measurable water-management problem. Setup fees, subscriptions and support are revenue hypotheses. We have not established pricing, willingness to pay, margins or customer agreements. Those assumptions need to be tested with prospective users.

Presenter cue: show the updated one-page business model canvas; older PDF exports are excluded from the current review pack.

## 10. What remains outside the model

The supplied scheduler uses illustrative production, demand, tank and electricity assumptions. Demand includes the target day's recorded temperature, so this is a retrospective scenario. Pressure, flushing, water quality, ramps and maintenance are not established by these charts. A real operator would need to supply those constraints and approve any trial. There is no plant control connection, and no measured electricity-bill saving or solar recovery is claimed.

Source cue: original `model/scheduler.py`; production 100–400 m³/h, tank 4,000 m³, minimum 800 m³, start 2,000 m³ at each period. Keep hourly endpoints distinct from continuous physical safety.

## 11. Next evidence

Stefanos's v2 source and validation predictions have been received and merged without altering his original files. A small correction of its chronology-safe refit is now evaluated and shown in the historical forecast viewer. On all 3,566 validation hours, precision is 94.08 percent, recall 88.24 percent and F1 91.06 percent. There are 270 true positives, 17 false positives, 36 false negatives and 3,243 true negatives.

Supplied v2 at its original threshold scores 91.29 percent precision, 85.62 percent recall and 88.36 percent F1. The separate 008 comparison scores 92.81 percent precision, 88.56 percent recall and 90.64 percent F1. The correction has four fewer false alarms than 008 but misses one additional hour. Its higher observed F1 does not establish superiority on unseen data. The paired-day interval for the F1 difference against 008 includes zero, from −1.6061 to +2.6215 percentage points. The validation period has been reused. No new v2 test predictions were supplied or scored.

The correction changes high-solar event calls. Its radiation curve is the separately retained v2 refit, not an alteration of the supplied curve. It does not change the demonstration schedule or establish operational savings. The intended submission schedule still needs team confirmation. For a pilot, we need an operator, a data contact and an agreed measurement plan. The presentation lead can use these checked facts in the final slides and rehearse the chosen demonstration.

Source cue: `app/experiments/v2-019/result/summary.json` and `app/experiments/v2-019/review/review.json`. Event truth is strictly above 600 W/m². Source files, saved coefficients and complete matched-hour counts are retained. Two team rehearsals remain uncompleted.

## 12. Team and ask

Our team is Loukas Louka, Stefanos Bordea, Andreas Nikolaides and Cleopas Cleopa. We are asking for a Paphos operator and a data contact to help test the idea against real operating needs. The current evidence gives us a reviewable starting point, with its limits visible.

Preparation checks: confirm the team contact, final slide alignment, required competition declarations and intended schedule before submission. Keep the original source credits and third-party licences. Keep the earlier reference experiment distinct from the original model.
