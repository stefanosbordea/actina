"""Current-deck checks and deliberate corruption; the delivered PPTX is never edited."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('deck_notes', ROOT / 'scripts/check_deck_notes.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
DECK = ROOT / 'delivery/Aktina-Pafos-2026.pptx'
NOTES = ROOT / 'delivery/Aktina-Deck-Source/Speaker-Notes.md'
BUILD = ROOT / 'delivery/Aktina-Deck-Source/build.mjs'


class DeckNotesTests(unittest.TestCase):
    def test_current_notes_titles_charts_and_equal_team(self):
        result = checker.validate_current(DECK, NOTES, BUILD)
        self.assertEqual(len(result['checks']), 12)
        self.assertEqual(result['native_editable_charts'], 4)
        self.assertTrue(result['equal_team_credit'])
        self.assertNotIn('plan_seconds', result)

    def test_native_note_title_chart_team_and_notes_relationship_corruption(self):
        cases = [
            ('ppt/notesSlides/notesSlide1.xml', lambda raw: raw.replace(b'Aktina starts', b'Wrong starts'), 'Native notes'),
            ('ppt/slides/slide2.xml', lambda raw: raw.replace(b'Why water storage matters', b'Wrong title'), 'Slide title'),
            ('ppt/slides/charts/chart4.xml', lambda raw: None, 'four referenced native charts'),
            ('ppt/slides/slide12.xml', lambda raw: raw.replace(b'Cleopas Cleopa', b'Loukas Louka'), 'Every team name'),
            ('ppt/slides/_rels/slide1.xml.rels', lambda raw: raw.replace(b'notesSlide1.xml', b'notesSlide2.xml'), 'Native notes'),
        ]
        with tempfile.TemporaryDirectory() as directory:
            for index, (part, mutate, error) in enumerate(cases):
                with self.subTest(part=part):
                    path = Path(directory) / f'corrupted-{index}.pptx'
                    with zipfile.ZipFile(DECK) as source, zipfile.ZipFile(path, 'w') as target:
                        for info in source.infolist():
                            data = source.read(info.filename)
                            if info.filename == part: data = mutate(data)
                            if data is not None: target.writestr(info, data)
                    with self.assertRaisesRegex(AssertionError, error): checker.validate_current(path, NOTES, BUILD)

    def test_unequal_name_typography_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'unequal.pptx'
            with zipfile.ZipFile(DECK) as source, zipfile.ZipFile(path, 'w') as target:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename == 'ppt/slides/slide12.xml':
                        tree = ET.fromstring(data)
                        shape = next(s for s in tree.findall('.//p:sp', checker.NS)
                                     if ''.join(s.find('./p:txBody', checker.NS).itertext()) == 'Loukas Louka')
                        shape.find('./p:txBody/a:p/a:r/a:rPr', checker.NS).set('sz', '4000')
                        data = ET.tostring(tree)
                    target.writestr(info, data)
            with self.assertRaisesRegex(AssertionError, 'Team name style changed'): checker.validate_current(path, NOTES, BUILD)

    def test_source_and_wrapper_mismatches_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            notes, build = Path(directory) / 'notes.md', Path(directory) / 'build.mjs'
            notes.write_text(NOTES.read_text().replace('Aktina starts', 'Wrong starts'))
            with self.assertRaisesRegex(AssertionError, 'Native notes'): checker.validate_current(DECK, notes, BUILD)
            build.write_text(BUILD.read_text().replace('Historical original remains unchanged.', 'Changed provenance.'))
            with self.assertRaisesRegex(AssertionError, 'wrapper changed'): checker.validate_current(DECK, NOTES, build)

    def test_historical_mode_requires_explicit_matching_inputs(self):
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/check_deck_notes.py'), '--mode', 'historical'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('explicit matching --deck and --notes pair', result.stderr)


if __name__ == '__main__':
    unittest.main()
