"""Offline cap and live-predecessor tests; no API calls or real-store writes."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT,Receipt
from editorial import select_helper
import run_helper

def fixtures():
    types=['assertion','demo','first_hand','method','data','method']
    items={}
    decisions=[]
    for i,kind in enumerate(types):
        item_id='fixture:'+str(i)
        items[item_id]=dict(item_id=item_id,version_id='fictional-version',publisher_id='github',
                           published_at='2026-10-%02dT00:00:00Z'%(13-i),kind='youtube' if i%2 else 'feed',title='Fictional fixture')
        decisions.append(dict(item_id=item_id,version_id='fictional-version',decision='accept',reason='Original fixture '+str(i),piece_ids=['01'],
                              evidence_type=kind,strongest_claim='Fixture only',perspective='vendor',commercial_incentive=True,
                              model_decision='accept',model_reason='Original fixture '+str(i)))
    for i,decision in enumerate(['accept','reject','defer'],6):
        item_id='fixture:'+str(i);items[item_id]=dict(items['fixture:0'],item_id=item_id,publisher_id='other-publisher')
        decisions.append(dict(decisions[0],item_id=item_id,decision=decision,model_decision=decision,piece_ids=['02'] if decision=='accept' else []))
    return items,decisions

def cap_ranking():
    items,original=fixtures();decisions=copy.deepcopy(original)
    info=select_helper.apply_publisher_cap(decisions,items)
    assert {d['item_id'] for d in decisions[:6] if d['decision']=='accept'}=={'fixture:3','fixture:4','fixture:5'}
    assert info['accepted_counts_before']['github']==6 and info['accepted_counts_after']['github']==3
    assert info['deferred_item_ids']==['fixture:0','fixture:1','fixture:2']
    assert decisions[6:]==original[6:]
    for row in decisions[:3]:
        assert row['decision']=='defer' and row['piece_ids']==[]
        assert row['reason']=='publisher cap (policy v2): github already has 3 stronger accepted items'
        assert row['model_decision']=='accept' and row['model_reason']==original[int(row['item_id'].split(':')[1])]['reason']
    # Equal evidence ranks use recency, then stable IDs independent of input order.
    equal=copy.deepcopy(original[:6])
    for row in equal:row['evidence_type']='data'
    select_helper.apply_publisher_cap(equal,items)
    assert {d['item_id'] for d in equal if d['decision']=='accept'}=={'fixture:0','fixture:1','fixture:2'}
    tied=copy.deepcopy(original[:6]);tie_items=copy.deepcopy(items)
    for row in tied:
        row['evidence_type']='method';tie_items[row['item_id']]['published_at']='2026-10-10T00:00:00Z'
    tied.reverse();select_helper.apply_publisher_cap(tied,tie_items)
    assert {d['item_id'] for d in tied if d['decision']=='accept'}=={'fixture:0','fixture:1','fixture:2'}
    print('Cap: whole-set evidence ranking, recency/ties, shared feed/video publisher, preserved model fields, other decisions unchanged: PASS')

def selection_integration():
    items,decisions=fixtures()
    class FakeEvidence:
        def __init__(self,*args):pass
        def get(self,item_id,version):return items[item_id]
        def excerpt(self,item):return dict(item,excerpt='Fictional contract fixture only.')
    class FakeClient:
        requests=[]
        def __init__(self,*args):pass
        def chat(self,stage,messages,**kwargs):
            self.requests.append(copy.deepcopy(messages))
            item=json.loads(messages[-1]['content'])['ITEM']['item_id']
            decision=next(d for d in decisions if d['item_id']==item)
            return json.dumps({k:decision[k] for k in ['decision','reason','piece_ids','strongest_claim','evidence_type','perspective','commercial_incentive']})
    with tempfile.TemporaryDirectory(prefix='pset4-v2-cap-') as folder:
        run=Path(folder).resolve()
        for name in ['config','prompts']:shutil.copytree(ROOT/name,run/name)
        (run/'run.json').write_text(json.dumps(dict(run_id='fictional-cap-test',mode='example',development=True)))
        for policy,expected in [('Version: **v2 (2026-10-14)**\n',3),('Version: v1 (fixture)\n',6)]:
            # Only the temporary snapshot changes; Yilin's policy remains untouched.
            (run/'config/editorial_policy.md').write_text(policy);FakeClient.requests=[]
            receipt=Receipt(run,'fixture-cap');output=io.StringIO()
            with patch.object(select_helper,'Evidence',FakeEvidence),patch.object(select_helper,'LLMClient',FakeClient),\
                 patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(r)+'\n' for r in items.values()))),contextlib.redirect_stdout(output):
                select_helper.select(run,receipt)
            result=[json.loads(line) for line in output.getvalue().splitlines()]
            assert len(result)==len(items)==receipt.output_count==len(FakeClient.requests)
            assert [r['item_id'] for r in result]==list(items)
            assert sum(r['decision']=='accept' for r in result[:6])==expected
            assert all('model_decision' in r and 'model_reason' in r for r in result)
            assert ('publisher_cap' in receipt.details)==(expected==3)
            if expected==3:assert all('after ALL item decisions' in m[0]['content'] for m in FakeClient.requests)
    print('Selection: one model call/record per item, post-processing cap receipt and original fields, v1 unaffected: PASS (model/store mocked)')

def live_predecessor():
    with tempfile.TemporaryDirectory(prefix='pset4-v2-predecessor-') as folder:
        root=Path(folder).resolve();(root/'runs').mkdir()
        for name in ['config','prompts']:shutil.copytree(ROOT/name,root/name)
        for run_id,mode,development,date in [('live-run-1','live',False,'2026-10-13'),('newer-replay','replay',False,'2026-10-14'),('newest-dev','live',True,'2026-10-15')]:
            run=root/'runs'/run_id;run.mkdir()
            (run/'run.json').write_text(json.dumps(dict(run_id=run_id,started_at=date+'T00:00:00Z',as_of_date=date,mode=mode,development=development)))
        output=io.StringIO()
        with patch.object(run_helper,'ROOT',root),patch.object(run_helper,'validate'),contextlib.redirect_stdout(output):run_helper.setup()
        created=root/output.getvalue().strip();metadata=json.loads((created/'run.json').read_text())
        assert metadata['previous_run_id']=='live-run-1' and metadata['mode']=='live'
    print('New live run predecessor ignores newer replay and development runs: PASS')

if __name__=='__main__':
    assert os.environ.get('EVIDENCE_DIR') and Path(os.environ['EVIDENCE_DIR']).resolve()!=ROOT/'data/evidence','Set EVIDENCE_DIR to a temp directory'
    cap_ranking();selection_integration();live_predecessor()
