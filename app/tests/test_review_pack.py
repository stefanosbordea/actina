import importlib.util
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1] / 'tools/package_review_pack.py'
spec = importlib.util.spec_from_file_location('review_pack', MODULE)
pack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pack)


class ReviewPackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.app = self.root / 'app'
        self.output = self.root / 'final.zip'
        for name in ('index.html', 'site.css', 'site.mjs', 'data.js', 'schedule_hourly.csv',
                     'benchmark.html', 'benchmark.mjs', 'benchmark-data.js'):
            self.write('site/' + name, 'local fixture')
        self.write('web/public/index.html', '<html>workspace</html>')
        self.write('site/fonts/LICENSE.txt', 'font license')
        self.write('site/.DS_Store', 'omit')
        self.write('site/drafts/unused.js', 'omit')
        shutil.copytree(self.app / 'site', self.app / 'dist')
        shutil.copytree(self.app / 'web/public', self.app / 'dist/workspace')
        (self.root / 'eval').mkdir()
        (self.root / 'eval/schedule_hourly.csv').write_text('local fixture')
        deck = io.BytesIO()
        with zipfile.ZipFile(deck, 'w') as archive:
            for slide in range(1, 13):
                archive.writestr(f'ppt/slides/slide{slide}.xml', '<slide/>')
        self.write('delivery/' + pack.DECK, deck.getvalue())
        self.write('delivery/Aktina-Deck-Source/verification.json', json.dumps({
            'sha256': pack.sha(deck.getvalue()), 'bytes': len(deck.getvalue()), 'slides': 12,
            'checks': {'build_exit_code': 0, 'package_integrity': 'pass'}}))
        notes = f'Use the silent 44-second backup: {pack.VIDEO}.'
        self.write('delivery/Aktina-Deck-Source/Speaker-Notes.md', notes)
        self.write('delivery/Aktina-Deck-Source/inputs.sha256.json', json.dumps({
            'delivery/Aktina-Deck-Source/Speaker-Notes.md': pack.sha(notes.encode())}))
        for name in ('Business-Model-Canvas', 'Executive-Summary', 'Technical-Proposal'):
            self.write(f'delivery/AquaShift-{name}.tex', 'current standalone source')
            self.write(f'delivery/AquaShift-{name}.pdf', 'stale export must not ship')
        self.write('delivery/AquaShift-Backup.mp4', 'old video must not ship')
        self.write('experiments/bulk.json', 'research bulk must not ship')
        self.write('delivery/' + pack.VIDEO, b'final video fixture')
        self.receipt = {
            'status': 'EXPORTED_AND_DECODED', 'duration_seconds': 44, 'audio_tracks': 0,
            'width': 1920, 'height': 1080, 'fps': 30,
            'output': {'sha256': pack.sha(b'final video fixture')},
            'verification': {'full_decode': 'passed', 'no_audio': True}}
        self.write_receipt()

    def write(self, relative, value):
        path = self.app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value.encode() if isinstance(value, str) else value)
        return path

    def write_receipt(self):
        self.write('delivery/Aktina-Backup-Final-Source/render/verification.json', json.dumps(self.receipt))

    def test_archive_is_complete_current_and_excludes_historical_artifacts(self):
        result = pack.build(self.app, self.output)
        self.assertEqual(result['status'], 'PACKAGED_AND_VERIFIED')
        with zipfile.ZipFile(self.output) as archive:
            names = archive.namelist()
            manifest = json.loads(archive.read('Aktina/MANIFEST.json'))
            for name, expected in manifest['files'].items():
                raw = archive.read('Aktina/' + name)
                self.assertEqual(len(raw), expected['bytes'])
                self.assertEqual(pack.sha(raw), expected['sha256'])
            self.assertEqual(archive.read('Aktina/presentation/Aktina-Speaker-Notes.md'),
                             (self.app / 'delivery/Aktina-Deck-Source/Speaker-Notes.md').read_bytes())
            self.assertIn('Aktina/site/fonts/LICENSE.txt', names)
            self.assertIn('Aktina/site/workspace/index.html', names)
            self.assertFalse(any('.pdf' in name or 'drafts/' in name or 'experiments/' in name
                                 or '.DS_Store' in name or 'AquaShift' in name for name in names))
        self.assertEqual(json.loads(self.output.with_suffix('.manifest.json').read_text())['sha256'],
                         pack.sha(self.output.read_bytes()))
        before = self.output.read_bytes()
        with self.assertRaisesRegex(ValueError, 'never overwritten'):
            pack.build(self.app, self.output)
        self.assertEqual(self.output.read_bytes(), before)

    def test_stale_offline_build_is_rejected(self):
        self.write('site/site.mjs', 'new source absent from dist')
        with self.assertRaisesRegex(ValueError, 'dist is stale'):
            pack.build(self.app, self.output)
        self.assertFalse(self.output.exists())

    def test_changed_notes_are_rejected(self):
        self.write('delivery/Aktina-Deck-Source/Speaker-Notes.md', 'changed after final build')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            pack.collect(self.app)

    def test_changed_deck_is_rejected(self):
        self.write('delivery/' + pack.DECK, 'unverified new deck')
        with self.assertRaisesRegex(ValueError, 'PowerPoint does not match'):
            pack.collect(self.app)

    def test_stale_document_video_cue_is_rejected(self):
        self.write('delivery/AquaShift-Technical-Proposal.tex', 'Play Aktina-Backup-v2.mp4')
        with self.assertRaisesRegex(ValueError, 'superseded video'):
            pack.collect(self.app)

    def test_audio_or_changed_video_is_rejected(self):
        self.receipt['audio_tracks'] = 1
        self.write_receipt()
        with self.assertRaisesRegex(ValueError, 'no audio'):
            pack.collect(self.app)
        self.receipt['audio_tracks'] = 0
        self.write_receipt()
        self.write('delivery/' + pack.VIDEO, b'new unverified bytes')
        with self.assertRaisesRegex(ValueError, 'video bytes differ'):
            pack.collect(self.app)

    def test_symlink_site_is_rejected(self):
        (self.app / 'site/external.json').symlink_to(self.app / 'site/data.js')
        with self.assertRaisesRegex(ValueError, 'Symlink in site'):
            pack.collect(self.app)

    def test_check_does_not_write_an_archive(self):
        self.assertEqual(pack.build(self.app, self.output, check_only=True)['status'], 'READY')
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix('.manifest.json').exists())


if __name__ == '__main__':
    unittest.main()
