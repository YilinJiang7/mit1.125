"""Offline contract tests against a completed dev run; no paid calls or live edits."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT, Receipt, StageFailure
from editorial import select_helper
from editorial.evidence_helper import Evidence,validate_briefs

def records(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def selection_retry(run):
    item=records(run/'eligible.jsonl')[0]
    valid=dict(decision='reject',reason='Fictional contract-test decision, never saved as editorial evidence.',piece_ids=[],strongest_claim='Contract fixture only.',evidence_type='none',perspective='other',commercial_incentive=False)
    class FakeClient:
        outputs=[]
        calls=0
        def __init__(self,*args):pass
        def chat(self,*args,**kwargs):
            value=self.outputs[self.calls]
            type(self).calls+=1
            return value
    for outputs,should_fail in [(['{}',json.dumps(valid)],False),(['{}','{}'],True)]:
        FakeClient.outputs=outputs;FakeClient.calls=0
        receipt=Receipt(run,'fixture-selection')
        output=io.StringIO()
        with patch.object(select_helper,'LLMClient',FakeClient),patch.object(sys,'stdin',io.StringIO(json.dumps(item)+'\n')),contextlib.redirect_stdout(output):
            try:
                select_helper.select(run,receipt)
                assert not should_fail
            except StageFailure:
                assert should_fail
        assert FakeClient.calls==2
        assert not output.getvalue() if should_fail else len(output.getvalue().splitlines())==1
    print('Selection: exactly one retry, then validated result or failure without fake decision: PASS')

def review_tampering(run):
    test_run=ROOT/'runs'/('phase2-contract-test-'+str(os.getpid()))
    test_run.mkdir()
    try:
        for name in ['run.json','briefs.jsonl','decisions.jsonl','articles.jsonl','video_scripts.jsonl']:
            shutil.copy(run/name,test_run/name)
        metadata=json.loads((test_run/'run.json').read_text())
        metadata.update(run_id=test_run.name,mode='example',development=True)
        (test_run/'run.json').write_text(json.dumps(metadata))
        for name in ['articles','video_scripts']:
            shutil.copytree(run/name,test_run/name)
            values=records(test_run/(name+'.jsonl'))
            for row in values:
                row['path']=str((test_run/name/(row['piece_id']+'.md')).relative_to(ROOT))
            (test_run/(name+'.jsonl')).write_text(''.join(json.dumps(row)+'\n' for row in values))
        def assess():
            result=subprocess.run(['bash','review/check_content.sh',str(test_run)],cwd=ROOT,capture_output=True,text=True)
            assert result.returncode==0,result.stderr
            return json.loads(result.stdout)
        original=assess()
        assert original['passed']
        briefs=records(test_run/'briefs.jsonl')
        bad=copy.deepcopy(briefs)
        reference=next(r for b in bad for c in b['claims'] for r in c['evidence'] if r['locator']['type']=='text')
        reference['locator']['quote']='[fictional invalid quote for contract test]'
        (test_run/'briefs.jsonl').write_text(''.join(json.dumps(b)+'\n' for b in bad))
        changed=assess()
        assert not changed['passed'] and changed['review_id']!=original['review_id']
        assert any('exact substring' in r['message'] for r in changed['issues'])
        (test_run/'briefs.jsonl').write_bytes((run/'briefs.jsonl').read_bytes())
        article=test_run/'articles/01.md'
        body=article.read_text();article.write_text(body.replace('\n## Sources','\nInvalid fixture marker [99-c99].\n\n## Sources',1))
        invalid_marker=assess()
        assert not invalid_marker['passed'] and invalid_marker['review_id']!=original['review_id']
        article.write_text(body)
        warnings=assess()
        assert sum('Needs human judgment' in row['message'] for row in warnings['issues'])==3
        assert warnings['review_id']==original['review_id']
        print('Review: exact quotes, marker rejection, fingerprint change/stability, human warnings and exit 0 on failed assessment: PASS')
    finally:
        shutil.rmtree(test_run)

def main():
    if len(sys.argv)!=2:
        raise SystemExit('usage: EVIDENCE_DIR=TEMP python3 tests/phase2_test.py DEV_RUN_DIR')
    run=Path(sys.argv[1]).resolve()
    assert json.loads((run/'run.json').read_text()).get('development'), 'Use a development run only'
    os.environ['RUN_DIR']=str(run)
    selection_retry(run)
    evidence=Evidence()
    briefs=records(run/'briefs.jsonl')
    assert not validate_briefs(briefs,evidence)
    bad=copy.deepcopy(briefs)
    reference=next(r for b in bad for c in b['claims'] for r in c['evidence'] if r['locator']['type']=='segment')
    reference['locator']['segment_id']='fictional-absent-segment'
    assert any('Segment does not exist' in error for error in validate_briefs(bad,evidence))
    print('Brief validator rejects missing segments: PASS')
    review_tampering(run)

if __name__=='__main__':
    main()
