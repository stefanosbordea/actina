# Your part in Aktina

Aktina explores using available solar electricity to make drinking water earlier, then storing the water for later demand. Spare plant capacity, tank space and a verified electricity allocation are needed; sunny weather alone does not establish recoverable curtailment.

Stefanos owns the primary forecast model and scheduler. Loukas owns evaluation, feature/filter feedback, integration and the usable demo. Andreas Nikolaides and Cleopas Cleopa contribute the business case and pitch. The current collaboration also includes separate prediction experiments; these preserve Stefanos's original files.

## What is ready

- [Aktina](https://aktina-pafos-2026.vercel.app/) presents the supplied schedule with a date picker, actual/forecast radiation, water production, tank levels and stated tariff assumptions.
- [AktinaBench](https://aktina-pafos-2026.vercel.app/benchmark.html) compares the original model, persistence and six fixed experiments. Validation and test remain separate; every month and hour is included. Predictions, confusion counts, MAE/RMSE and slide figures are downloadable.
- [The review workspace](https://aktina-pafos-2026.vercel.app/workspace/#reviews) supports supplied-file checks, fixed-plan water accounting and reproducible review exports. Its retained reference experiment is separate from Stefanos's model.
- [The silent 60-second backup](Aktina-Backup-v2.mp4) shows the actual supplied demo and rebuilt benchmark. It is a screenshot walkthrough; its captures retain the earlier benchmark spelling. Version 1 and both editable sources remain available.

## What the evaluation says

Evaluation checks the same timestamps against a useful simple forecast, counts misses and false surplus predictions, and checks what information was available when each forecast was issued. It then distinguishes forecast accuracy from useful changes in the water plan.

On the full original test, persistence has lower MAE and higher F1, precision and recall than the original model. The validation-selected direct classifier recovers more surplus-labelled hours, with more false positives than persistence. No tested candidate improves all three classification metrics together. The roadmap prioritizes precision because false surplus predictions can increase costs. These are retrospective results on already inspected periods, not proof of future performance.

The supplied schedule is reproduced byte for byte when the scheduler selects persistence. Running the unchanged scheduler with the model forecast produces a different plan, changing 469 production hours. Both reproductions are retained in [the schedule report](../handoff/scheduler-reproduction/README.md). The site keeps the supplied export until Stefanos confirms the intended replacement; its displayed cost is not attributed to the model.

## Next handoff

Stefanos is preparing Aktina v2; no new model handoff has been received. When it arrives, retain its exact files and timing declarations, rerun the same full-period comparisons, review changed plans against the same water constraints, and integrate the agreed export. Keep the current baseline losses visible.

Finish the current-name submission documents, confirm member details and lead contact, then rehearse twice: once live and once with the silent backup. See [delivery status](../handoff/DELIVERY-STATUS.md) and [submission readiness](Submission-readiness.md). No competition submission or human rehearsal is claimed complete.
