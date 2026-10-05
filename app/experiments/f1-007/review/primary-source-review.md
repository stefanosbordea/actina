# Joint-reference target: scientific review

Reviewed full PDF methods, equations and selected experiments on 2026-10-04. This is prior art and a bounded hypothesis, not a novelty or local-performance claim. Protocol reviewed: `f6950483c4bc3864c4a902d9b1e230681011c634d02bd7474c025cec4aa461fc`.

1. **Raykar et al., Learning From Crowds (2010).** [Full PDF](https://jmlr.org/papers/volume11/raykar10a/raykar10a.pdf). Section 1.1, printed p.1299, already describes averaging noisy labels into soft targets. Sections 2.4–2.5, pp.1301–1303, derive a latent-label likelihood with conditional independence assumptions. Section 6.1.2, pp.1311–1312, tests against biopsy evidence; Section 7, p.1319, explicitly discusses correlated errors and instance-dependent reference reliability. Our two-product average does not implement their latent-label estimator or identify which reference is correct.

2. **Hinton, Vinyals and Dean, Distilling the Knowledge in a Neural Network (2015).** [Full PDF](https://arxiv.org/pdf/1503.02531). Section 2, PDF pp.2–3, uses soft-target cross-entropy; Eq.2 gives the probability-minus-target gradient. Section 4, pp.4–5, and Table 1 compare a student with the teacher ensemble. This establishes relevant soft-supervision precedent. Their teacher probabilities and known speech labels differ from our two thresholded irradiance products; the paper does not justify our references' equal reliability.

3. **Pfeifroth et al., SARAH-3 (2024).** [Full PDF](https://essd.copernicus.org/articles/16/5243/2024/essd-16-5243-2024.pdf). Section 2, p.5245, combines satellite cloud albedo with clear-sky radiative transfer. Sections 2.5.1–2.5.3, p.5249, document ECMWF IFS auxiliary inputs for the 2021-onward interim product, including water vapour and ozone. Sections 3.1–3.2 and Tables 2–4, pp.5251–5253, validate against surface networks at stated temporal resolutions. Satellite derivation therefore supplies a distinct reference, not proven independent errors or direct local hourly ground truth. Shared model inputs prevent inferring statistical independence merely from separate APIs.

4. **Schulz, El Ayari, Lerch and Baran, Post-processing numerical weather prediction ensembles for probabilistic solar irradiance forecasting (2021).** [Full PDF](https://arxiv.org/pdf/2101.06717). Sections 3.1–3.2, PDF pp.6–10, define zero-censored logistic post-processing; Eqs.3.9–3.10, pp.10–11, distinguish distributional CRPS from threshold Brier score. Section 4.1, pp.12–15, evaluates skill, interval coverage and probability calibration separately. Our event head is neither their distribution model nor automatically calibrated: improving F1 does not establish reliable probabilities or operating benefit.

## What the fixed target optimizes

For binary weather and satellite events W and S, let z=(W+S)/2 and L(p,y)=-y log(p)-(1-y) log(1-p). Direct algebra gives L(p,z)=[L(p,W)+L(p,S)]/2. On paired rows, unrestricted expected-log-loss minimization yields p*(x)=[P(W=1|x)+P(S=1|x)]/2, the mean reference frequency, not an identified physical-event probability. Correlated or shared biases can remain.

Missing satellite rows use z=W. Thus N paired rows and M missing rows contribute effective weather weight N/2+M and satellite weight N/2. Equal weighting applies within paired rows, not globally. Under a logit, the gradient is p-z; disagreement z=0.5 pulls toward uncertainty rather than selecting a winner.

## Implementable check and decision

007 tests the fixed target with the unchanged 006 features, capacities and purged hours. Applying the same joint validation gate to saved weather-only predictions separates a target change from a cutoff-policy change. This addresses the observed weather/SARAH reversal without inventing new inputs or true labels.

Run one descriptive check on each purged TRAIN bank: exact weather/SARAH 2×2 event counts, missing counts by target month, and effective source-weight sums. Reconstruct every soft label and reject joins or weighting that disagree with the rule. Retain this report without tuning from it. Separate reference scores, all failed candidates and the NWP fallback remain necessary; already-inspected test results cannot validate live superiority.
