# Full papers read, then implemented

The method, equation and experimental-result sections below were read from the actual PDFs on 4 October 2026. These are primary papers, not search-result summaries. Results reported for their datasets do not establish Aktina's performance.

## Solar distribution forecasts

[Gneiting, Lerch and Schulz, Solar Energy 252 (2023), pp. 72–80](https://publikationen.bibliothek.kit.edu/1000155949/150349405).

Read §§2–4, printed pp. 73–78, including Table 2 and equations 2, 5 and 6. The neural quantile method beats the analogue ensemble in mean CRPS at all seven reported US sites, using 2017–2019 training and 2020 evaluation. The normal-distribution network is less well calibrated despite narrower intervals. Temporal scenario generation needs a dependence model; independent hourly error samples do not provide one.

Application: experiment 008 adds a distinct forecast model and measures its contribution with matched controls. A future trajectory experiment should preserve coherent cloud-error sequences and measure schedule consequences. Neither this paper nor a higher F1 proves operational water savings. We are not relabelling a tree classifier as their Bernstein quantile network.

## Censored forecast distributions

[Schulz et al., Post-processing numerical weather prediction ensembles for probabilistic solar irradiance forecasting (2021)](https://arxiv.org/pdf/2101.06717).

Read §§3.1–3.4, §4.1, §4.2 and the conclusion. Equation 3.1 keeps probability mass at zero irradiance; equation 3.3 maps forecast members to distribution location and spread. Equation 3.9 scores the complete distribution. The two case studies differ: calibration improvements do not reliably imply improved point accuracy; reported gains vary by location and forecast range. Clear-sky normalization is not automatically better (§4.1).

Application: use GFS/ECMWF disagreement as a testable feature, retain individual model identity, and report the binary decision metrics separately. Experiment 008's two correction thresholds are a local engineering hypothesis intended to address the observed false-alarm failure, not a proven guarantee from this paper.

## Executions linked to the reading

- `../f1-007/`: weather/satellite soft supervision; measured recall gains with precision regressions. Rejected as an all-metric improvement. Exact training-source disagreement and separate PDF evidence are in its independent review.
- `../nwp-alternative-001/`: one historical NOAA GFS request; radiation is complete. Eight invalid cloud percentages are preserved, and the entire cloud column is excluded from the declared radiation-only subset.
- `../f1-008/`: frozen source ablation and confidence-directed corrections. Its protocol, inputs and eventual execution receipt determine what actually ran; this note does not assert a successful result.
