"""Check the deployed static bytes, script types and private-path exclusions."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--base', default='https://aquashift-pafos-2026.vercel.app')
parser.add_argument('--output', default='http-check-current.json')
args = parser.parse_args()
root = Path(__file__).parent
result = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'base': args.base, 'public': [], 'excluded': []}
for path in sorted((root / 'public').rglob('*')):
    if not path.is_file():
        continue
    relative = str(path.relative_to(root / 'public'))
    request = urllib.request.Request(args.base + '/' + relative,
                                     headers={'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(request, timeout=30) as response:
        body, status, headers = response.read(), response.status, response.headers
    digest = hashlib.sha256(body).hexdigest()
    assert status == 200 and digest == hashlib.sha256(path.read_bytes()).hexdigest(), relative
    if relative.endswith(('.js', '.mjs')):
        assert 'javascript' in headers.get('Content-Type', ''), relative
    assert headers.get('X-Content-Type-Options') == 'nosniff', relative
    assert "default-src 'self'" in headers.get('Content-Security-Policy', ''), relative
    result['public'].append({'path': relative, 'status': status, 'bytes': len(body),
                             'sha256': digest, 'content_type': headers.get('Content-Type')})
for relative in ['source/provenance.json', 'results/metrics.json', 'generate.py',
                 '.vercel/project.json', 'package.json', 'test_workspace.mjs',
                 'archived-initial/app.js', 'review_pilot.mjs', 'check_pilot_cli.mjs',
                 'fixtures/pilot-synthetic-declaration.json']:
    try:
        with urllib.request.urlopen(args.base + '/' + relative, timeout=30) as response:
            status = response.status
    except urllib.error.HTTPError as error:
        status = error.code
    assert status == 404, (relative, status)
    result['excluded'].append({'path': relative, 'status': status})
(root / args.output).write_text(json.dumps(result, indent=2) + '\n')
print(f"{len(result['public'])} public assets match; {len(result['excluded'])} excluded routes return 404.")
