# Your part, in plain English

AquaShift uses electricity that would otherwise be curtailed to make drinking water, then stores the water for later. It needs a plant with spare production capacity, a usable tank and permission to coordinate with the grid. A sunny day alone does not prove that electricity was available to recover.

Under Stefanos's September 30 roadmap, **he builds the primary prediction model and the plant/tank scheduling assumptions. You check the predictions and resulting plans, explain the evidence, and make them usable in the dashboard.** Andreas Nikolaides and Cleopas Cleopa handle the business case and pitch.

## What you now have

The [online workspace](https://aquashift-pafos-2026.vercel.app) connects the unit, tank, historical weather, plan, forecast checks, source reports and review records. It has a working independent reference while Stefanos prepares his handoff. That reference is not presented as his work.

Evaluation means checking whether a prediction helps. Compare the same hours with a competent simple forecast; count errors; check that the model never used information unavailable when the prediction was made. Then check whether a better prediction changes useful decisions while maintaining the same water service and tank limits.

The current reference loses to safe persistence on average absolute error: 8.812 versus 7.638 W/m². It has lower RMSE, 17.942 versus 19.433. This finding says nothing about a model Stefanos has not supplied.

The default scenario makes 2,880 m³ with 9,792 kWh. Its lower assumed tariff cost comes from the schedule, with €0 extra saving attributable to the model over price-only scheduling. The dated EAC windows let you inspect when that load falls relative to reported curtailment. They do not measure recovered solar electricity.

## What to inspect when you wake

1. Open Operations: July 15, tank 4,000 m³. Inspect hour 13 and evening hour 20; the tank should fill and later supply demand.
2. Compare tank sizes in Scenarios. Water service and terminal rules stay fixed.
3. Open Evaluation and Evidence. The controls and source limits should be understandable without a sales claim.
4. Watch the 90-second concept/prototype film. Review the one-page summary, three-page brief, business canvas and editable deck.

When Stefanos supplies predictions, import his CSV and retain the issue-time/training provenance. Compare it with the same controls. Review his schedule against water balance, storage and capacity before treating it as an operational recommendation.

Your meaningful contribution is the evidence and decision workflow: make it possible to tell which predictions help, whether the plan supplies water, and what the operator should inspect next. The research note also gives Stefanos concrete papers on forecast provenance, variable-speed pumping and safe desalination flexibility.

The documents retain your original concept and philosophy, Stefanos's roadmap contribution and the team's roles. Codex assistance is disclosed. Loucas approved the WhatsApp handoff on 2 October. Competition submission remains pending.
