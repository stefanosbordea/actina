"""Check delivered notes; optionally compare an earlier deck and rendered slides."""
from pathlib import Path
import argparse
import hashlib
import json
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
TEAM = ('Loukas Louka', 'Stefanos Bordea', 'Andreas Nikolaides', 'Cleopas Cleopa')
WRAPPER = r'SLIDE ${index}: ${title}\n\n${notes[index-1]}\n\nData and artifact provenance: delivery/Aktina-Deck-Source/inputs.sha256.json. Historical original remains unchanged.'


def relationship_targets(package, part, kind):
    directory, basename = posixpath.split(part)
    relations = ET.fromstring(package.read(f'{directory}/_rels/{basename}.rels'))
    return {relation.get('Id'): posixpath.normpath(posixpath.join(directory, relation.get('Target'))).lstrip('/')
            for relation in relations if relation.get('Type').endswith('/' + kind) and relation.get('TargetMode') != 'External'}


def native_notes(package, slide):
    targets = relationship_targets(package, slide, 'notesSlide')
    assert len(targets) == 1, ('Expected one native notes relationship', slide)
    tree = ET.fromstring(package.read(next(iter(targets.values()))))
    bodies = [shape for shape in tree.findall('.//p:sp', NS)
              if shape.find('./p:nvSpPr/p:nvPr/p:ph', NS) is not None
              and shape.find('./p:nvSpPr/p:nvPr/p:ph', NS).get('type') == 'body']
    assert len(bodies) == 1, ('Expected one native notes body', slide)
    return '\n'.join(''.join(p.itertext()) for p in bodies[0].findall('./p:txBody/a:p', NS))


def validate_current(deck, notes, build):
    markdown, source = notes.read_text(), build.read_text()
    assert WRAPPER in source, 'Deck build notes wrapper changed; review the exact embedding contract'
    assert re.findall(r'(?m)^## (\d+)\. ', markdown) == [str(i) for i in range(1, 13)], 'Expected twelve ordered note sections'
    sections = re.split(r'\n## \d+\. ', markdown)[1:]
    titles = re.findall(r"\bslide\((\d+),'([^']+)'\)", source)
    assert [int(index) for index, _ in titles] == list(range(1, 13)), 'Expected twelve ordered build slide titles'
    checks, visible, team_styles, charts_used = [], [], [], []
    with zipfile.ZipFile(deck) as package:
        slide_map = relationship_targets(package, 'ppt/presentation.xml', 'slide')
        order = ET.fromstring(package.read('ppt/presentation.xml')).findall('./p:sldIdLst/p:sldId', NS)
        slides = [slide_map[item.get('{' + NS['r'] + '}id')] for item in order]
        assert len(slides) == len(set(slides)) == 12, 'Expected twelve distinct slides in presentation order'
        assert len([n for n in package.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)]) == 12, 'Unexpected slide parts'
        for index, (slide, (_, title), section) in enumerate(zip(slides, titles, sections), 1):
            expected = WRAPPER.replace(r'\n', '\n').replace('${index}', str(index)).replace('${title}', title).replace('${notes[index-1]}', section)
            assert native_notes(package, slide) == expected, ('Native notes differ from exact source/build wrapper', index)
            tree = ET.fromstring(package.read(slide))
            shapes = tree.findall('.//p:sp', NS)
            headings = [shape for shape in shapes if shape.find('./p:nvSpPr/p:cNvPr', NS).get('name') == 'slide-title']
            if index == 1:  # The inherited cover has no named heading; build.mjs adds its wordmark.
                headings = [shape for shape in shapes if shape.find('./p:txBody', NS) is not None
                            and ''.join(shape.find('./p:txBody', NS).itertext()) == title]
            assert len(headings) == 1 and ''.join(headings[0].find('./p:txBody', NS).itertext()) == title, ('Slide title differs from build', index)
            visible.append('\n'.join(''.join(shape.find('./p:txBody', NS).itertext()) for shape in shapes if shape.find('./p:txBody', NS) is not None))
            for shape in shapes:
                body = shape.find('./p:txBody', NS)
                text = ''.join(body.itertext()) if body is not None else ''
                if text in TEAM:
                    assert index == 12, ('Team name outside final slide', text)
                    runs = body.findall('./a:p/a:r/a:rPr', NS)
                    assert len(runs) == 1, ('Expected single team-name style', text)
                    style = runs[0]
                    assert style.get('sz') == '2250' and style.get('b') == '0' and style.find('./a:latin', NS).get('typeface') == 'Arial', ('Team name style changed', text)
                    team_styles.append(ET.tostring(style))
            charts_used.extend(relationship_targets(package, slide, 'chart').values())
            checks.append({'slide': index, 'title': title, 'native_notes_match_source_and_wrapper': True})
        charts = [name for name in package.namelist() if re.search(r'/charts/chart\d+\.xml$', name)]
        assert len(charts) == 4 and sorted(charts_used) == sorted(charts), 'Expected four referenced native charts'
        workbooks = [name for name in package.namelist() if name.startswith('ppt/embeddings/') and name.endswith('.xlsx')]
        assert len(workbooks) == 4, 'Expected four embedded chart workbooks'
        assert all('\n'.join(visible).count(name) == 1 for name in TEAM), 'Every team name must appear exactly once'
        assert len(team_styles) == 4 and len(set(team_styles)) == 1, 'Team names must have equal typography'
    return {'status': 'PASS', 'mode': 'current-aktina', 'checks': checks, 'native_editable_charts': 4,
            'embedded_workbooks': 4, 'team_names': list(TEAM), 'equal_team_credit': True,
            'input_sha256': {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in [('deck', deck), ('markdown', notes), ('build', build)]},
            'human_rehearsal_performed': False, 'timing_and_presenter_assignments': 'Not specified by current notes; require team rehearsal'}


def canonical_slide(package, index):
    text = package.read(f'ppt/slides/slide{index}.xml').decode()
    text = re.sub(r'<(?:a16|p14):creationId\b[^>]*/>', '', text)
    for relation in ET.fromstring(package.read(f'ppt/slides/_rels/slide{index}.xml.rels')):
        if relation.get('Type').endswith('/chart'):
            text = text.replace('r:id="'+relation.get('Id')+'"', 'r:id="'+relation.get('Target')+'"')
    return text


def validate_historical(args):
    regression = (args.compare_deck, args.before_previews, args.after_previews)
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
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('current', 'historical'), default='current')
    parser.add_argument('--deck', type=Path)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--build', type=Path, default=ROOT/'delivery/Aktina-Deck-Source/build.mjs')
    parser.add_argument('--compare-deck', type=Path)
    parser.add_argument('--before-previews', type=Path)
    parser.add_argument('--after-previews', type=Path)
    parser.add_argument('--receipt', type=Path, help='Write a new receipt; never overwrite an existing receipt.')
    args = parser.parse_args()
    regression = (args.compare_deck, args.before_previews, args.after_previews)
    if any(regression) and (args.mode != 'historical' or not all(regression)):
        parser.error('Historical visual regression requires --mode historical, --compare-deck, --before-previews and --after-previews together.')
    if args.mode == 'historical' and (args.deck is None or args.notes is None):
        parser.error('Historical mode requires an explicit matching --deck and --notes pair.')
    args.deck = args.deck or ROOT/'delivery/Aktina-Pafos-2026.pptx'
    args.notes = args.notes or ROOT/'delivery/Aktina-Deck-Source/Speaker-Notes.md'
    result = validate_current(args.deck, args.notes, args.build) if args.mode == 'current' else validate_historical(args)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        with args.receipt.open('x') as stream:
            stream.write(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'checks'}))


if __name__ == '__main__':
    main()
