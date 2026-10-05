"""Independent PDF word-position check of the published main report fields."""
from pathlib import Path
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys

import pdfplumber

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def half_unit(token):
    token = token.rstrip('%')
    decimals = len(token.split('.')[1]) if '.' in token else 0
    return .5 * 10**-decimals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pdf-dir', type=Path, default=ROOT/'data/grid-reports/originals')
    args = parser.parse_args()
    json_path, csv_path = ROOT/'data/eac_curtailment_days.json', ROOT/'data/eac_curtailment_days.csv'
    rows = {d['date']: d for d in json.loads(json_path.read_text())['days']}
    csv_rows = {d['date']: d for d in csv.DictReader(csv_path.open())}
    sources_path = ROOT/'data/grid-reports/eac-report-sources.json'
    sources = json.loads(sources_path.read_text())
    checked, discrepancies, identities, reasons = [], [], {}, set()
    for source in sources:
        path = args.pdf_dir/source['filename']
        identities[str(path)] = digest(path)
        assert identities[str(path)] == source['sha256']
        assert path.stat().st_size == source['bytes']
        with pdfplumber.open(path) as pdf:
            assert len(pdf.pages) == 31
            for day, page in enumerate(pdf.pages, 1):
                # Direct PDF word coordinates, independent of the importer's Poppler crop.
                tokens = [w['text'] for w in page.extract_words() if 170 < w['x0'] < 250 and 100 < w['top'] < 445]
                source_date = dt.datetime.strptime(next(s for s in tokens if re.fullmatch(r'\d{1,2}/\d{1,2}/\d{4}', s)), '%d/%m/%Y').date().isoformat()
                times = [s.zfill(5) for s in tokens if re.fullmatch(r'\d{1,2}:\d{2}', s)]
                assert len(times) in (2, 4), (source_date, times)
                energy_tokens = [s for s in tokens if re.fullmatch(r'\d+(?:\.\d+)?', s)]
                percent_token = next(s for s in tokens if re.fullmatch(r'\d+(?:\.\d+)?%', s))
                values = list(map(float, energy_tokens))
                percent = float(percent_token[:-1])
                key = f"2026-{source['month']:02}-{day:02}"
                j, c = rows[key], csv_rows[key]
                assert source_date == key
                assert values == [j['estimated_day_energy_mwh'], j['estimated_curtailed_mwh']] == [float(c['estimated_day_energy_mwh']), float(c['estimated_curtailed_mwh'])]
                assert percent == j['reported_curtailment_percent'] == float(c['reported_curtailment_percent'])
                end = 1 if len(times) == 2 else 2
                assert (times[0], times[end]) == (j['windows'][0]['start_local'], j['windows'][0]['end_local']) == (c['group_1_start_local'], c['group_1_end_local'])
                if len(times) == 4:
                    assert (times[1], times[3]) == (j['group_2_windows'][0]['start_local'], j['group_2_windows'][0]['end_local'])
                potential, curtailed = values
                hp, hc, hr = half_unit(energy_tokens[0]), half_unit(energy_tokens[1]), half_unit(percent_token)
                ratio = 100*curtailed/potential
                interval = [100*(curtailed-hc)/(potential+hp), 100*(curtailed+hc)/(potential-hp)]
                if interval[1] < percent-hr or interval[0] > percent+hr:
                    discrepancies.append({'date': key, 'reported_percent': percent, 'ratio_percent': ratio,
                                          'ratio_interval_from_displayed_precision': interval,
                                          'reported_percent_interval': [percent-hr, percent+hr],
                                          'cause': 'Unknown source arithmetic discrepancy; imported values faithfully retained'})
                reasons.update(line for line in page.extract_text().splitlines() if 'Λόγος' in line)
                checked.append(key)
    assert len(checked) == len(rows) == len(csv_rows) == 62
    for path in (json_path, csv_path, sources_path, Path(__file__)):
        identities[str(path)] = digest(path)
    result = {'status': 'PASS — displayed source fields match both exports',
              'checked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'reproducing_command': f'{sys.executable} scripts/check_curtailment_report_sources.py --pdf-dir {args.pdf_dir}',
              'exit_status': 0, 'method': 'pdfplumber direct word positions x0 in(170,250), top in(100,445); dates, Group1 windows, main estimated energies and reported percentages compared independently against JSON and CSV; Group2 windows checked against JSON (CSV exports Group1 only); no importer functions reused',
              'checked_dates': checked, 'source_and_input_sha256': identities,
              'full_page_visual_review': ['August25', 'August29', 'August30'],
              'reason_text_variants': sorted(reasons), 'source_arithmetic_discrepancies': discrepancies,
              'scope': 'Main EAC report fields only. Separate Ripple/IoT values excluded; not all-PV totals, not Paphos plant allocation or recovered energy',
              'ripple_iot_visual_checks': {'2026-08-29': {'main_mwh': 805.8, 'ripple_mwh': 230.1, 'iot_mwh': 88.6},
                                          '2026-08-30': {'main_mwh': 1796.1, 'ripple_mwh': 567.6, 'iot_mwh': 727.0}}}
    (ROOT/'results/curtailment-independent-review.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': result['status'], 'checked_days': len(checked), 'source_discrepancy_dates': [d['date'] for d in discrepancies]}))


if __name__ == '__main__':
    main()
