# Physical decision study

Design note, not an executed result. The proposed contribution is an Aktina-specific comparison of reference-robust daily electricity regret under equal water service. Scenario construction, CVaR and linear scheduling are established methods. No novelty or field benefit is established.

## Why the existing calculation is insufficient

`app/model/scheduler.py:77–98` minimizes an illustrative clock tariff. Forecast radiation only breaks tariff ties with a coefficient of 1e-6. Better event classification therefore does not imply better dispatch. Its demand, unit limit, water balance, reserve and equal terminal storage provide useful existing constraints.

`app/web/public/paired-water-service.mjs` already independently assesses delivery, reserve and terminal stock for supplied uniform-rate plans. Reuse `assessWaterService` and `compareWaterService`. `app/results/paired-water-service/independent-oracle.py` supplies an independent rational replay. `app/results/operating-envelope/` establishes why hourly means cannot certify ramps. No extra product panel is needed.

## One bounded experiment

Three issued plans per target day: a raw ECMWF solar-aware baseline, a complete-trajectory regret plan, and its same-marginal shuffled ablation. Freeze all assumptions and code before any solve or realized-cost scoring. No forecast fitting, hyperparameter search or selection by test results.

Use the saved010 common issuance at previous-day00:00 fixedUTC+03. Target endpoints00–23 describe preceding-hour radiation, so the physical horizon runs from previous-day23:00 to target-day23:00. Endpoint leads are24–47h. Do not concatenate009 rolling-origin predictions. Saved010 raw ECMWF day2 radiation and existing reference arrays are enough. Historical publication time remains unverified.

For each validation/test stage, freeze a bank at its earliest common issue. Select the latest64 source target days with all24 weather and SARAH values finite and all24 endpoints strictly before that issue. Both reference banks share these exact day IDs. Retain missing-day exclusions. For source reference r and source day k, save the24-vector e[r,k,h] = reference[r,k,h] − historical_ECMWF[k,h]. Forecast scenarios are current_ECMWF[h] + e[r,k,h]. These empirical residual transfers are not calibrated probabilities or independent truth. No new evaluation references enter either bank.

For every plan hold demand at120m³/h, production between0 and500m³/h, capacity4000m³, initial and final stock2000m³, reserve800m³ and specific energy3.4kWh/m³. These reproduce an illustrative summer configuration, not verified Paphos plant limits. Use hourly uniform flows with S[h+1] = S[h] + q[h] −120. Required water is2880m³ and electricity9792kWh per horizon.

Declare illustrative PV conversion P(x) = min(1700, 1.7 max(0,x)) kW. The1700kW nameplate equals the assumed maximum plant load. It is not measured PV production or curtailed energy. Unlimited grid backup ensures the same water production is actually supplied in every scenario. No battery, export credit or operating recourse. Grid energy is max(3.4q[h] − P[h],0) kWh. Reuse the existing illustrative tariff101€/MWh for source endpoint hours10–16,183 for17–22 and130 otherwise, explicitly retaining its endpoint-hour convention.

First solve q0 by minimizing grid cost under the raw ECMWF profile with the common water constraints. Keep the old tariff-only schedule only as optional context, not the matched baseline.

For each reference and residual trajectory compute daily cost C[r,k](q) as the sum of hourly grid cost. Optimize the single shared production vector q by minimizing the larger of two empirical CVaR90 values of C[r,k](q) − C[r,k](q0). Each baseline scenario cost is evaluated using that scenario's PV, not the raw forecast. This measures scenario regret against the same fixed baseline action.

Use sparse linear constraints g[r,k,h] ≥ 3.4q[h] − P[r,k,h], g≥0, u[r,k] ≥ sum_h(price[h]g[r,k,h]/1000) − C[r,k](q0) − z[r], u≥0, and v ≥ z[r] + sum_k u[r,k]/6.4. Minimize v. Allow v and z to be negative. The feasible q0 gives empirical objective0, not a guarantee outside the bank. Recompute costs from q, never report arbitrary slack g as realized consumption. Define numerical feasibility and primary-objective tolerances before execution. A second solve minimizing a fixed positively weighted L1 distance from q0 can resolve equal-primary solutions. Retain its actual primary objective and residuals. A tiny relaxed violation is numerical evidence, not exact service certification.

For the shuffled arm, permute the64 scenario IDs independently within each hour using a fixed seed and the same permutations for both references. Verify identical sorted hourly values before and after shuffling. Re-solve the identical objective and constraints. This isolates temporal arrangement within each reference while retaining contemporaneous cross-reference pairing and every marginal. An expected sum of hourly grid costs would be invariant to this shuffle. Daily CVaR can differ.

## Decision and falsifier

Generate all full24h plans before scoring masks. Primary comparison uses only full original-period days with all24 reference values available for both sources. Retain separate full-weather and partial original-hour diagnostics, but never call a partial-day tail statistic a full-day CVaR. List all omitted boundary or missing-reference days.

Report per-plan production, exact and tolerance-based water replay, final stock, plant energy, PV used, grid energy, peak grid demand, daily grid cost and regret under each reference. Evaluate empirical CVaR90 with fractional tail mass, including negative losses and ties. Report mean cost and every daily ledger alongside tail values. Report how often intact and shuffled plans differ and their outcomes on identical days.

The hypothesis fails operationally if water requirements regress, either reference's mean or tail cost worsens relative to q0, or intact trajectories do not yield a distinct beneficial decision compared with the shuffled arm. Report zero or conflicting gains without another parameter search. A favorable retrospective result justifies a prospective pilot, not product replacement.

Required preflight fixtures: equal hourly marginals with identical expected hourly costs, different daily tails under dependence, identical scenarios retaining q0, physical balance and rate bounds, source cutoff, reference missingness, full-day masking, and CVaR ties/fractional tail mass. Keep solver status, all source hashes, scenario IDs, objectives, numerical residuals and actual execution receipt.

## Full-paper grounding

- [Pinson et al., author manuscript of the2009 Wind Energy paper](https://pierrepinson.com/docs/pinsonetal_wpfscenarios_fin.pdf), PDFpp4–6, equations3–12, transforms reliable marginal forecasts into dependent scenarios using a covariance estimate from fully observed forecast trajectories. PDFp10 distinguishes preserving supplied marginals from proving those marginals reliable. Its wind results do not establish solar calibration. We adopt the need for joint trajectories, not its Gaussian model.
- [Hu and Konstantinou,2026](https://arxiv.org/pdf/2601.07295), PDFp4 equations29–38 covers flushing, minimum off duration, water balance and terminal stock. PDFp5 equations39–42 adds salt dynamics. PDFpp6–7 Algorithm1 shares commitment before scenario-specific recourse. Their full desalination model explains the limit of our fixed-efficiency water-only experiment. Their plant parameters and savings cannot be transferred to Paphos.
- [Rockafellar and Uryasev, full author manuscript](https://sites.math.washington.edu/~rtr/papers/rtr179-CVaR1.pdf), PDFpp5–6 equations4–10 and PDFpp8–9 give the scenario hinge-loss and LP epigraph. Use this empirical variational definition directly. No tail calibration or finite-sample generalization guarantee follows from solving it.

Actual usable curtailment, PV conversion, tariff, pressure, salinity, membrane recovery, ramp and minimum on/off limits remain unverified. Unlimited backup buys modeled service reliability. This experiment can identify a better illustrative electricity-purchase decision while holding water service fixed. It cannot demonstrate recovered rejected solar, plant authorization or field cost savings.
