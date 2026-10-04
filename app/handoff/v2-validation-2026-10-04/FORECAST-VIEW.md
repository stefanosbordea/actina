# Forecast view verification

Checked on 4 October 2026. Open `/forecast.html` from the homepage's Forecasts link.

The default curve and event calls use Stefanos's supplied v2 CSV. The viewer joins his exact next-day cloud input from the pinned source feature export. All 3,566 validation hours remain included, including the first five and last nine hours. The original schedule, water quantities and costs are unchanged.

The two weather lines are selectable controls with different sources. The optional 562 threshold changes event calls only. The 008 option shows its saved binary calls and never supplies a radiation curve. Research 016 is not a product replacement.

Executed checks:

- Python tool suite: 28 tests passed, including seven forecast data tests.
- Browser-independent interaction suites: four schedule, seven benchmark and eight forecast tests passed.
- Saved calibration and weather-source audits passed.
- Static site build passed.
- Built-in browser: desktop preview, mobile viewport measured at 375 pixels with no document overflow, homepage navigation, weather selection, 008 selection and the partial first date checked. No browser console errors were observed.
- Model/data/eval compared with the original protected commit and remained unchanged.

Mobile navigation now wraps within its container instead of extending beyond the page margin. The browser's attempted narrower override still measured 375 pixels, so this review does not claim a 320-pixel browser check.

Reproduce the data and interaction checks from the repository root:

```sh
python -m unittest discover -s app/tools -p 'test_*.py' -v
node app/tools/test_demo.mjs
node app/tools/test_benchmark_ui.mjs
node app/tools/test_forecast_demo.mjs
python app/handoff/v2-calibration-2026-10-04/review.py --check
python app/handoff/v2-validation-2026-10-04/weather-source/check.py --check
node app/build.mjs
```

Browser observations are manual verification through the built-in browser, not a claim of automated layout coverage. Publication receipts are separate from these local checks.
