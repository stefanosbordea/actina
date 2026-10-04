# AquaShift submission readiness

This is a local review pack for the university category. No competition application or organiser message has been sent, and no declaration or signature has been completed on anyone's behalf. Loucas authorised the WhatsApp handoff to Stefanos; delivery of the workspace and review pack was verified on 2 October.

The official submission deadline is **6 October 2026**; finalists are announced on **12 October**, and final presentations/awards are on **14 October**. The rules do not specify a closing time. The team's earlier target of **5 October** is sensible. The official rules allow **two to five members**, including students from different eligible institutions, and accept Greek or English. [Official announcement and rules](https://pafos.org.cy/diagonismos-kainotomias-pafos-2-0/)

## The five required components

| Component | Official requirement | What to review in this pack |
| --- | --- | --- |
| Executive summary | At most two pages | Problem, solution, AI use, customer/pilot route and honest expected benefit |
| Technical proposal | At most ten pages | Architecture, data, evaluation, implementation, assumptions and why AI adds value over a conventional approach |
| Business Model Canvas | Complete canvas | All nine blocks, intended buyers, pilot partners, resources, costs, income and sustainability |
| Functional PoC or MVP | Demonstrate core behaviour; a finished commercial product is unnecessary | Inspect Operations, Scenarios, Evaluation and Alerts & Sites; import a forecast/plan and record a review; distinguish historical weather, scenarios and synthetic meter data |
| Presentation | Up to fifteen minutes; live demonstration where technically feasible | Rehearse the actual screens, evidence and limits; retain the 90-second Blender concept/prototype film as the fallback |

The final PDFs/deck and their filenames are listed in the README as the pack is assembled. Check page counts and open each final file before upload. The demo/source package supports the functional component; the official upload form's accepted file formats and access expectations still need checking during submission. Source-code handover is not established as an independent mandatory component. [Official university application form](https://forms.zohopublic.eu/pafosmunicipality/form/201/formperma/KweOBBaQJ_bcYCPap3N2t6vQ5EMbNbPQzHivQGkJ5S8)

## The university rubric

| Criterion | Weight | Relevant AquaShift evidence |
| --- | --- | --- |
| Innovation and originality | 20% | The local water–energy/site-management application and integration; credit existing methods rather than claiming their invention |
| Use of AI | 20% | Frozen forecasting model, fair stronger baseline, no-leakage timing checks and clearly synthetic anomaly demonstration |
| PoC or MVP | 20% | Working dashboard, water/storage constraints, scenario comparisons, downloads and functional tests |
| Relevance to Pafos | 15% | Paphos-specific weather and a proposed local site/utility pilot; no invented customer validation |
| Business Model Canvas and sustainability | 15% | A concrete site-service entry route, honest costs/benefits and conditions for Grid expansion |
| Presentation | 10% | Clear explanation, live demo, fallback film and answers to the strongest-baseline and carbon questions |

These are the **university** weights, not the separate school-student rubric. [Official English rules, sections 7.2 and 9.2](https://pafos.org.cy/wp-content/uploads/2026/09/MUNICIPAL-YOUTH-COUNCIL-erasmus-days-competition-AI.pdf)

## Facts to keep consistent throughout the upload

- The prototype uses historical gridded weather, not a live plant or grid feed.
- The frozen model has worse average absolute error than the strongest safe persistence baseline, but better root-mean-square error. Show both.
- Equal water and energy are delivered in the schedule comparison. Clock-tariff timing creates the illustrated cost saving; additional AI cost saving is €0 in this experiment.
- A sunny-hour flag is not measured grid surplus or curtailment. Constant carbon intensity with equal energy gives zero carbon saving.
- The Sites irrigation calculation is retrospective and assumes soil/crop parameters. Its meter history and leak are synthetic.
- The reference was independently prepared with AI assistance and is replaceable by Stefanos's reviewed handoff. Do not attribute completed code or model training to a teammate without confirmation.

The next defensible improvement is a real pilot and new held-out evidence. Changing models after inspecting this test is exploratory work; it does not become a newly blind test merely by rerunning the same dates.

## Details that only the team can complete

Confirm the full legal names in Greek and English for **Loucas Louka, Stefanos, Andreas Nikolaides and Cleopas Cleopa**. The latter names are the spellings provided by Loucas, not verified application identities. Complete every member's institution, department/programme, study year, phone and email. Choose the lead contact rather than assuming one. Confirm eligible student status, one team per individual, and one original, previously unawarded proposal per team.

Each person must review the participation terms, rights/consent declarations and their own signature requirement. No signatures, invented contact details or consent boxes have been supplied here. The application terms retain participants' rights while permitting non-exclusive promotion; each member should read the actual wording before accepting. [Official university participation PDF](https://pafos.org.cy/wp-content/uploads/2026/09/%CE%95%CE%9D%CE%A4%CE%A5%CE%A0%CE%9F-%CE%A3%CE%A5%CE%9C%CE%9C%CE%95%CE%A4%CE%9F%CE%A7%CE%97%CE%A3-%CE%A6%CE%9F%CE%99%CE%A4%CE%97%CE%A4%CE%95%CE%A3.pdf)

## AI-use disclosure to review and include

A suggested disclosure, to be confirmed by the team:

> OpenAI Codex was used to assist with prototype implementation, tests, evaluation, visual presentation and draft submission materials. The forecasting reference uses LightGBM; constrained scheduling uses SciPy/HiGHS; the synthetic leak demonstration uses scikit-learn IsolationForest. These are credited upstream tools. Team members will review, reproduce and understand the submitted implementation and conclusions. The prototype's measured results and scenario assumptions are identified separately; no operational water, grid or customer benefit is claimed.

This wording describes tool assistance. It does not replace student review or assert that review/signatures have already happened. The competition permits AI assistance when disclosed in the submission. [Official rules, sections 6 and 8](https://pafos.org.cy/wp-content/uploads/2026/09/MUNICIPAL-YOUTH-COUNCIL-erasmus-days-competition-AI.pdf)

## Final practical sequence

1. Review the demo and guide together; agree the exact claims and business assumptions.
2. Complete member details, lead contact, terms and signatures yourselves.
3. Open the five final components and check page limits, names, data attribution and AI disclosure.
4. Rehearse once with the live demo and once using the fallback film.
5. Have the nominated lead upload the confirmed files, check the receipt and keep a copy, aiming for 5 October rather than relying on an unspecified final-hour deadline.
