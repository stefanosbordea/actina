# Official Cyprus grid evidence

Checked 4 October 2026. The useful next target is **EAC Distribution System Operator PV Generation Curtailment Reports**, rather than another irradiance threshold. These are retrospective operating reports. They distinguish a reported intervention from the energy that might have been generated without it.

## Recommended source and fields

The [January 2026 report](https://www.eac.com.cy/EN/RegulatedActivities/Distribution/DistributionSystemOperation/Documents/CURTAILMENTS_01_2026.pdf) contains a date, group-specific curtailment start/end times, whether TSOC instructed the action, its reason, Ripple/IoT disconnection areas and times, estimated daily generation, estimated curtailed MWh and percentage. Charts distinguish SCADA-connected PV output, estimated unrestricted generation, available RES penetration and setpoint commands. Their horizontal axis is marked 15-minute resolution. The chart is not a verified downloadable numerical quarter-hour series.

For example, its indexed 1 January record identifies Group 1 from 07:45–16:30 and Group 2 from 08:30–15:15, with a TSOC instruction. The [October 2025 report](https://www.eac.com.cy/EN/RegulatedActivities/Distribution/DistributionSystemOperation/Documents/CURTAILMENTS_10_2025.pdf) is indexed as a 31-page PDF. Its 25 October record also identifies Paphos disconnection groups. A [January 2024 report](https://www.eac.com.cy/EN/RegulatedActivities/Distribution/DistributionSystemOperation/Documents/CURTAILMENTS_01_2024.pdf) identifies an event on 10 January from 11:45–14:15. Thus examples span 2024–2026, but complete monthly/day coverage and the latest available month are not established.

## Access and reuse

Public search-index text was available. Current access is impaired: direct retrieval of the October PDF returned HTTP 404 on both official host spellings, and the [new forecast/production page](https://pilot.eac.com.cy/en/distribution/pv_forecast_and_production/) redirects to maintenance. No account, paid API or bulk scraping was used. No complete curtailment dataset was acquired, and cached search text should not become training truth without the corresponding original report.

No dataset-specific open licence was verified. [EAC website terms, section 7](https://eac.com.cy/Terms%20and%20Conditions/EAC%20Website%20Terms%20and%20Conditions.pdf) permit viewing, printing and downloading extracts for personal use with notices preserved and reserve EAC's intellectual-property rights. That is not evidence of a CC BY licence or unrestricted redistribution. The terms PDF was directly retrievable, 317,511 bytes, SHA256 `db7634de64ffea4ef75a7e1c9bb61b38ddee34fefccf0ec056788a5a39f2a928`.

## Label boundary and next intake

A verified ledger could label **DSO-reported PV curtailment active for a named control group during an interval**. Keep SCADA curtailment and Ripple/IoT disconnection separate. Treat the energy columns as the operator's estimates, not metered foregone energy. Missing reports or omitted areas are unknown, not zero curtailment. Neither a command nor its estimate establishes physically available electricity at a desalination connection, recoverable MWh, water production or savings.

For a bounded intake, obtain one complete report month or the DSO's corresponding CSV with date, group, start/end, command, reason, estimated MWh, method and coverage. Preserve the original bytes and verify every parsed event against the page. Confirm timezone, DST, interval endpoints and publication time. The reports do not supply an explicit UTC offset in the inspected text. The existing weather dataset's fixed UTC+03 convention must not be copied onto winter operating records. Complete coverage is needed before scoring false alarms or treating non-event intervals as negative labels.

## Supporting sources

The [TSOC weekly generation archive](https://tsoc.org.cy/electrical-system/energy-generation-records/weekly/) lists average MW data and related fields as Excel downloads, including 2024–2026 and older years back to 2006. Its warning limits assurances of completeness and accuracy. Direct access returned HTTP 403 here, so column names and numerical interval spacing were not independently inspected. Generation and demand could supply covariates once verified. Their balance is not an observed-curtailment label.

[EAC's curtailment procedure](https://www.eac.com.cy/EN/RegulatedActivities/Distribution/DistributionSystemOperation/Documents/Photovoltaic_Disconnection_Process_EN.pdf) separates staged export restrictions and disconnections and assigns final coordination to TSOC. This helps interpret group labels. It is a procedure, not a timestamped record of executed commands.

No model, original benchmark, scheduler or product files changed.
