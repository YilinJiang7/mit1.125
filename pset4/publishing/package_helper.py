"""Verify review/approval fingerprints and preserve publication links on repackage."""
import datetime as dt
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT,StageFailure,emit,read_json,read_lines,stage_main
from review.check_helper import build_review
from editorial.evidence_helper import Evidence
from content.sources_helper import source_notes

def package(run_dir,receipt):
    for name in ['review.json','approval.json']:
        if not (run_dir/name).is_file():raise StageFailure('Packaging requires '+name+'; no package created')
    try:saved=read_json(run_dir/'review.json');approval=read_json(run_dir/'approval.json')
    except (ValueError,TypeError):raise StageFailure('Malformed review or approval; no package created')
    if not isinstance(saved,dict) or not isinstance(approval,dict):raise StageFailure('Review and approval must be JSON objects; no package created')
    if saved.get('passed') is not True:raise StageFailure('Packaging requires a passing review')
    if approval.get('decision')!='approve':raise StageFailure('Packaging requires a human decision of approve')
    for key in ['review_id','reviewer','reviewed_at']:
        if not isinstance(approval.get(key),str) or not approval[key].strip():raise StageFailure('Approval requires '+key)
    if not isinstance(approval.get('notes'),str):raise StageFailure('Approval requires string notes')
    try:dt.datetime.fromisoformat(approval['reviewed_at'].replace('Z','+00:00'))
    except ValueError:raise StageFailure('Approval reviewed_at must be an ISO timestamp')
    try:current=build_review(run_dir,receipt)
    except (ValueError,KeyError,TypeError,OSError) as error:raise StageFailure('Cannot verify current run inputs: '+str(error))
    if not current['passed']:raise StageFailure('Current content checks failed: '+'; '.join(i['message'] for i in current['issues'] if i['severity']=='error'))
    if current['review_id']!=saved.get('review_id') or current['review_id']!=approval['review_id']:
        raise StageFailure('Review/approval is stale: assessed drafts, briefs, references or as-of date changed')
    def rows(name):
        with (run_dir/(name+'.jsonl')).open() as stream:return list(read_lines(stream))
    articles={r['piece_id']:r for r in rows('articles')};scripts={r['piece_id']:r for r in rows('video_scripts')}
    briefs={r['piece_id']:r for r in rows('briefs')}
    folder=run_dir/'package';links_path=folder/'publication_links.json'
    if links_path.is_file():
        try:links=read_json(links_path)
        except ValueError:raise StageFailure('Malformed publication_links.json; preserved without overwriting')
        if not isinstance(links,list) or len(links)!=3 or any(not isinstance(r,dict) for r in links) or {r.get('piece_id') for r in links}!={'01','02','03'}:
            raise StageFailure('Existing publication_links.json is invalid; preserved without overwriting')
        for row in links:
            for key in ['substack_url','youtube_url']:
                if key not in row or row[key] is not None and not isinstance(row[key],str):raise StageFailure('Invalid existing publication link; preserved without overwriting')
    else:links=[dict(piece_id=p,substack_url=None,youtube_url=None) for p in ['01','02','03']]
    for name in ['articles','video_scripts','sources']:(folder/name).mkdir(parents=True,exist_ok=True)
    evidence=Evidence();pieces=[]
    for piece in ['01','02','03']:
        article=folder/'articles'/(piece+'.md');script=folder/'video_scripts'/(piece+'.md');sources=folder/'sources'/(piece+'.md')
        shutil.copyfile(ROOT/articles[piece]['path'],article);shutil.copyfile(ROOT/scripts[piece]['path'],script)
        sources.write_text(source_notes(briefs[piece],evidence))
        pieces.append(dict(piece_id=piece,article_path=str(article.resolve().relative_to(ROOT)),
                           video_script_path=str(script.resolve().relative_to(ROOT)),sources_path=str(sources.resolve().relative_to(ROOT))))
    if not links_path.exists():links_path.write_text(json.dumps(links,indent=2)+'\n')
    metadata=read_json(run_dir/'run.json')
    result=dict(run_id=metadata['run_id'],as_of_date=metadata['as_of_date'],review_id=current['review_id'],pieces=pieces,
                publication_links_path=str(links_path.resolve().relative_to(ROOT)),
                remaining_manual_steps=['Produce each audience video in Google Vids or HeyGen; review narration and visuals.',
                'Publish the approved articles on Substack with shareable access and no paid subscription requirement.',
                'Publish the three videos on YouTube (public or unlisted), with article links and source notes.',
                'Cross-link article/video pairs, verify course-staff access and record real URLs in publication_links.json.'])
    (folder/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    receipt.output_count=1;receipt.details['review_id']=current['review_id'];emit(result)

if __name__=='__main__':stage_main('prepare-package',package)
