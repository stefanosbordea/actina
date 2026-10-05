import hashlib
import json
import os
from pathlib import Path
import runpy
import unittest

HERE=Path(__file__).resolve().parent
SOURCE_KEY='f1-009/review/uncertainty.py'


def replay_and_compare():
    paths=[HERE/name for name in ['uncertainty-result.json','uncertainty-receipt.json','uncertainty.py']]
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    before={p:digest(p) for p in paths}
    relative=os.path.relpath(HERE/'uncertainty.py',Path.cwd())
    assert not Path(relative).is_absolute()
    result=runpy.run_path(relative)['main']()
    saved=json.loads(paths[0].read_text())
    archive=HERE/'attempts/uncertainty-relative-runpy-001'
    assert saved['inputs_sha256'][SOURCE_KEY]==digest(archive/'uncertainty.py')
    assert paths[0].read_bytes()==(archive/'uncertainty-result.json').read_bytes()
    assert paths[1].read_bytes()==(archive/'uncertainty-receipt.json').read_bytes()
    expected=json.loads(json.dumps(saved))
    expected['inputs_sha256'][SOURCE_KEY]=before[HERE/'uncertainty.py']
    assert result==expected
    assert before=={p:digest(p) for p in paths}
    return result


class RelativeRunpyTests(unittest.TestCase):
    def test_relative_source_preserves_all_analysis_values(self):
        result=replay_and_compare()
        self.assertEqual(result['hours'],[3567,3517])
        self.assertEqual(result['resamples_per_block_length'],20000)


if __name__=='__main__':unittest.main()
