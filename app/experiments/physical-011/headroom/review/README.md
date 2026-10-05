# Independent bound review

PASS, exit0. Re-solved all1132 reference/day/objective bounds using explicit inventory variables and HiGHS interior-point. The original uses cumulative inventory constraints and dual simplex. Maximum objective difference is9.09e-13 in native units. All4528 signed gaps and32 summaries reconstruct on139validation and144test common days.

Cost and energy objectives remain separate.267 of566 paired oracle schedules differ. An energy-optimal schedule can cost€431.2849 more than the cost optimum. The saved cost optima also reach the energy minimum on these particular trajectories within roundoff. This observed coincidence is not an equivalence of the optimization problems.

Twenty negative gaps are preserved, the smallest−1.82e-12. They are numerical residuals within the declared tolerance, not schedules beating the lower bound.

The test mean cost gap is€16.97 against weather and€27.82 against satellite for raw-point schedules. Shuffled schedules retain€8.31 and€19.43 respectively. These gaps use perfect future information. They are upper limits on further improvement within this illustrative model, not promised forecast improvements, operating policies or field savings.

`check.py` imports neither production optimizer nor headroom helper. The executed command, exit and hashes are in `execution-001.json`. `membership-identity.json` verifies the two original cohort CSVs against the frozen011 manifest without claiming an additional numerical run.
