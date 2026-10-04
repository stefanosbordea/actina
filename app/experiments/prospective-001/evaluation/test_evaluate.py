"""Constructed cases; no future reference download or accuracy measurement."""
import copy
from datetime import timedelta
from email.message import Message
import importlib.util
import json
import io
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('evaluator', HERE / 'evaluate.py')
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)


def fixture():
    targets, candidates, reference = [], {name: {} for name in e.CANDIDATES}, {}
    first = e.GATES['primary'] - timedelta(hours=71)
    for i in range(24):
        at, k = first + timedelta(hours=i), i % 4
        stamp = int(at.timestamp())
        q = [601, 600, 800, 0][k]
        targets.append({'interval_start_utc': (at - timedelta(hours=1)).isoformat(),
                        'valid_time_utc': at.isoformat(), 'shortwave_radiation_w_m2': q,
                        'start_lead_seconds': 90000 + 3600*i, 'valid_time_lead_seconds': 93600 + 3600*i})
        reference[stamp] = [600, 601, 700, 0][k]
        candidates['captured_raw'][stamp] = {'point_w_m2': q, 'probability': int(q > 600)}
        for name in e.CANDIDATES[1:]:
            candidates[name][stamp] = {'point_w_m2': [610, 610, 610, 0][k], 'probability': [.5, .75, 1, 0][k],
                                       'interval_low_w_m2': [600, 601, 600, 0][k], 'interval_high_w_m2': [600, 601, 699, 0][k]}
    return targets, candidates, reference


def response(reference):
    return json.dumps({'utc_offset_seconds': 0, 'hourly_units': {'time': 'unixtime', 'shortwave_radiation': 'W/m²'},
                       'hourly': {'time': list(reference), 'shortwave_radiation': list(reference.values())}}).encode()


def copy_package(root):
    target = root / 'app/experiments/prospective-001/evaluation'
    target.mkdir(parents=True)
    for name in ('input-lock.json', 'PROTOCOL.md', 'AMENDMENT-001.md', 'frozen-inputs.zip'):
        shutil.copyfile(HERE / name, target / name)
    return target


class EvaluationTests(unittest.TestCase):
    def test_offline_http_workflow_keeps_complete_incomplete_and_invalid_attempts(self):
        targets, candidates, reference = fixture()
        for case in ('complete', 'incomplete', 'duplicate'):
            payload = json.loads(response(reference))
            if case == 'incomplete': payload['hourly']['shortwave_radiation'][0] = None
            if case == 'duplicate': payload['hourly']['time'][1] = payload['hourly']['time'][0]
            raw = json.dumps(payload).encode()
            def fake_open(request, timeout):
                stream = io.BytesIO(raw)
                stream.status = 200; stream.headers = Message(); stream.geturl = lambda: request.full_url
                return stream
            frozen = ({'targets': {'primary': {'intervals': targets}}}, {'primary': candidates}, {'files_sha256': {}})
            with tempfile.TemporaryDirectory() as directory, patch.object(e, 'now', return_value=e.GATES['primary']), patch.object(e, 'load_frozen', return_value=frozen), patch.object(e.urllib.request, 'urlopen', side_effect=fake_open) as network:
                output = Path(directory) / 'attempt'
                if case == 'duplicate':
                    with self.assertRaisesRegex(ValueError, 'duplicate'): e.run('primary', output)
                    self.assertFalse((output / 'assessment.json').exists())
                    self.assertTrue((output / 'failure.json').exists())
                else:
                    receipt = e.run('primary', output)
                    self.assertEqual(receipt['status'], 'COMPLETE' if case == 'complete' else 'INCOMPLETE')
                    result = e.decode((output / 'assessment.json').read_bytes())
                    self.assertEqual(result['common_hour_diagnostic']['n'], 24 if case == 'complete' else 23)
                self.assertEqual(len(e.decode((output / 'rows.json').read_bytes())), 24)
                self.assertEqual((output / 'reference-response.json').read_bytes(), raw)
                network.assert_called_once()
                self.assertIn('models=eumetsat_sarah3', network.call_args.args[0].full_url)

    def test_integrity_failure_prevents_request_after_time_gate(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(e, 'now', return_value=e.GATES['primary']), patch.object(e, 'load_frozen', side_effect=ValueError('Frozen bytes changed')), patch.object(e.urllib.request, 'urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'changed'): e.run('primary', Path(directory) / 'attempt')
            network.assert_not_called()

    def test_gate_before_and_exact_boundary_for_both_sets(self):
        for name, boundary in e.GATES.items():
            with self.assertRaisesRegex(ValueError, 'Not eligible'):
                e.gate(name, boundary - timedelta(microseconds=1))
            e.gate(name, boundary)

    def test_early_attempt_never_loads_inputs_or_network_and_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(e, 'now', return_value=e.GATES['primary'] - timedelta(seconds=1)), patch.object(e, 'load_frozen') as load, patch.object(e.urllib.request, 'urlopen') as network:
            output = Path(directory) / 'attempt'
            with self.assertRaisesRegex(ValueError, 'Not eligible'):
                e.run('primary', output)
            load.assert_not_called(); network.assert_not_called()
            self.assertEqual(e.decode((output / 'failure.json').read_bytes())['status'], 'REFUSED_EARLY')
            with self.assertRaises(FileExistsError):
                e.run('primary', output)

    def test_hand_derived_strict_threshold_metrics_and_inclusive_intervals(self):
        result = e.assess(*fixture())
        self.assertEqual(result['status'], 'COMPLETE')
        raw = result['complete_set_metrics']['captured_raw']['metrics']
        for key in ('tp', 'tn', 'fp', 'fn'):
            self.assertEqual(raw[key], 6)
        self.assertEqual(raw['mae_w_m2'], 25.5)
        self.assertAlmostEqual(raw['rmse_w_m2'], math.sqrt(2500.5))
        self.assertEqual(raw['brier'], .5)
        analogue = result['complete_set_metrics']['analogue_raw']
        self.assertEqual([analogue['metrics'][k] for k in ('tp', 'tn', 'fp', 'fn')], [12, 12, 0, 0])
        self.assertEqual(analogue['metrics']['mae_w_m2'], 27.25)
        self.assertEqual(analogue['metrics']['mean_error_w_m2'], -17.75)
        self.assertAlmostEqual(analogue['metrics']['rmse_w_m2'], math.sqrt(2070.25))
        self.assertEqual(analogue['metrics']['brier'], .078125)
        self.assertEqual(analogue['intervals'], {'coverage_90': .75, 'mean_width_w_m2': 24.75})
        self.assertIsNone(result['complete_set_metrics']['captured_raw']['intervals'])

    def test_null_and_absent_reference_are_different_original_rows_retained(self):
        targets, candidates, reference = fixture()
        keys = list(reference); reference[keys[0]] = None; del reference[keys[1]]
        result = e.assess(targets, candidates, e.parse_reference(response(reference)))
        self.assertEqual(result['status'], 'INCOMPLETE')
        self.assertIsNone(result['complete_set_metrics'])
        self.assertEqual(len(result['rows']), 24)
        self.assertEqual(result['common_hour_diagnostic']['n'], 22)
        self.assertEqual([row['reference_status'] for row in result['rows'][:2]], ['null', 'absent'])
        self.assertTrue(all(item['n'] == 22 for item in result['common_hour_diagnostic']['candidates'].values()))

    def test_unknown_forecast_remains_unknown_for_every_candidate(self):
        targets, candidates, reference = fixture(); stamp = next(iter(reference))
        targets[0]['shortwave_radiation_w_m2'] = None
        for name in e.CANDIDATES:
            candidates[name][stamp] = {key: None for key in candidates[name][stamp]}
        result = e.assess(targets, candidates, reference)
        self.assertEqual(result['common_hour_diagnostic']['n'], 23)
        self.assertEqual(result['rows'][0]['exclusion_reasons'], ['forecast_null'])
        self.assertIsNone(result['rows'][0]['candidates']['captured_raw']['probability'])

    def test_partial_null_invalid_probability_and_interval_are_integrity_failures(self):
        for field, value in [('probability', None), ('probability', True), ('probability', 1.01), ('point_w_m2', float('inf')), ('interval_low_w_m2', 900)]:
            targets, candidates, reference = fixture()
            candidates['analogue_raw'][next(iter(reference))][field] = value
            with self.assertRaises(ValueError): e.assess(targets, candidates, reference)

    def test_no_candidate_specific_or_duplicate_target_subset(self):
        targets, candidates, reference = fixture()
        del candidates['analogue_solar'][next(iter(reference))]
        with self.assertRaisesRegex(ValueError, 'Candidate keys'): e.assess(targets, candidates, reference)
        targets, candidates, reference = fixture(); targets[1] = targets[0]
        with self.assertRaisesRegex(ValueError, '24 consecutive'): e.assess(targets, candidates, reference)

    def test_reference_rejects_duplicates_invalid_units_numbers_and_clock(self):
        _, _, reference = fixture(); base = json.loads(response(reference))
        mutations = [lambda x: x['hourly']['time'].__setitem__(1, x['hourly']['time'][0]),
                     lambda x: x['hourly_units'].__setitem__('shortwave_radiation', 'kWh'),
                     lambda x: x.__setitem__('utc_offset_seconds', 10800),
                     lambda x: x['hourly']['time'].__setitem__(0, x['hourly']['time'][0] + 1),
                     lambda x: x['hourly']['shortwave_radiation'].__setitem__(0, True),
                     lambda x: x['hourly']['shortwave_radiation'].__setitem__(0, -1),
                     lambda x: x['hourly']['shortwave_radiation'].__setitem__(0, float('nan'))]
        for mutate in mutations:
            value = copy.deepcopy(base); mutate(value)
            with self.assertRaises(ValueError): e.parse_reference(json.dumps(value).encode())

    def test_undefined_metrics_and_empty_intersection(self):
        targets, candidates, reference = fixture()
        result = e.assess(targets, candidates, {})
        self.assertTrue(all(item['metrics'] is None for item in result['common_hour_diagnostic']['candidates'].values()))
        zero = {'reference_w_m2': 0, 'candidates': {'captured_raw': {'point_w_m2': 0, 'probability': 0}}}
        scores = e.metrics([zero], 'captured_raw')
        for key in ('precision', 'recall', 'f1'):
            self.assertIsNone(scores['metrics'][key]); self.assertEqual(scores['classification_denominators'][key], 0)

    def test_frozen_chain_and_corruption(self):
        selection, candidates, lock = e.load_frozen()
        self.assertEqual(len(candidates['primary']['analogue_raw']), 24)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = copy_package(root)
            self.assertEqual(e.load_frozen(root), (selection, candidates, lock))
            for name in ('frozen-inputs.zip', 'input-lock.json', 'AMENDMENT-001.md'):
                target = package / name; original = target.read_bytes(); target.write_bytes(original + b' ')
                with self.assertRaisesRegex(ValueError, 'changed'): e.load_frozen(root)
                target.write_bytes(original)

    def test_working_inputs_can_change_or_be_absent_without_changing_frozen_predictions(self):
        expected = e.load_frozen()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); copy_package(root)
            # Only the archive package exists; even absent working inputs are unnecessary.
            self.assertEqual(e.load_frozen(root), expected)
            for name in expected[2]['files_sha256']:
                target = root / name; target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'Legitimate replacement working data, unrelated to the frozen forecast.\n')
            self.assertEqual(e.load_frozen(root), expected)

    def test_member_hashes_are_checked_even_with_a_new_archive_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); package = copy_package(root)
            with zipfile.ZipFile(package / 'frozen-inputs.zip') as archive:
                members = [(info, archive.read(info.filename)) for info in archive.infolist()]
            with zipfile.ZipFile(package / 'frozen-inputs.zip', 'w') as archive:
                for info, raw in members:
                    archive.writestr(info, raw + b' ' if info.filename == 'data/features.csv' else raw)
            with patch.object(e, 'ARCHIVE_SHA', e.sha((package / 'frozen-inputs.zip').read_bytes())):
                with self.assertRaisesRegex(ValueError, 'Frozen member bytes changed: data/features.csv'):
                    e.load_frozen(root)

    def test_exact_archive_member_set_and_duplicate_guard(self):
        for kind in ('missing', 'extra', 'duplicate'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); package = copy_package(root)
                with zipfile.ZipFile(package / 'frozen-inputs.zip') as archive:
                    members = [(info, archive.read(info.filename)) for info in archive.infolist()]
                with zipfile.ZipFile(package / 'frozen-inputs.zip', 'w') as archive, warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    for index, (info, raw) in enumerate(members):
                        if kind != 'missing' or index != 0: archive.writestr(info, raw)
                    if kind == 'extra': archive.writestr('unapproved.txt', b'extra')
                    if kind == 'duplicate': archive.writestr(members[0][0], members[0][1])
                with patch.object(e, 'ARCHIVE_SHA', e.sha((package / 'frozen-inputs.zip').read_bytes())):
                    with self.assertRaisesRegex(ValueError, 'exact locked member set, without duplicates'):
                        e.load_frozen(root)


if __name__ == '__main__':
    unittest.main()
