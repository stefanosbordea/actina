# Perfect-foresight headroom diagnostic

Added after experiment 011 began planning, before its outcome report was inspected. This is a diagnostic of the simplified physical model. It is not a forecast candidate, an available operating policy or an independent evaluation.

For every primary comparison day and each reference separately, solve two linear programs using that day's complete realized reference trajectory. One minimizes grid cost. The other minimizes imported grid energy. They may produce different schedules. Compare every saved 011 schedule with the matching minimum, on exactly the same days. Do not select a candidate or tune its parameters from these results.

Use the same declared conversion, hourly indexing, prices and water constraints as 011. Production lies between 0 and 500 cubic metres per hour. Demand is 120 cubic metres per hour. Storage starts and ends at 2,000 cubic metres and remains between 800 and 4,000. Specific energy consumption is 3.4 kilowatt-hours per cubic metre. Illustrative PV power is min(1,700, 1.7 × max(GHI, 0)) kilowatts. Grid imports are nonnegative and cover any production electricity above PV. There is no export revenue, ramp limit or extra operational model.

Implement these programs independently of the candidate solver, using 48 variables for production and grid imports. Use HiGHS dual simplex with one thread and feasibility tolerances of 1e-9. No secondary scheduling objective is needed for a lower bound. Reconstruct grid imports and inventory directly from each solution. Audit primal feasibility, the solver objective and each saved schedule's gap to the bound within 1e-6 in the corresponding native units. Retain signed gaps, including numerical residuals. Do not silently clip them to zero.

Save each solution and the exact input hashes. Report the primary comparison size, mean lower bound, each method's mean gap, and maximum daily gap for cost and energy separately. These numbers measure the maximum room for improvement under perfect future information and this illustrative model. They cannot establish attainable forecast gains, real curtailment recovery or actual plant savings.

Analytical checks before historical execution cover a zero-PV day, a known midday-PV case, storage balance and equivalent repeated solutions. Run only after the original 011 output report and plan freeze exist. Preserve original experiment inputs and results.
