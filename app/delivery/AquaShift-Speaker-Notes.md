# AquaShift speaker notes

Target 13 minutes 50 seconds, including a 90-second live demo or video fallback. This leaves 1 minute 10 seconds within the 15-minute limit. Read the spoken text; cues and sources are for preparation. Presenter assignments can be adjusted by the team.

## 1. AquaShift

SLIDE 1: AquaShift
Timing: 45 seconds. Presenter: Στέφανος Μπορτέας.

Preparation note (not spoken): AI tools assisted implementation, drafting and review. These artifacts are a starting point for the team to check and rehearse.

Spoken text:
AquaShift starts with a simple idea: use solar power that would otherwise be curtailed to make drinking water, then store that water for later. Loucas proposed the core idea; Stefanos developed the roadmap. We are testing how it could work with a desalination unit, a tank and a useful planning tool. The draft already lets us compare schedules and inspect the forecast evidence. Recovering curtailed solar will still need a plant with spare capacity, usable storage and permission from the grid operator. Today we will show the concept, the prototype and the evidence we need for a pilot in Paphos.

Sources (not spoken):
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.
Team contribution credit: Loucas proposed the core idea; Stefanos developed the roadmap.

## 2. Paphos needs water resilience

SLIDE 2: Paphos needs water resilience
Timing: 65 seconds. Presenter: Andreas Nikolaides.

Spoken text:
Paphos has good reasons to plan its water supply carefully. Cyprus Mail reported that its three main dams were around nine percent full in January 2026, using Water Development Department figures. By September, conditions had improved: Asprokremmos was reported at 37.6 percent. The January number on this slide is dated context, rather than today's reservoir level. On the electricity side, a CyprusGrid industry estimate put curtailed distributed renewable generation at roughly 306 gigawatt-hours across Cyprus in 2025. That national estimate cannot tell us how much a particular plant could use. It does show why flexible demand deserves investigation. A desalination operator needs to produce enough water every day. If some of that production can move into otherwise curtailed solar hours, a tank could help carry the supply into later demand.

Sources (not spoken):
Cyprus Mail, 14 January 2026, reports WDD figures: https://cyprus-mail.com/2026/01/14/paphos-water-supply-at-amid-critically-low-dam-levels
Cyprus Mail, 23 September 2026, reports WDD/CNA: https://cyprus-mail.com/2026/09/23/pomos-has-highest-water-level-in-paphos-reservoirs
pv magazine, 13 January 2026, citing CyprusGrid industry analysis: https://www.pv-magazine.com/2026/01/13/cyprus-solar-curtailment-hits-47-in-2025/
Cyprus Mail guest analysis, 19 March 2026: https://cyprus-mail.com/2026/03/19/why-cyprus-wastes-nearly-half-its-solar-energy-and-what-battery-storage-could-fix

## 3. Grid and Sites

SLIDE 3: Grid and Sites
Timing: 55 seconds. Presenter: Στέφανος Μπορτέας.

Spoken text:
Stefanos's roadmap develops the idea into Grid and Sites. Grid helps a water operator compare production schedules for a desalination unit and its tank. Sites helps a hotel or garden operator review an irrigation budget and unusual overnight meter readings. We propose starting with a small site because it gives us a manageable place to collect data and work with an operator. Grid would need more work on operating limits, electricity arrangements and procurement. Both parts currently give advice. They send no command to a plant or irrigation controller. The operator can inspect the inputs, compare the suggestion with a baseline and decide whether the recommendation makes sense.

Sources (not spoken):
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.

## 4. A working planning loop

SLIDE 4: A working planning loop
Timing: 70 seconds. Presenter: Loucas Louka.

Spoken text:
The planning loop starts with saved historical weather for Paphos. We keep its source and timestamps, estimate the following day's solar radiation, then compare the prediction with simple controls. The weather is a gridded reconstruction, so this test cannot establish how an operational forecast would have performed at the time. Radiation tells us about sunny hours; an actual curtailment signal has to come from the grid. Historical EAC reports now give the workspace dated grid context. The planner uses assumed hourly electricity prices and limits on production and storage. The forecast orders production within hours that have the same price. The dashboard then shows the plan, the tank trajectory and the evidence behind them. Saved rows can be exported for review. If the scheduler has no usable forecast, it retains the flat baseline. If production capacity cannot meet demand, it reports that the scenario is infeasible.

Sources (not spoken):
results/metrics.json; results/independent-review.json. Open-Meteo ECMWF IFS historical reconstruction. Training targets before 1 July; test July to September 2026. Nominal previous-day 18:00 cutoff; original publication vintages uncertified.
model/scheduler.py; build/deck-data.json, 15 July. Unit 500 m³/h, tank 4,000 m³, demand 120 m³/h, energy 3.4 kWh/m³, reserve 800 m³. Assumed prices €101/MWh at hours 10-16, €183 at 17-22, €130 otherwise. Uniform hourly flows; real ramp/minimum-run/maintenance constraints absent.
Implementation: model/train.py, eval/evaluate.py, model/scheduler.py, model/sites.py; web/public. Grid context: data/eac_curtailment_days.json, 62 July/August EAC daily reports; main report fields only, not plant allocation.

## 5. Same water and energy, different hours

SLIDE 5: Same water and energy, different hours
Timing: 80 seconds. Presenter: Στέφανος Μπορτέας.

Spoken text:
This example uses 15 July. Both plans make 2,880 cubic metres of water and use 9,792 kilowatt-hours. The tank starts and finishes with 2,000 cubic metres. That prevents a cheaper plan from borrowing water from the following day. With the assumed hourly prices, the flat plan costs about 1,320 euros and the shifted plan about 989 euros: a 25.1 percent scenario reduction. The reduction comes from cheaper production hours and enough storage to use them. We checked the contribution of forecasting across all 92 test days. The reference model, strong persistence, climatology and a price-only plan produced exactly the same water, energy and tariff cost. Added AI cost benefit was zero euros. Equal energy at a constant carbon factor also gives zero modeled carbon saving. A real pilot must measure whether the changed production uses solar that would otherwise be curtailed before we can claim that benefit.

Sources (not spoken):
model/scheduler.py; build/deck-data.json, 15 July. Unit 500 m³/h, tank 4,000 m³, demand 120 m³/h, energy 3.4 kWh/m³, reserve 800 m³. Assumed prices €101/MWh at hours 10-16, €183 at 17-22, €130 otherwise. Uniform hourly flows; real ramp/minimum-run/maintenance constraints absent.
Attribution source: results/independent-review.json. Four forecast strategies have equal 92-day cost, water and energy.

## 6. The demo and its fallback

SLIDE 6: The demo and its fallback
Timing: 120 seconds. Presenter: Loucas Louka.

Spoken text:
We will spend ninety seconds in the workspace. Start with one saved day, then compare tank sizes. The water total stays fixed while the production plan changes. We will check the forecast comparison and switch the simulated meter anomaly off and on. If the browser fails, the ninety-second film shows the concept and the working draft.

Presenter cues (not spoken): 0-20 s: Overview, 1 July, tank 4,000 m³, inspect hour 13. 20-45 s: Scenarios, compare 500 and 8,000 m³; point to equal water and assumed tariffs. 45-65 s: Evaluation, MAE 8.81 versus 7.64. 65-85 s: Alerts & Sites, switch the synthetic anomaly off and on. 85-90 s: return to Overview. Fallback: play AquaShift-Concept-and-Prototype.mp4 instead of the live sequence; do not play both.

Sources (not spoken):
model/scheduler.py; build/deck-data.json, 15 July. Unit 500 m³/h, tank 4,000 m³, demand 120 m³/h, energy 3.4 kWh/m³, reserve 800 m³. Assumed prices €101/MWh at hours 10-16, €183 at 17-22, €130 otherwise. Uniform hourly flows; real ramp/minimum-run/maintenance constraints absent.
Workspace: https://aquashift-pafos-2026.vercel.app. Fallback: delivery/AquaShift-Concept-and-Prototype.mp4. The July 1 demo date differs from the July 15 numerical example on slides 5 and 8.

## 7. The stronger control wins on MAE

SLIDE 7: The stronger control wins on MAE
Timing: 100 seconds. Presenter: Loucas Louka.

Spoken text:
We evaluated an independent reference while waiting for Stefanos's model handoff. The test covers 2,208 hours over 92 days, from July through September. For the control, we assume same-hour readings through six p.m. are available at the previous day's issue time. We have not verified publication delays or the original data vintages. The rule uses the preceding day through six p.m., and the day before that for later hours. On mean absolute error, the reference scores 8.81 watts per square metre; stronger persistence scores 7.64. The reference is about 15.4 percent worse on that measure. Its lower root mean square error suggests fewer large errors, so the measures need to be read together. The paired-day interval for the MAE difference is about plus 0.18 to plus 2.07. Sunny-hour precision is close: 98.20 percent for the model and 98.36 for persistence. Those flags describe radiation, not measured surplus electricity. Added AI forecasting value remains unproven. Next we should freeze Stefanos's model and Loucas's prediction experiments and compare them with this control, without tuning on the test quarter.

Sources (not spoken):
results/metrics.json; results/independent-review.json. Open-Meteo ECMWF IFS historical reconstruction. Training targets before 1 July; test July to September 2026. Nominal previous-day 18:00 cutoff; original publication vintages uncertified.
Strong baseline nominal rule: day−1 same local hour for target 00–18, day−2 for 19–23. Paired-day bootstrap 2,000 repeats, seed 20261002. Seasonal dependence remains.

## 8. Sites: irrigation and an overnight fixture

SLIDE 8: Sites: irrigation and an overnight fixture
Timing: 70 seconds. Presenter: Loucas Louka.

Spoken text:
Sites applies the same approach to a garden and a meter. For 15 July, the saved weather gives evapotranspiration of about 6.32 millimetres. With an assumed 5,000-square-metre garden, crop coefficient and irrigation efficiency, the suggested amount is about 26 cubic metres. A six-millimetre timer would apply 30. The 13.3 percent difference is a scenario comparison; a hotter day or a different timer can change its direction. We also generate normal meter history and keep the query day out of training. Adding 0.3 cubic metres per hour over four night hours gives four flagged fixture hours, compared with none in the matched no-leak control. That tests the review workflow. Field detection accuracy still needs real meter histories, faults and seasonal patterns. In a pilot, the operator should help choose and review the alert threshold.

Sources (not spoken):
Source: model/sites.py and build/deck-data.json. ET0 and rainfall sum over 15 July 2026 local time. Area 5,000 m², crop coefficient 0.70, efficiency 0.85, effective rain 80%, assumed soil reserve 0 mm, timer 6 mm/day.
Meter history and query are synthetic. IsolationForest trains only on 28 generated normal days. Injected event: 0.3 m³/h in hours 01–04, 1.2 m³ total. Fixture labels never enter fitting.

## 9. The business model hypotheses

SLIDE 9: The business model hypotheses
Timing: 80 seconds. Presenter: Cleopas Cleopa.

Spoken text:
I'll show our one-page business model canvas now. Our first customer segment is a hotel or municipal garden with a usable meter. The value proposition is practical water advice whose benefit we can measure. Direct operator contacts and irrigation installers are the proposed channels. Customer relationships would start with a hands-on pilot and regular review. The revenue hypothesis is a monthly Sites fee of 99 to 299 euros or a share of verified savings; Grid could later use a licence or the proposed twenty-percent savings share. We still need to test those prices, and we have no signed customer or revenue. Our resources are the team's skills, meter access and weather data. The activities are evaluating forecasts, reviewing plans and supporting the site. Partners would include the site operator, an installer and a water or plant operator for Grid. The main costs are team time, meter integration and support. Andreas and Cleopas will test these assumptions in customer interviews.

Presenter cue (not spoken): Open delivery/AquaShift-Business-Model-Canvas.pdf and keep its one-page nine-block canvas visible while presenting this slide. Return to slide 10 afterwards. Allow the switch within this slide slot.

Sources (not spoken):
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.
delivery/AquaShift-Business-Model-Canvas.pdf: all nine canvas blocks presented alongside slide 9.

## 10. Safety, privacy and AI disclosure

SLIDE 10: Safety, privacy and AI disclosure
Timing: 55 seconds. Presenter: Στέφανος Μπορτέας.

Spoken text:
An operator must approve any action in a real pilot. The model checks water balance, storage limits and production capacity, but equipment also has ramp rates, maintenance needs, salinity limits and other constraints. Those need to be added with the plant operator. The scheduler retains a flat baseline when the forecast is missing and blocks an infeasible plan. For site data, we would agree access, purpose, retention and deletion with the owner, keep private readings separate and record approvals. AI tools assisted the coding, drafting and review of this starting point. We will disclose that assistance, credit the software we used and have the team review the submission. The draft has not undergone field safety testing or a legal compliance assessment.

Sources (not spoken):
model/scheduler.py; build/deck-data.json, 15 July. Unit 500 m³/h, tank 4,000 m³, demand 120 m³/h, energy 3.4 kWh/m³, reserve 800 m³. Assumed prices €101/MWh at hours 10-16, €183 at 17-22, €130 otherwise. Uniform hourly flows; real ramp/minimum-run/maintenance constraints absent.
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.
Competition source: supplied Official rules.pdf. AI assistance includes OpenAI Codex for implementation, evaluation review, artifact preparation and editing. Team members must review and confirm the final submission and tool disclosure.

## 11. A 30 / 60 / 90 day pilot path

SLIDE 11: A 30 / 60 / 90 day pilot path
Timing: 55 seconds. Presenter: Andreas Nikolaides.

Spoken text:
We propose three pilot stages. In the first thirty days, agree one site, a data contact and a measurement plan. Check the meter units, missing data, operating limits and who approves actions. Continue only with a usable baseline and an agreed scope. By sixty days, run suggestions in shadow mode. Compare the simple control, Stefanos's model and Loucas's prediction experiments on fresh data, and record false alerts and operator feedback. If prediction adds no value, simplify it. By ninety days, consider a small controlled trial with the operator's approval. Compare equal water supply, storage, costs and any measured renewable displacement. The business team will use the results to test payment and support costs. If a plant has no spare capacity, Sites remains a smaller pilot option.

Sources (not spoken):
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.
Proposed pilot stages; site approval and fresh measurements required.

## 12. The team and the pilot ask

SLIDE 12: The team and the pilot ask
Timing: 35 seconds. Presenter: Cleopas Cleopa.

Spoken text:
Loucas proposed the core idea and will work on evaluation, the dashboard and prediction experiments. Stefanos developed the roadmap and leads the model and scheduler work. Andreas Nikolaides and Cleopas Cleopa are business students working on the business case and pitch. Our ask is one Paphos pilot site and one data contact. A hotel garden could start Sites; a plant or water operator could help test Grid. We would agree the baseline, begin in advice mode and measure the result. Thank you.

Sources (not spoken):
AquaShift Pitch.pdf, 30 September 2026: roadmap and proposed business terms.
Team roles confirmed by Loucas. Greek name retained as supplied; no overall team lead assigned.