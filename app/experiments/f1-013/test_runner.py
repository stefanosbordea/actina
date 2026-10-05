"""Synthetic loader, identity, delayed scoring and failure-retention fixtures."""
from contextlib import ExitStack
import csv
from datetime import datetime, timedelta
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np
import run


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.here = self.root / 'app/experiments/f1-013'
        self.previous = self.root / 'app/experiments/physical-012'
        self.here.mkdir(parents=True)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name, value in dict(ROOT=self.root, HERE=self.here, PREVIOUS=self.previous,
                                DAYS=dict(validation=2, test=2), POOL_DAYS=dict(validation=64, test=64),
                                CUTOFF=dict(validation=datetime(2020, 3, 5), test=datetime(2020, 3, 5)),
                                HOURS=dict(validation=4, test=4), COMMON=dict(validation=3, test=3)).items():
            self.stack.enter_context(patch.object(run, name, value))
        self.targets = [datetime(2020, 1, 1) + timedelta(hours=i) for i in range(67 * 24)]
        self.origins = [t - timedelta(hours=24) for t in self.targets]
        self.forecast = np.asarray([400 + 10 * t.hour for t in self.targets], dtype=float)
        self.positions = np.arange(65 * 24, 67 * 24).reshape(2, 24)
        self.pool = np.arange(64 * 24).reshape(64, 24)
        self.raw = self.forecast[self.positions]
        self.metadata = []
        for p in self.positions:
            day = self.targets[p[0]]
            issue = day - timedelta(days=1)
            self.metadata.append(dict(day=str(day.date()), issue_time=str(issue),
                issue_utc=(issue - timedelta(hours=3)).isoformat() + '+00:00',
                interval_start=str(day - timedelta(hours=1)), interval_end=str(day + timedelta(hours=23)),
                maximum_nwp_nominal_time=str(issue - timedelta(hours=1)),
                maximum_selected_source_time=str(self.targets[self.pool[-1, -1]])))
        for stage in run.STAGES:
            directory = self.previous / 'result' / stage
            directory.mkdir(parents=True)
            np.savez(directory / 'plans.npz', target_positions=self.positions, raw_forecast_ghi=self.raw)
            np.savez(directory / 'bank.npz', pool_source_positions=self.pool,
                pool_source_target_time=np.asarray([[str(self.targets[i]) for i in day] for day in self.pool]),
                pool_source_days=np.asarray([str(self.targets[p[0]].date()) for p in self.pool]),
                pool_nwp=self.forecast[self.pool], pool_residuals=np.zeros((2, 64, 24)),
                recency_pool_indices=np.arange(64), conditional_pool_indices=np.tile(np.arange(64), (2, 1)))
            scenarios = np.broadcast_to(self.raw[:, None, None, None, None, :], (2, 2, 2, 2, 64, 24)).copy()
            np.savez(directory / 'scenario-replay.npz', unclipped_ghi=scenarios)
            self.csv(directory / 'plan-metadata.csv', self.metadata)
        self.refresh_manifests()

    def csv(self, path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

    def refresh_manifests(self):
        files = {str(p.relative_to(self.previous / 'result')): run.sha(p)
                 for p in (self.previous / 'result').rglob('*') if p.is_file() and p.suffix != '.json'}
        run.save(self.previous / 'result/planning-freeze.json', dict(files_sha256=files))
        run.save(self.previous / 'result/outputs.json', files)

    def mutate(self, filename, member, change):
        path = self.previous / 'result/validation' / filename
        with np.load(path, allow_pickle=False) as source:
            content = {k: source[k] for k in source.files}
        content[member] = change(content[member].copy())
        np.savez(path, **content)
        self.refresh_manifests()

    def package(self):
        return run.forecast_package('validation', self.targets, self.forecast)

    def test_forecast_identity_and_padding_are_retained(self):
        package = self.package()
        self.assertEqual(package['scenarios'].shape, (2, 2, 2, 64, 24))
        np.testing.assert_array_equal(package['positions'], self.positions)
        self.assertEqual(package['selected_days'][0][0][0], '2020-01-01')
        diagnostic = run.complexity(package)
        self.assertEqual(diagnostic['recency']['canonical_subsets'], 2)
        self.assertEqual(diagnostic['conditional']['max_uncertain_hours'], 0)

    def test_tampered_manifest_refused(self):
        path = self.previous / 'result/validation/plans.npz'
        path.write_bytes(path.read_bytes() + b'tampered')
        with self.assertRaisesRegex(ValueError, 'pre-scoring identity'):
            self.package()

    def test_duplicate_target_refused(self):
        def duplicate(a):
            a[0, 1] = a[0, 0]
            return a
        self.mutate('plans.npz', 'target_positions', duplicate)
        with self.assertRaisesRegex(ValueError, 'duplicate positions'):
            self.package()

    def test_missing_target_refused(self):
        self.mutate('plans.npz', 'target_positions', lambda a: a[:, :-1])
        with self.assertRaisesRegex(ValueError, 'Target position dimensions'):
            self.package()

    def test_source_day_identity_refused(self):
        def invalid(a):
            a[0] = '2020-01-02'
            return a
        self.mutate('bank.npz', 'pool_source_days', invalid)
        with self.assertRaisesRegex(ValueError, 'complete-day identity'):
            self.package()

    def test_source_cutoff_refused(self):
        with patch.object(run, 'CUTOFF', dict(validation=datetime(2020, 3, 4), test=datetime(2020, 3, 5))):
            with self.assertRaisesRegex(ValueError, 'Historical cutoff'):
                self.package()

    def test_nonfinite_scenario_refused(self):
        def invalid(a):
            a[0, 0, 0, 0, 0, 0] = np.nan
            return a
        self.mutate('scenario-replay.npz', 'unclipped_ghi', invalid)
        with self.assertRaisesRegex(ValueError, 'Scenario dimensions or values'):
            self.package()

    def test_unsorted_source_ids_refused(self):
        self.mutate('bank.npz', 'conditional_pool_indices', lambda a: a[:, ::-1])
        with self.assertRaisesRegex(ValueError, 'Canonical selected days'):
            self.package()

    def test_source_reconstruction_refused(self):
        self.mutate('scenario-replay.npz', 'unclipped_ghi', lambda a: a + 1)
        with self.assertRaisesRegex(ValueError, 'scenario reconstruction'):
            self.package()

    def test_exact_original_masks_and_all_comparator_daily_metrics(self):
        positions = self.positions.flat
        selected = [positions[i] for i in (1, 22, 26, 47)]
        weather = [650.0 if i in selected[:2] else 400.0 for i in range(len(self.targets))]
        satellite = list(weather)
        satellite[selected[1]] = None
        originals = [dict(time=str(self.origins[i]), actual=weather[i], predicted=650.0, baseline=400.0) for i in selected]
        self.csv(self.root / 'eval/cv_predictions.csv', originals)
        membership = [dict(feature_time=str(self.origins[i]), target_time=str(self.targets[i]),
            weather_w_m2=weather[i], satellite_w_m2='' if satellite[i] is None else satellite[i],
            satellite_available=int(satellite[i] is not None)) for i in selected]
        self.csv(self.root / 'app/experiments/f1-009/result/validation-reference-membership.csv', membership)
        for experiment, arm, weather_field in (('008', 'consensus_two_source', 'weather_actual_w_m2'), ('009', 'joint', 'weather_w_m2')):
            base = self.root / f'app/experiments/f1-{experiment}/result'
            selection = {'selected_augmented_arm' if experiment == '008' else 'selected_arm': arm,
                         'policies': {arm: {'policy': {'kind': 'correction', 'lower': 0.5, 'upper': 0.65}}}}
            base.mkdir(parents=True, exist_ok=True)
            run.save(base / 'validation-selection.json', selection)
            self.csv(base / f'predictions/validation-{arm}.csv', [dict(feature_time=str(self.origins[i]), target_time=str(self.targets[i]),
                probability=int(self.forecast[i] > 600), **{weather_field: weather[i]}, satellite_w_m2='' if satellite[i] is None else satellite[i],
                nwp_positive=int(self.forecast[i] > 600), predicted_positive=int(self.forecast[i] > 600)) for i in selected])
        package = self.package()
        calls = np.broadcast_to((package['raw'] > 600)[:, None, :], (2, 5, 24)).copy()
        out = self.here / 'synthetic-score'
        (out / 'validation').mkdir(parents=True)
        report = run.score_stage('validation', self.origins, self.targets, self.forecast, package, calls, weather, satellite, out)
        self.assertEqual((report['hours'], report['common_hours'], report['padding_hours'], report['missing_satellite_hours']), (4, 3, 44, 1))
        self.assertEqual(report['metrics']['raw_nwp']['weather_full']['tp'], 1)
        self.assertEqual(report['metrics']['raw_nwp']['weather_full']['fp'], 1)
        self.assertEqual(report['metrics']['raw_nwp']['satellite_common']['tp'], 0)
        self.assertEqual(len(json.loads((out / 'validation/daily-metrics.json').read_text())), 2 * 3 * 9)
        membership[0]['satellite_available'] = 0
        self.csv(self.root / 'app/experiments/f1-009/result/validation-reference-membership.csv', membership)
        with self.assertRaisesRegex(ValueError, 'Frozen reference mask values'):
            run.score_stage('validation', self.origins, self.targets, self.forecast, package, calls, weather, satellite, out)

    def test_undefined_observed_scores_remain_null(self):
        self.assertIsNone(run.event_metrics([False], [False])['f1'])
        self.assertIsNone(run.event_metrics([True], [False])['precision'])
        self.assertEqual(run.direct_expected(np.zeros((2, 2, 1), dtype=bool), [False])[0]['f1'], Fraction(1))

    def test_input_hash_changed_refused(self):
        sample = self.root / 'sample'
        sample.write_text('original')
        run.save(self.previous / 'inputs.json', {})
        with patch.object(run, 'input_paths', return_value=[sample]):
            run.freeze_inputs()
            run.verify_inputs()
            sample.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Changed frozen input'):
                run.verify_inputs()

    def test_previous_source_hash_disagreement_refused(self):
        sample = self.root / 'sample'
        sample.write_text('changed from 012')
        run.save(self.previous / 'inputs.json', {'sample': 'old012hash'})
        with patch.object(run, 'input_paths', return_value=[sample]):
            run.freeze_inputs()
            with self.assertRaisesRegex(ValueError, 'Changed 012 pinned source'):
                run.verify_inputs()

    def test_runtime_failure_retained_without_scoring(self):
        (self.here / 'PROTOCOL.md').write_text('synthetic')
        (self.here / 'inputs.json').write_text('{}')
        with patch.object(run, 'verify_inputs', return_value={}), patch.object(run, 'features', side_effect=lambda: time.sleep(0.1)), \
             patch.object(run, 'BUDGET_SECONDS', 0.01), patch.object(run, 'references') as scoring:
            out = self.here / 'timeout-receipt'
            with self.assertRaises(TimeoutError):
                run.execute(out)
            scoring.assert_not_called()
        receipt = json.loads((out / 'execution-receipt.json').read_text())
        self.assertEqual(receipt['exit_code'], 1)
        self.assertFalse(receipt['outcome_scoring_started'])
        self.assertEqual(receipt['error_type'], 'TimeoutError')
        self.assertTrue((out / 'outputs.json').exists())

    def test_both_periods_frozen_before_first_scoring_read(self):
        (self.here / 'PROTOCOL.md').write_text('synthetic')
        (self.here / 'inputs.json').write_text('{}')
        out = self.here / 'stage-order'
        passed = dict(passed=False, all_six_strict=False)
        scored = dict(comparisons={m: {'raw_nwp': passed} for m in run.METHODS[1:]})
        def first_reference_read(*args):
            manifest = json.loads((out / 'planning-freeze.json').read_text())['files_sha256']
            for stage in run.STAGES:
                for name in ('calls.npz', 'calls.csv', 'decisions.jsonl.gz'):
                    self.assertEqual(manifest[f'{stage}/{name}'], run.sha(out / stage / name))
            events = [json.loads(line)['event'] for line in (out / 'events.jsonl').read_text().splitlines()]
            self.assertLess(events.index('ALL_DECISIONS_FROZEN'), events.index('SCORING_REFERENCES_OPENED'))
            return [], []
        with patch.object(run, 'verify_inputs', return_value={}), patch.object(run, 'features', return_value=(self.origins, self.targets, self.forecast)), \
             patch.object(run, 'references', side_effect=first_reference_read), patch.object(run, 'score_stage', return_value=scored):
            run.execute(out)
        self.assertEqual(json.loads((out / 'execution-receipt.json').read_text())['status'], 'COMPLETE')


if __name__ == '__main__':
    unittest.main()
