# V2 integration and interface checks

4 October 2026. The historical forecast viewer defaults to audited 019 expanded event calls, paired with the frozen 016 refit radiation curve used by that correction. Original supplied v2 and 008 remain available. All 3,566 validation hours are retained. The scheduler, cost inputs and plan values are unchanged.

019 validation: 270 true positives, 17 false alarms, 36 misses and 3,243 true negatives. Precision 94.077%, recall 88.235%, F1 91.062%. Against 008 this is four fewer false alarms and one extra miss. The descriptive F1 difference interval crosses zero. No fresh test result or field-performance claim is made.

The explicit merge preserves all seven upstream NWP additions and all 17 pre-existing root model/data/eval files. See the adjacent source integration receipt and reproducer.

## Executed checks

- Python data and comparison suite: 29 passed.
- Website, benchmark, forecast and workspace-home interface tests: 27 passed.
- Final animation override change: all eight workspace-home tests passed again.
- Independent 017–019 model audits and 018 past-observation mutation audit passed, retained with each experiment.
- Static build completed successfully. Whitespace check passed.
- Built-in browser, actual viewport 375 × 812: no horizontal overflow on workspace home or forecast view. Simulation controls have 16px top padding. The overlapping visible legend is removed while its accessible label remains.
- Workspace forecast link opens the new default. Selecting supplied v2 switches both its event scores and numerical curve. The observed noon value changed from 666.0 for the refit to 668.6 W/m² for supplied v2 on 2 May.
- Reduced-motion preference was active. The diagram defaulted to paused. Explicit Play selected the animated SVG fragment and changed the button to Pause. Two captures differed in 1,988 pixels within the diagram, confirming actual rendered motion. Pause restored the static fragment.
- Desktop override requests did not change the actual 375px viewport in this browser session. No new desktop screenshot is claimed for this release. Responsive two-column controls are covered by source review, with mobile rendering inspected directly.

## Reproduce interface checks

From the repository root:

```sh
python -m unittest discover -s app/tools -p 'test_*.py' -v
node --test app/web/test_home_demo.mjs app/tools/test_forecast_demo.mjs app/tools/test_demo.mjs app/tools/test_benchmark_ui.mjs
node app/build.mjs
```

The release workflow also replays saved 017–019 coefficients/heads and past-context invariance without fitting new models. Publication byte checks and the final CI result are recorded separately after deployment.
