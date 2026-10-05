"""Check delivered notes; optionally compare an earlier deck and rendered slides."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}


def canonical_slide(package, index):
    text = package.read(f'ppt/slides/slide{index}.xml').decode()
    text = re.sub(r'<(?:a16|p14):creationId\b[^>]*/>', '', text)
    for relation in ET.fromstring(package.read(f'ppt/slides/_rels/slide{index}.xml.rels')):
        if relation.get('Type').endswith('/chart'):
            text = text.replace('r:id="'+relation.get('Id')+'"', 'r:id="'+relation.get('Target')+'"')
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--deck', type=Path, default=ROOT/'delivery/AquaShift-Pafos-2026.pptx')
    parser.add_argument('--notes', type=Path, default=ROOT/'delivery/AquaShift-Speaker-Notes.md')
    parser.add_argument('--compare-deck', type=Path)
    parser.add_argument('--before-previews', type=Path)
    parser.add_argument('--after-previews', type=Path)
    parser.add_argument('--receipt', type=Path, help='Write a new receipt; historical receipts stay unchanged by default.')
    args = parser.parse_args()
    regression = (args.compare_deck, args.before_previews, args.after_previews)
    if any(regression) and not all(regression):
        parser.error('Visual regression requires --compare-deck, --before-previews and --after-previews together.')
    markdown = args.notes.read_text()
    sections = re.split(r'(?m)^## (\d+)\. (.+)\n\n', markdown)[1:]
    records = []
    for index, title, body in zip(sections[::3], sections[1::3], sections[2::3]):
        note = body.rstrip()
        timing = re.search(r'^Timing: (\d+) seconds\. Presenter: (.+)\.$', note, re.M)
        assert timing, ('missing timing/presenter', index)
        spoken = re.search(r'Spoken text:\n(.*?)(?=\n\n(?:Presenter cue|Sources))', note, re.S)
        assert spoken, ('missing spoken text', index)
        records.append({'index': int(index), 'title': title, 'note': note, 'seconds': int(timing[1]),
                        'speaker': timing[2], 'spoken': spoken[1]})
    assert [record['index'] for record in records] == list(range(1, 13)), 'Expected twelve ordered slide sections'
    checks = []
    with zipfile.ZipFile(args.deck) as after:
        assert len([name for name in after.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', name)]) == 12
        for index, record in enumerate(records, 1):
            tree = ET.fromstring(after.read(f'ppt/notesSlides/notesSlide{index}.xml'))
            body = next(shape for shape in tree.findall('.//p:sp', NS)
                        if shape.find('./p:nvSpPr/p:nvPr/p:ph', NS) is not None
                        and shape.find('./p:nvSpPr/p:nvPr/p:ph', NS).get('type') == 'body')
            note = '\n'.join(''.join(p.itertext()) for p in body.findall('./p:txBody/a:p', NS))
            assert note == record['note'], ('notes', index)
            checks.append({'slide': index, 'native_notes_match_markdown': True,
                           'presenter': record['speaker'], 'seconds': record['seconds']})
        if all(regression):
            from PIL import Image, ImageChops
            with zipfile.ZipFile(args.compare_deck) as before:
                for index, check in enumerate(checks, 1):
                    assert canonical_slide(before, index) == canonical_slide(after, index), ('slide', index)
                    with Image.open(args.before_previews/f'slide-{index:02}.png') as a, Image.open(args.after_previews/f'slide-{index:02}.png') as b:
                        assert a.size == b.size and ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is None, ('render', index)
                    check.update(visual_xml_unchanged_except_generated_ids=True, final_render_pixel_equal=True)
                charts = [name for name in before.namelist() if re.search(r'/charts/chart\d+\.xml$', name)]
                assert len(charts) == 3
                assert all(before.read(name) == after.read(name) for name in charts)
    words = sum(len(re.findall(r"\b[\w]+(?:['-][\w]+)*\b", r['spoken'])) for r in records)
    assert 1300 <= words <= 1600 and sum(r['seconds'] for r in records) == 830
    assert 'according to the operator' not in markdown and 'Status: AI-assisted preparation draft' not in markdown
    assert markdown.count('Preparation note (not spoken):') == 1
    canvas = records[8]['spoken'].lower()
    assert all(term in canvas for term in ('customer segment', 'value proposition', 'channels', 'customer relationships', 'revenue', 'resources', 'activities', 'partners', 'costs'))
    assert 'delivery/AquaShift-Business-Model-Canvas.pdf' in records[8]['note']
    assert 'publication delays or the original data vintages' in records[6]['spoken']
    assert 'business students' in records[11]['spoken']
    assert all('—' not in r['spoken'] and '–' not in r['spoken'] for r in records)
    result = {'status': 'PASS', 'mode': 'visual-regression' if all(regression) else 'current-notes', 'checks': checks,
              'input_sha256': {'deck': hashlib.sha256(args.deck.read_bytes()).hexdigest(),
                               'markdown': hashlib.sha256(args.notes.read_bytes()).hexdigest()},
              'spoken_words': words, 'plan_seconds': 830, 'included_demo_or_fallback_seconds': 90,
              'official_limit_seconds': 900, 'remaining_seconds': 70, 'human_rehearsal_performed': False}
    if all(regression):
        result['native_charts_byte_identical'] = 3
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}))


if __name__ == '__main__':
    main()
