# Satellite reference intake

Three pinned EUMETSAT SARAH3 samples returned **72 of 72 hourly values**, with no nulls, for the nearest returned cell at 34.75° N, 32.4° E. These are availability checks, not model scores.

The dates were fixed before fetching: 10 December 2025, 3 July 2026, and 1 October 2026. UTC timestamps, preceding-hour mean GHI, units, hourly continuity, nonnegative finite values and response hashes passed. Raw responses, headers, retrieval times and the pre-request protocol are in `result/`. The command completed with exit status 0.

SARAH3 is satellite-derived irradiance, not a Paphos ground sensor. It offers a different reference from the weather-model reconstruction used in the original benchmark. Its retrieval assumptions, spatial averaging and Open-Meteo's conversion to hourly averages still matter. These three days do not establish full-period coverage or statistical independence from every forecast input. No original labels were replaced and no forecast was scored against these samples.

Source: [Open-Meteo satellite documentation](https://open-meteo.com/en/docs/satellite-radiation-api). Dataset attribution: Pfeifroth et al., [Surface Radiation Data Set — Heliosat, Edition 3](https://doi.org/10.5676/EUM_SAF_CM/SARAH/V003), EUMETSAT CM SAF, accessed through Open-Meteo. The provider exposes the product as `eumetsat_sarah3`; a more precise upstream processing-version identifier is not supplied in these API responses.

Reproduce into a new directory:

```sh
python3 app/experiments/satellite-intake-001/fetch.py --output app/experiments/satellite-intake-001/result-new
```

The script refuses an existing output directory. A refreshed source response may differ; retained bytes and hashes identify this particular intake. This command only requests three public samples and performs no training or publication.
