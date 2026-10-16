"""Offline Phase 3/4a contracts, using only an explicitly labelled temp-store run."""
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'collectors'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'processing'))
from lib.records import ROOT,Receipt,StageFailure
from editorial.evidence_helper import Evidence,stamp
from editorial.excerpt_helper import sample_segments
from editorial.briefs_helper import citation_choices
from editorial.policy_diff_helper import diff_text
from content import articles_helper
from content.sources_helper import source_notes
from content.word_counts import word_count
from publishing.package_helper import package
from review.check_helper import build_review
import youtube_helper
import extract_helper
import run_helper

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def command(args,stdin=None):
    return subprocess.run(args,cwd=ROOT,input=stdin,capture_output=True,text=True)

def sampling(run):
    segments=[dict(segment_id='s%03d'%i,start_seconds=i*30,end_seconds=(i+1)*30,
                   text=('AI coding agents learner education ' if i==85 else 'ordinary discussion ')*24) for i in range(100)]
    segments[20]['text']="Today's sponsor. Use our code for a discount."
    segments[85]['text']+='\nA later relevant passage.'
    project=json.loads((run/'config/project.json').read_text())
    text,details=sample_segments(segments,project,6000,stamp)
    selected=details['selected_segment_ids']
    assert len(text)<=6000 and all(line.startswith('[') for line in text.splitlines())
    assert {'s000','s099','s085'}<=set(selected)
    assert all('s%03d'%i not in selected for i in range(20,25))
    assert details['selected_span_seconds']==[0,3000]
    assert details['method']=='evenly_spaced_windows_and_project_keyword_matches'
    receipt=Receipt(run,'fixture-sampling');evidence=Evidence(project,receipt)
    item=next(r for r in rows(run/'items.jsonl') if r['kind']=='youtube')
    excerpt=evidence.excerpt(item)
    choices,_=citation_choices(evidence,[item])
    actual={s['segment_id'] for s in json.loads((ROOT/item['segments_path']).read_text())}
    assert len(excerpt['excerpt'])<=6000
    assert {c['segment_id'] for c in choices[0]['reference_choices']}<=actual
    assert len(receipt.details['excerpt_sampling'])==2
    print('Distributed, keyword, sponsor and single-line sampling; real citation choices and receipt method: PASS')

def sources(run):
    brief=copy.deepcopy(rows(run/'briefs.jsonl')[0]);evidence=Evidence()
    reference=next(r for c in brief['claims'] for r in c['evidence'] if r['locator']['type']=='text')
    video=next(r for b in rows(run/'briefs.jsonl') for c in b['claims'] for r in c['evidence'] if evidence.get(r['item_id'],r['version_id'])['kind']=='youtube')
    brief['claims']=[dict(claim_id='01-c1',evidence=[reference,video]),dict(claim_id='01-c2',evidence=[reference,video])]
    notes=source_notes(brief,evidence)
    lines=[line for line in notes.splitlines() if line.startswith('- ')]
    assert len(lines)==2 and all('[01-c1] [01-c2]' in line for line in lines)
    assert '&t=' in notes and 'published ' in notes and '; passage: ' in notes
    separate=copy.deepcopy(reference);separate['locator']['quote']=reference['locator']['quote'][:50]
    brief['claims'][1]['evidence'].append(separate)
    assert len([line for line in source_notes(brief,evidence).splitlines() if line.startswith('- ')])==3
    print('Sources: distinct item/locator lines, grouped markers, separate passages and timed YouTube links: PASS')

def length_revision(run):
    briefs=rows(run/'briefs.jsonl')
    class FakeClient:
        calls=[]
        overlong_revision=False
        structural_errors=False
        def __init__(self,*args):pass
        def chat(self,stage,messages,**kwargs):
            self.calls.append(copy.deepcopy(messages))
            payload=json.loads(messages[1]['content']);brief=payload['BRIEF']
            assert all(item['cited_passages'] for item in payload['EVIDENCE'])
            assert 'overrides the prompt' in messages[0]['content'] and articles_helper.DRAFT_DISCLOSURE in messages[0]['content']
            revised=any(m['role']=='system' and m['content'].startswith('Length revision contract:') for m in messages)
            size=(750 if stage=='write-articles' else 550) if revised else (100 if brief['piece_id']=='01' else 1000)
            if revised and self.overlong_revision:size=1000
            markers=' '.join('['+c['claim_id']+']' for c in brief['claims'])
            if self.structural_errors and revised and len(messages)==5:markers=' '.join('['+c['claim_id']+']' for c in brief['claims'][1:])
            body='# Fictional length test\n\n'
            if stage=='write-video-scripts':body+='## Scene 1\n**Narration:** '
            body+='word '*size+markers+'\n'
            if stage=='write-video-scripts':body+='**On screen:** Fixture only.\n'
            if self.structural_errors and len(messages)==2:
                body+='Drafted with AI assistance from a source-tracked pipeline and reviewed by the editor.\n\n## Sources\nFixture invalid initial section.\n'
            else:body+=articles_helper.DRAFT_DISCLOSURE+'\n'
            return body
    for kind in ['article','script']:
        FakeClient.calls=[];receipt=Receipt(run,'fixture-length-'+kind);output=io.StringIO()
        with patch.object(articles_helper,'LLMClient',FakeClient),patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(b)+'\n' for b in briefs))),contextlib.redirect_stdout(output):
            articles_helper.write(run,receipt,kind)
        assert len(FakeClient.calls)==6 and len(receipt.details['length_revisions'])==3
        assert all(r['within_review_range'] and r['target_met'] for r in receipt.details['length_revisions'])
        assert all('Keep EVERY claim marker' in m[-1]['content'] for m in FakeClient.calls[1::2])
        name='articles' if kind=='article' else 'video_scripts'
        (run/(name+'.jsonl')).write_text(output.getvalue())
        for row in rows(run/(name+'.jsonl')):
            body=(ROOT/row['path']).read_text()
            low,high=(600,900) if kind=='article' else (450,700)
            assert low<=word_count(body,kind)<=high
    for overlong,structural in [(True,False),(False,True)]:
        FakeClient.calls=[];FakeClient.overlong_revision=overlong;FakeClient.structural_errors=structural
        receipt=Receipt(run,'fixture-bounded-revision')
        with patch.object(articles_helper,'LLMClient',FakeClient),patch.object(sys,'stdin',io.StringIO(''.join(json.dumps(b)+'\n' for b in briefs))),contextlib.redirect_stdout(io.StringIO()):
            articles_helper.write(run,receipt,'article')
        assert len(receipt.details['length_revisions'])==3
        assert len(FakeClient.calls)==(6 if overlong else 12)
        assert all(r['within_review_range']==(not overlong) for r in receipt.details['length_revisions'])
        if structural:assert receipt.details['repair_count']==6
        if structural:assert all(any(m['role']=='system' and articles_helper.DRAFT_DISCLOSURE in m['content'] for m in request[2:]) for request in FakeClient.calls[1::4])
    print('Articles/scripts: short and long bodies trigger one revision; all markers preserved; cited passages included: PASS (model mocked)')

def youtube_fallback(run):
    source=dict(source_id='fixture-yt',publisher_id='fictional',kind='youtube',url='https://www.youtube.com/channel/UC'+'a'*22,max_items=1)
    flat=SimpleNamespace(returncode=0,stdout=json.dumps({'entries':[{'id':'old','upload_date':'20261013'},{'id':'recent','upload_date':'19900101'}]}).encode())
    def metadata(url):
        return dict(title='Fixture only',upload_date='19900101' if url.endswith('old') else '20261012')
    attempts=[]
    with patch.object(youtube_helper,'download',side_effect=OSError('fixture RSS unavailable')),patch.object(youtube_helper.subprocess,'run',return_value=flat) as call,patch.object(youtube_helper,'yt_metadata',side_effect=metadata):
        found=youtube_helper.discover(source,run,attempts)
    assert len(found)==1 and found[0]['item_id']=='youtube:recent' and found[0]['published_at']=='2026-10-12T00:00:00Z'
    assert '--flat-playlist' in call.call_args.args[0]
    assert found[0]['discovery_method']=='yt_dlp_flat_playlist_and_video_metadata'
    assert any(a['endpoint']=='channel-rss' and a['status']=='failed' for a in attempts)
    original=(run/'config/sources.json').read_bytes()
    try:
        (run/'config/sources.json').write_text(json.dumps([source]));receipt=Receipt(run,'fixture-youtube-failure')
        with patch.object(youtube_helper,'download',side_effect=OSError()),patch.object(youtube_helper.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            assert youtube_helper.collect(run,receipt)==1
        assert receipt.details['sources'][0]['status']=='failed' and receipt.errors
        assert any(a['endpoint']=='yt-dlp-flat-playlist' and a['status']=='failed' for a in receipt.details['sources'][0]['attempts'])
    finally:(run/'config/sources.json').write_bytes(original)
    print('YouTube: RSS failure falls back to flat IDs + per-video dates; both-method failure remains failed: PASS')

def packaging(run):
    def expect_failure(message):
        try:
            with contextlib.redirect_stdout(io.StringIO()):package(run,Receipt(run,'fixture-package'))
            raise AssertionError('Expected packaging failure')
        except StageFailure as error:assert message.lower() in str(error).lower(),str(error)
    expect_failure('review.json')
    review=build_review(run,Receipt(run,'fixture-review'));assert review['passed']
    (run/'review.json').write_text(json.dumps(review))
    expect_failure('approval.json')
    approval=dict(review_id=review['review_id'],decision='revise',reviewer='FICTIONAL CONTRACT FIXTURE',reviewed_at='2026-10-13T12:00:00Z',notes='Synthetic approval for an example run only; not Yilin approval.')
    (run/'approval.json').write_text(json.dumps(approval));expect_failure('approve')
    approval['decision']='approve';approval['review_id']='stale-fixture'
    (run/'approval.json').write_text(json.dumps(approval));expect_failure('stale')
    approval['review_id']=review['review_id'];(run/'approval.json').write_text(json.dumps(approval))
    assert not (run/'package').exists()
    with contextlib.redirect_stdout(io.StringIO()):package(run,Receipt(run,'fixture-package'))
    links=run/'package/publication_links.json';values=json.loads(links.read_text())
    assert len(values)==3 and all(r['substack_url'] is None and r['youtube_url'] is None for r in values)
    values[0]['substack_url']='https://example.invalid/fictional-package-test';links.write_text(json.dumps(values,indent=4)+'\n');before=links.read_bytes()
    with contextlib.redirect_stdout(io.StringIO()):package(run,Receipt(run,'fixture-package'))
    assert links.read_bytes()==before
    manifest=json.loads((run/'package/manifest.json').read_text())
    assert len(manifest['pieces'])==3 and len(manifest['remaining_manual_steps'])==4
    article=run/'articles/01.md';saved=article.read_bytes();article.write_bytes(saved+b'\nFixture tamper.\n')
    expect_failure('stale');article.write_bytes(saved)
    briefs_path=run/'briefs.jsonl';saved_briefs=briefs_path.read_bytes();briefs=rows(briefs_path)
    briefs[0]['argument']+=' Fictional changed argument.'
    briefs_path.write_text(''.join(json.dumps(b)+'\n' for b in briefs));expect_failure('stale');briefs_path.write_bytes(saved_briefs)
    metadata=run/'run.json';saved_meta=metadata.read_bytes();value=json.loads(saved_meta);value['as_of_date']='2026-10-14'
    metadata.write_text(json.dumps(value));expect_failure('stale');metadata.write_bytes(saved_meta)
    links.write_text('{');expect_failure('Malformed publication');assert links.read_text()=='{';links.write_bytes(before)
    command_result=command(['bash','run.sh','--package',str(run)])
    assert command_result.returncode==0,command_result.stderr
    assert json.loads(command_result.stdout)['status']=='ready_for_production'
    assert links.read_bytes()==before
    assert (run/'package/articles/01.md').read_bytes()==article.read_bytes()
    approval['decision']='revise';(run/'approval.json').write_text(json.dumps(approval))
    denied=command(['bash','run.sh','--package',str(run)])
    assert denied.returncode==1 and 'approve' in denied.stderr
    (run/'approval.json').write_text('{')
    malformed=command(['bash','run.sh','--package',str(run)])
    assert malformed.returncode==1 and json.loads(malformed.stdout)['artifact_errors'][0]['artifact']=='approval.json'
    approval['decision']='approve';(run/'approval.json').write_text(json.dumps(approval));links.write_text('{')
    malformed=command(['bash','run.sh','--package',str(run)])
    assert malformed.returncode==1 and json.loads(malformed.stdout)['artifact_errors'][0]['artifact']=='package/publication_links.json'
    assert links.read_text()=='{';links.write_bytes(before)
    print('Package/CLI: missing, revise, stale, changed inputs and malformed links rejected; copies unchanged, null links and repackage preservation: PASS')

def replay(run):
    result=command(['bash','run.sh','--replay',str(run)])
    assert result.returncode==0,result.stderr
    summary=json.loads(result.stdout);replayed=ROOT/'runs'/summary['run_id']
    check=json.loads((replayed/'replay_check.json').read_text())
    assert check['passed'] and check['before']==check['after'] and check['unchanged']==44
    assert summary['operation_status']=='completed'
    metadata=json.loads((replayed/'run.json').read_text())
    assert metadata['mode']=='replay' and metadata['previous_run_id']==run.name and metadata['as_of_date']=='2026-10-13'
    assert all(c['change']=='unchanged' for c in rows(replayed/'changes.jsonl'))
    candidate=rows(replayed/'candidates.jsonl')[0];bad=dict(candidate,item_id='feed:fictional-absent')
    receipt=Receipt(replayed,'fixture-offline-miss')
    with patch.object(extract_helper,'fetch',side_effect=AssertionError('Network forbidden')),patch.object(extract_helper,'retrieve_audio',side_effect=AssertionError('Network forbidden')),patch.object(sys,'stdin',io.StringIO(json.dumps(bad)+'\n')):
        try:
            extract_helper.extract(replayed,receipt);raise AssertionError('Expected offline cache miss')
        except StageFailure as error:assert 'no saved extraction' in str(error)
    print('Temporary replay: 44 unchanged; item/version/observation counts and DB hash identical; missing extraction fails without network: PASS')
    return replayed

def policy_diff(run):
    old=[dict(item_id='fixture:'+str(i),decision='reject',piece_ids=[],reason='Old reason '+str(i)) for i in range(3)]
    old[1].update(decision='accept',piece_ids=['01'])
    new=copy.deepcopy(old);new[0].update(decision='accept',piece_ids=['01'],reason='New decision reason');new[1].update(piece_ids=['02'],reason='New piece reason')
    text,changed=diff_text(old,new)
    assert changed==['fixture:0','fixture:1'] and 'Old reason 0' in text and 'New decision reason' in text and 'New piece reason' in text
    assert not diff_text(old,old)[1]
    reordered=[dict(item_id='fixture',decision='accept',piece_ids=['01','02'],reason='Only order changed')]
    assert not diff_text(reordered,[dict(reordered[0],piece_ids=['02','01'])])[1]
    try:diff_text(old,new[:-1]);raise AssertionError('Missing item should fail')
    except StageFailure:pass
    with tempfile.TemporaryDirectory(prefix='pset4-policy-snapshot-') as directory:
        root=Path(directory).resolve();source=root/'runs/snapshot-fixture';source.mkdir(parents=True)
        for name in ['config','prompts']:
            shutil.copytree(run/name,root/name);shutil.copytree(run/name,source/name)
        (source/'run.json').write_text(json.dumps(dict(run_id=source.name,as_of_date='2026-10-09')))
        (source/'eligible.jsonl').write_bytes((run/'eligible.jsonl').read_bytes())
        (root/'config/editorial_policy.md').write_text('FICTIONAL current policy snapshot for an offline contract test.\n')
        with patch.object(run_helper,'ROOT',root),contextlib.redirect_stdout(io.StringIO()):run_helper.derivative(str(source),'policy_compare')
        derivative=next(p for p in (root/'runs').iterdir() if p!=source)
        metadata=json.loads((derivative/'run.json').read_text())
        assert metadata['mode']=='replay' and metadata['previous_run_id']==source.name and metadata['as_of_date']=='2026-10-09'
        assert (derivative/'config/editorial_policy.md').read_bytes()==(root/'config/editorial_policy.md').read_bytes()
        assert (derivative/'eligible.jsonl').read_bytes()==(source/'eligible.jsonl').read_bytes()
        assert not (derivative/'decisions.jsonl').exists()
    print('Policy helpers: complete decision/piece diff and old/new reasons; current snapshots, parent/date and saved eligible input: PASS (comparison command NOT run)')

def main():
    if len(sys.argv)!=2:raise SystemExit('usage: EVIDENCE_DIR=TEMP python3 tests/phase34_test.py EXAMPLE_RUN')
    run=Path(sys.argv[1]).resolve();metadata=json.loads((run/'run.json').read_text())
    assert metadata['mode']=='example' and metadata.get('development') and os.environ.get('EVIDENCE_DIR')
    assert Path(os.environ['EVIDENCE_DIR']).resolve()!=ROOT/'data/evidence'
    os.environ['RUN_DIR']=str(run)
    sampling(run);sources(run);length_revision(run);youtube_fallback(run);packaging(run);replayed=replay(run);policy_diff(run)
    (Path(os.environ['EVIDENCE_DIR']).parent/'contract_replay_run.txt').write_text(str(replayed)+'\n')

if __name__=='__main__':main()
