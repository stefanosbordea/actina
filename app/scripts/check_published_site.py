"""Compare both public aliases with the locally built static release."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

APP = Path(__file__).resolve().parents[1]
ALIASES = ('https://aktina-pafos-2026.vercel.app',
           'https://aquashift-pafos-2026.vercel.app')


def verify(item):
    base, path = item
    relative = path.relative_to(APP / 'dist').as_posix()
    result = dict(url=f'{base}/{relative}', path=relative,
                  expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    try:
        with urlopen(result['url'], timeout=30) as response:
            result.update(status=response.status, final_url=response.url,
                          observed_sha256=hashlib.sha256(response.read()).hexdigest())
        result['matches'] = result['status'] == 200 and result['observed_sha256'] == result['expected_sha256']
    except (HTTPError, URLError, TimeoutError) as error:
        result.update(matches=False, error=str(error))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = sorted(p for p in (APP / 'dist').rglob('*') if p.is_file())
    if not files or not (APP / 'dist/index.html').is_file():
        parser.error('Build app/dist first with node app/build.mjs')
    if args.output.exists():
        parser.error('Choose a new output path to preserve prior evidence')
    started = datetime.now(timezone.utc).isoformat()
    with ThreadPoolExecutor(max_workers=2) as pool:
        records = list(pool.map(verify, ((base, path) for base in ALIASES for path in files)))
    passed = all(row['matches'] for row in records)
    result = dict(status='PASS' if passed else 'FAIL', started_at_utc=started,
                  completed_at_utc=datetime.now(timezone.utc).isoformat(),
                  checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  scope='Published static bytes, not browser interaction or model accuracy.',
                  files_per_alias=len(files), records=records)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(dict(status=result['status'], files=len(records), output=str(args.output))))
    raise SystemExit(0 if passed else 1)
