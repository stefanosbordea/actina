"""Verify cloud enrichment preserves the full retained 71-test canonical payload."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
PRIOR_SHA = '159a5a9e37a86685099efb53777645f866ff239bce83239ccf65b8a5709de885'
data = json.loads((ROOT / 'public/data.json').read_bytes())
cloud = [day.pop('cloud_cover') for day in data['days']]
stripped = (json.dumps(data, separators=(',', ':'), allow_nan=False) + '\n').encode()
assert hashlib.sha256(stripped).hexdigest() == PRIOR_SHA, 'Retained forecasts, controls or plans changed'
assert len(cloud) == 92 and all(len(values) == 24 for values in cloud)
receipt = {'status': 'PASS', 'command': 'python3 web/check_cloud_enrichment.py',
    'comparison': 'Full payload without cloud_cover matches exact retained 71-test data SHA; forecasts, controls, 460 schedules, Sites and metadata preserved.',
    'old_sha256': PRIOR_SHA, 'new_sha256': hashlib.sha256((ROOT / 'public/data.json').read_bytes()).hexdigest(),
    'rows_added': sum(map(len, cloud)), 'plans_preserved': 460, 'cloud_range': [min(map(min, cloud)), max(map(max, cloud))]}
(ROOT / 'cloud-enrichment-check.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(receipt))
