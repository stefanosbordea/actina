# Archived forecast intake

An isolated input experiment for Stefanos's next model. No model is trained, no schedule is generated, and original files stay unchanged.

`protocol.json` records the pinned model, target period and limits before the full download. `requests.json` records exact URLs, HTTP results and response hashes; raw JSON and headers remain beside it, including failed responses. `time-checks.json` compares the original weather CSV with three small archive samples and a winter UTC control. `intake-summary.json` counts every target hour and null without imputing or selecting favourable weather.

The original CSV's naive labels match a fixed **UTC+03:00** in sampled winter, summer and transition days. This is recovered sample evidence, not a claim that Cyprus civil time has no DST. Do not attach `ZoneInfo('Asia/Nicosia')` to these labels. Forecast response timestamps are UTC epochs. A prediction-origin row joins forecast features at its target, **origin + 24 hours**; day1/day2 fields have nominal leads of 24/48 hours respectively. Day2 therefore has a nominal extra day before the prediction origin, but historical publication availability remains unverified.

Radiation is a preceding-hour mean; cloud cover is an instantaneous value. The full UTC request pads the local date range; padding stays in the raw response. Preserve the original radiation target and threshold. Do not substitute a new archive response for retained truth.

Run once, from the repository root:

```sh
python3 app/experiments/nwp-archive-001/fetch.py
```

The script refuses to overwrite a retained run. It uses seven serial public-API requests with a pause between them. A rerun requires a new experiment directory. Acquisition is not evidence of improved accuracy, a verified operational forecast vintage or plant benefit. The existing test period is already inspected.
