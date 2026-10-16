"""Offline coverage/repair and resume-routing tests; no API or live-run writes."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from editorial import briefs_helper
from editorial.evidence_helper import Evidence
from lib.records import ROOT,Receipt,StageFailure

LIVE=ROOT/'runs/20261013T035421Z-98ff50c1'

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def coverage_and_repairs():
    # Reuse retained bytes read-only; fictional responses never become live briefs.
    items={r['item_id']:r for r in rows(LIVE/'eligible.jsonl')}
    accepted=[d for d in rows(LIVE/'decisions.jsonl') if d['decision']=='accept']
    chosen=[]
    publishers=set()
    for decision in accepted:
        item=items[decision['item_id']]
        if item['kind']!='feed' or len(publishers)<2 and item['publisher_id'] not in publishers:
            chosen.append(decision)
            if item['kind']=='feed':publishers.add(item['publisher_id'])
    class ReadOnlyEvidence(Evidence):
        def get(self,item_id,version_id):
            value=items[item_id]
            assert value['version_id']==version_id
            return value
    evidence=ReadOnlyEvidence()
    sources=[items[d['item_id']] for d in chosen]
    choices,catalog=briefs_helper.citation_choices(evidence,sources)
    codes=[item['reference_choices'][0]['reference_id'] for item in choices]
    missing=[]
    for piece in ['01','02','03']:
        claims=[]
        for index,(kind,references) in enumerate([
            ('source_claim',[codes[0]]),('source_claim',[codes[1]]),
            ('source_claim',[codes[2]]),('inference',[codes[0],codes[2]])],1):
            claims.append({'claim_id':piece+'-c'+str(index),'statement':'Fictional validator fixture, never saved as live editorial evidence.',
                           'type':kind,'evidence':[{'reference_id':code} for code in references]})
        missing.append(dict(piece_id=piece,title='Fictional contract fixture',question='Fixture?',argument='Fixture argument.',
                            synthesis='Fixture synthesis.',limitations='Fixture only.',claims=claims))
    valid=copy.deepcopy(missing)
    valid[1]['claims'].append({'claim_id':'02-c5','statement':'Fictional video fixture.',
                              'type':'source_claim','evidence':[{'reference_id':codes[3]}]})
    exact_errors=briefs_helper.validate_briefs(briefs_helper.expand_choices(copy.deepcopy(missing),catalog),evidence)
    assert exact_errors==['Series must use feed, youtube and podcast; got feed, podcast']
    class FakeClient:
        outputs=[]
        requests=[]
        def __init__(self,*args):pass
        def chat(self,stage,messages,**kwargs):
            type(self).requests.append(copy.deepcopy(messages))
            return json.dumps({'briefs':type(self).outputs.pop(0)})
    run=ROOT/'runs'/('resume-contract-example-'+uuid.uuid4().hex[:8])
    run.mkdir()
    try:
        shutil.copytree(LIVE/'config',run/'config')
        shutil.copytree(LIVE/'prompts',run/'prompts')
        (run/'run.json').write_text(json.dumps({'run_id':run.name,'as_of_date':'2026-10-13','mode':'example'}))
        for outputs,fail in [([missing,missing,valid],False),([missing,missing,missing],True)]:
            FakeClient.outputs=copy.deepcopy(outputs);FakeClient.requests=[]
            receipt=Receipt(run,'fixture-create-briefs');output=io.StringIO()
            with patch.object(briefs_helper,'Evidence',ReadOnlyEvidence),patch.object(briefs_helper,'LLMClient',FakeClient),\
                 patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(d)+'\n' for d in chosen))),contextlib.redirect_stdout(output):
                try:
                    briefs_helper.create(run,receipt)
                    assert not fail
                except StageFailure as error:
                    assert fail and 'after two repairs' in str(error)
            assert len(FakeClient.requests)==3 and receipt.details['repair_count']==2
            assert not output.getvalue() if fail else len(output.getvalue().splitlines())==3
            plan=json.loads((ROOT/receipt.details['coverage_plan_path']).read_text())
            assert plan['accepted_by_kind_and_publisher']['youtube']['t3-theo'][0]['item_id']=='youtube:ND_kRgU_WlY'
            assert 'youtube:ND_kRgU_WlY' in FakeClient.requests[0][-1]['content']
            for request in FakeClient.requests[1:]:
                assert json.loads(request[-1]['content'])['validator_errors']==exact_errors
        assert len(list((run/'llm/create-briefs').glob('coverage-plan-*.json')))==2
    finally:
        shutil.rmtree(run)
    print('Coverage plan, exact repair errors, two repairs, unique plans, and failure without fake briefs: PASS')

def routing_fixture(root):
    for name in ['run.sh','run_helper.py','workflows/create_series.sh','lib/records.py','lib/receipt_helper.py',
                 'reporting/summarize_run.sh','reporting/summary_helper.py']:
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy(ROOT/name,target)
    run=root/'runs/resume-routing-example';run.mkdir(parents=True)
    shutil.copytree(LIVE/'config',run/'config');shutil.copytree(LIVE/'prompts',run/'prompts')
    metadata=dict(run_id=run.name,as_of_date='2026-10-08',started_at='2026-10-08T00:00:00Z',mode='example',previous_run_id=None)
    (run/'run.json').write_text(json.dumps(metadata))
    eligible=[dict(item_id='fictional:'+str(i),version_id='fixture-only',publisher_id='publisher-'+str(i%6),kind=['feed','youtube','podcast'][i%3]) for i in range(12)]
    decisions=[dict(item_id=r['item_id'],version_id=r['version_id'],decision='reject',reason='Routing fixture only.',piece_ids=[]) for r in eligible]
    briefs=[dict(piece_id=p,claims=[]) for p in ['01','02','03']]
    manifest=[dict(piece_id=p,path='fixture-only',claim_ids=[]) for p in ['01','02','03']]
    fixtures=root/'fixtures';fixtures.mkdir()
    for name,values in [('eligible',eligible),('decisions',decisions),('briefs',briefs),('articles',manifest),('video_scripts',manifest)]:
        data=''.join(json.dumps(v)+'\n' for v in values)
        (run/(name+'.jsonl')).write_text(data);(fixtures/(name+'.jsonl')).write_text(data)
    (fixtures/'review.json').write_text(json.dumps({'review_id':'fictional-routing-only','passed':True,'issues':[]}))
    (run/'logs').mkdir()
    original=dict(stage='select-items',status='completed',input_count=12,output_count=12,started_at=metadata['started_at'],
                  finished_at=metadata['started_at'],tools=[],models=[],cost_usd=0,cost_is_estimate=False,errors=[])
    (run/'logs/original.json').write_text(json.dumps(original))
    stages={'editorial/select_items.sh':('select_items','decisions.jsonl'),
            'editorial/create_briefs.sh':('create_briefs','briefs.jsonl'),
            'content/write_articles.sh':('write_articles','articles.jsonl'),
            'content/write_video_scripts.sh':('write_video_scripts','video_scripts.jsonl'),
            'review/check_content.sh':('check_content','review.json'),
            'workflows/collect_sources.sh':('FORBIDDEN_collection',None),'data/store.sh':('FORBIDDEN_store',None)}
    for name,(label,result) in stages.items():
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True)
        body='#!/usr/bin/env bash\nset -euo pipefail\n'
        body+='printf "'+label+'\\n" >> "$PSET4_TEST_TRACE"\n'
        body+='if [ "${PSET4_TEST_FAIL_STAGE:-}" = "'+label+'" ]; then exit 1; fi\n'
        body+='cat "'+str(fixtures/result)+'"\n' if result else 'exit 1\n'
        target.write_text(body)
    return run

def resume_routing():
    routes={'select_items':['select_items','create_briefs','write_articles','write_video_scripts','check_content'],
            'create_briefs':['create_briefs','write_articles','write_video_scripts','check_content'],
            'write_content':['write_articles','write_video_scripts','check_content'],'check_content':['check_content']}
    for stage,expected in routes.items():
        with tempfile.TemporaryDirectory(prefix='pset4-resume-routing-') as directory:
            root=Path(directory);run=routing_fixture(root);trace=root/'trace.txt'
            env=dict(os.environ,PSET4_TEST_TRACE=str(trace))
            protected={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in [run/'run.json',run/'eligible.jsonl',run/'logs/original.json',*list((run/'config').glob('*')),*list((run/'prompts').glob('*'))]}
            if stage!='select_items':protected[run/'decisions.jsonl']=hashlib.sha256((run/'decisions.jsonl').read_bytes()).hexdigest()
            result=subprocess.run(['bash','workflows/create_series.sh',str(run),'--from',stage],cwd=root,env=env,capture_output=True,text=True)
            assert result.returncode==0,result.stderr
            assert trace.read_text().splitlines()==expected
            receipts=[json.loads(p.read_text()) for p in (run/'logs').glob('create-series-*.json')]
            assert receipts[-1]['resumed_from']==stage and receipts[-1]['reason']
            assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in protected.items())
            if stage=='create_briefs':
                trace.write_text('')
                result=subprocess.run(['bash','run.sh','--resume',str(run),'--from',stage],cwd=root,env=env,capture_output=True,text=True)
                assert result.returncode==0,result.stderr
                assert trace.read_text().splitlines()==expected
                assert json.loads(result.stdout)['status']=='awaiting_review'
                assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in protected.items())
                assert len(list((root/'runs').iterdir()))==1
                receipts=[json.loads(p.read_text()) for p in (run/'logs').glob('run-resume-*.json')]
                assert receipts[-1]['resumed_from']==stage and receipts[-1]['reason']
                env['PSET4_TEST_FAIL_STAGE']='create_briefs'
                result=subprocess.run(['bash','run.sh','--resume',str(run),'--from',stage],cwd=root,env=env,capture_output=True,text=True)
                assert result.returncode==1 and json.loads(result.stdout)['status']=='failed'
                assert all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in protected.items())
            result=subprocess.run(['bash','run.sh','--resume',str(run),'--from','invalid'],cwd=root,env=env,capture_output=True,text=True)
            assert result.returncode==2
    print('All four resume routes, entry-point resume, preserved snapshots/date/decisions/receipts, failure and invalid arguments: PASS (stages mocked)')

if __name__=='__main__':
    coverage_and_repairs()
    resume_routing()
