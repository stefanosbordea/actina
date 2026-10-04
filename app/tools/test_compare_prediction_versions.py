import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compare_prediction_versions import ROOT, compare_versions, predictions, write_report


class VersionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.start = datetime(2026, 1, 1)

    def csv(self, name, rows, header=None, offset=0):
        path = self.root / name
        header = header or ['time', 'actual', 'predicted', 'baseline']
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            for index, values in enumerate(rows):
                writer.writerow([str(self.start + timedelta(hours=index + offset)), *values])
        return path

    def compare(self, incoming, original, **kwargs):
        return compare_versions(incoming, original, model_id='Stefanos nwp-features validation v2',
                                incoming_time_basis=kwargs.pop('basis', 'feature'),
                                reference_time_basis='feature', **kwargs)

    def test_hand_calculated_threshold_counts_and_raw_column(self):
        rows = [(600, 600, 600), (601, 600, 601), (600, 601, 600), (601, 601, 601)]
        original = self.csv('old.csv', rows)
        incoming = self.csv('new.csv', [(*row, row[0]) for row in rows],
                            ['time', 'actual', 'predicted', 'baseline', 'forecast'])
        result = self.compare(incoming, original)
        model = result['matched']['metrics']['incoming']
        self.assertEqual([model[k] for k in ('true_positive', 'false_positive', 'false_negative', 'true_negative')], [1, 1, 1, 1])
        self.assertEqual([model[k] for k in ('precision', 'recall', 'f1')], [.5, .5, .5])
        self.assertEqual(result['matched']['metrics']['supplied_raw_forecast']['f1'], 1)
        self.assertEqual(result['coverage']['matched_target_times'][0], '2026-01-02 00:00:00')

    def test_declared_target_basis_avoids_double_shift(self):
        rows = [(700, 690, 680), (10, 20, 30)]
        original = self.csv('old.csv', rows)
        target_labeled = self.csv('new.csv', rows, offset=24)
        correct = self.compare(target_labeled, original, basis='target')
        wrong = self.compare(target_labeled, original)
        self.assertEqual(correct['coverage']['matched_hours'], 2)
        self.assertEqual(wrong['coverage']['matched_hours'], 0)
        self.assertEqual(len(wrong['coverage']['missing_original_target_times']), 2)
        self.assertIsNone(wrong['matched']['metrics']['incoming'])
        self.assertFalse(wrong['matched']['comparisons']['retained_original']['assessable'])
        self.assertEqual(wrong['incoming_full_period']['model']['hours'], 2)

    def test_partial_coverage_preserves_missing_and_extra_identities(self):
        original = self.csv('old.csv', [(0, 0, 0)] * 3)
        incoming = self.csv('new.csv', [(0, 0, 0)] * 3, offset=1)
        result = self.compare(incoming, original)
        self.assertEqual(result['coverage']['missing_original_target_times'], ['2026-01-02 00:00:00'])
        self.assertEqual(result['coverage']['extra_incoming_target_times'], ['2026-01-02 03:00:00'])
        self.assertEqual(result['matched']['metrics']['incoming']['hours'], 2)
        self.assertEqual(result['incoming_full_period']['model']['hours'], 3)
        self.assertIn('does not establish full original-period superiority', result['matched']['scope'])

    def test_reject_changed_truth_or_persistence(self):
        original = self.csv('old.csv', [(700, 650, 610)])
        for values in [(701, 650, 610), (700, 650, 611)]:
            with self.subTest(values=values):
                incoming = self.csv('new.csv', [values])
                with self.assertRaisesRegex(ValueError, 'Conflicting'):
                    self.compare(incoming, original)

    def test_duplicate_nonconsecutive_and_nonfinite_rejected(self):
        header = 'time,actual,predicted,baseline\n'
        invalid = [
            '2026-01-01 00:00:00,1,1,1\n2026-01-01 00:00:00,1,1,1\n',
            '2026-01-01 00:00:00,1,1,1\n2026-01-01 02:00:00,1,1,1\n',
            '2026-01-01 00:00:00,NaN,1,1\n',
            '2026-01-01 00:00:00,1,inf,1\n',
            '2026-01-01 00:00:00,1,1,-1\n',
            '2026-01-01 00:00:00+00:00,1,1,1\n',
            '2026-01-01 00:30:00,1,1,1\n',
        ]
        path = self.root / 'bad.csv'
        for body in invalid:
            with self.subTest(body=body):
                path.write_text(header + body)
                with self.assertRaises(ValueError):
                    predictions(path, 'feature')
        path.write_text(header.rstrip('\n') + ',forecast\n2026-01-01 00:00:00,1,1,1,nan\n')
        with self.assertRaises(ValueError):
            predictions(path, 'feature')

    def test_bad_headers_and_silent_extra_fields_rejected(self):
        path = self.root / 'bad.csv'
        for text in ['', '\n', 'time,actual,predicted,baseline\n',
                     'time,actual,actual,baseline\n2026-01-01,0,0,0\n',
                     'time,actual,predicted,baseline\n2026-01-01,0,0,0,999\n']:
            with self.subTest(text=text):
                path.write_text(text)
                with self.assertRaises(ValueError):
                    predictions(path, 'feature')

    def test_original_byte_hash_survives_bom_and_unnamed_index(self):
        path = self.root / 'bom.csv'
        raw = b'\xef\xbb\xbf,actual,predicted,baseline,forecast\r\n2026-01-01,600,600,600,600\r\n'
        path.write_bytes(raw)
        rows, identity = predictions(path, 'feature')
        self.assertEqual(identity['sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(len(rows), 1)

    def test_null_denominators_serialize_without_false_superiority(self):
        original = self.csv('old.csv', [(600, 600, 600)])
        result = self.compare(original, original)
        model = result['incoming_full_period']['model']
        self.assertEqual([model[k] for k in ('precision', 'recall', 'f1')], [None] * 3)
        delta = result['matched']['comparisons']['retained_original']
        self.assertFalse(delta['assessable'])
        self.assertFalse(delta['all_three_nonregressing'])
        self.assertFalse(delta['any_strict_gain'])
        write_report(result, self.root / 'null.json')
        self.assertEqual(json.loads((self.root / 'null.json').read_text()), result)

    def controls(self):
        original = self.csv('old.csv', [(700, 550, 650), (0, 0, 0)])
        incoming = self.csv('new.csv', [(700, 680, 650, 650), (0, 0, 0, 10)],
                            ['time', 'actual', 'predicted', 'baseline', 'forecast'])
        raw = self.root / 'raw.csv'
        raw.write_text('feature_time,target_time,actual_w_m2,point_w_m2\n'
                       '2026-01-01 00:00:00,2026-01-02 00:00:00,700,650\n'
                       '2026-01-01 01:00:00,2026-01-02 01:00:00,0,0\n')
        classifier = self.root / 'classifier.csv'
        classifier.write_text('feature_time,target_time,weather_actual_w_m2,probability,nwp_positive,predicted_positive\n'
                              '2026-01-01 00:00:00,2026-01-02 00:00:00,700,0.5,1,0\n'
                              '2026-01-01 01:00:00,2026-01-02 01:00:00,0,0.6,0,0\n')
        policy = self.root / 'policy.json'
        policy.write_text(json.dumps({'selected_augmented_arm': 'consensus_two_source', 'policies': {
            'consensus_two_source': {'policy': {'kind': 'correction', 'lower': .5, 'upper': .6}}}}))
        options = dict(raw_control_path=raw, classifier_path=classifier, classifier_policy_path=policy)
        return incoming, original, options

    def test_frozen_policy_strict_boundaries_and_separate_raw_sources(self):
        incoming, original, options = self.controls()
        result = self.compare(incoming, original, **options)
        classifier = result['matched']['metrics']['f1_008_consensus_two_source']
        self.assertEqual(classifier['false_negative'], 1)
        self.assertEqual(classifier['true_negative'], 1)
        self.assertEqual(classifier['f1'], 0)
        self.assertIsNone(classifier['precision'])
        self.assertNotIn('mae_w_m2', classifier)
        self.assertEqual(result['supplied_raw_changed_from_retained_target_times'], ['2026-01-02 01:00:00'])
        self.assertEqual(result['matched']['metrics']['supplied_raw_forecast']['mae_w_m2'], 30)
        self.assertEqual(result['matched']['metrics']['retained_raw_forecast']['mae_w_m2'], 25)

    def test_corrupt_saved_classifier_or_retained_control_is_rejected(self):
        mutations = [
            ('classifier_path', ',700,0.5,1,0', ',700,0.5,1,1'),
            ('classifier_path', ',700,0.5,1,0', ',701,0.5,1,0'),
            ('classifier_path', ',700,0.5,1,0', ',700,nan,1,0'),
            ('raw_control_path', ',700,650', ',701,650'),
            ('raw_control_path', '2026-01-02 00:00:00', '2026-01-03 00:00:00'),
        ]
        for source, old, new in mutations:
            with self.subTest(source=source, new=new):
                incoming, original, options = self.controls()
                path = options[source]
                path.write_text(path.read_text().replace(old, new))
                with self.assertRaises(ValueError):
                    self.compare(incoming, original, **options)

    def test_changed_selected_arm_or_policy_is_rejected(self):
        for change in ('arm', 'threshold'):
            with self.subTest(change=change):
                incoming, original, options = self.controls()
                path = options['classifier_policy_path']
                policy = json.loads(path.read_text())
                if change == 'arm':
                    policy['selected_augmented_arm'] = 'weather_two_source'
                else:
                    policy['policies']['consensus_two_source']['policy']['lower'] = .45
                path.write_text(json.dumps(policy))
                with self.assertRaises(ValueError):
                    self.compare(incoming, original, **options)

    def test_output_never_overwrites_or_writes_protected_inputs(self):
        output = self.root / 'result.json'
        output.write_text('retained')
        with self.assertRaises(FileExistsError):
            write_report({}, output)
        self.assertEqual(output.read_text(), 'retained')
        for base in [ROOT, ROOT / 'app']:
            for name in ('model', 'data', 'eval'):
                with self.assertRaises(ValueError):
                    write_report({}, base / name / 'MUST-NOT-BE-WRITTEN.json')

    def test_single_validation_cli_needs_no_test_file(self):
        incoming, original, options = self.controls()
        output = self.root / 'report.json'
        command = [sys.executable, str(Path(__file__).with_name('compare_prediction_versions.py')),
                   '--incoming', str(incoming), '--reference', str(original), '--model-id', 'Stefanos validation v2',
                   '--incoming-time-basis', 'feature', '--reference-time-basis', 'feature', '--output', str(output),
                   '--raw-control', str(options['raw_control_path']), '--classifier', str(options['classifier_path']),
                   '--classifier-policy', str(options['classifier_policy_path'])]
        first = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = output.read_bytes()
        second = subprocess.run(command, text=True, capture_output=True)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(json.loads(before)['coverage']['matched_hours'], 2)


if __name__ == '__main__':
    unittest.main()
