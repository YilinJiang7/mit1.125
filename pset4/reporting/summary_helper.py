"""Report review readiness separately from collection failures and unknown costs."""
import collections
import datetime as dt
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import emit, read_json, read_lines, stage_main

def summarize(run_dir,receipt):
    run=read_json(run_dir/'run.json')
    artifact_errors=[]
    def optional_json(name,expected=dict):
        path=run_dir/name
        if not path.is_file() or not path.stat().st_size:return None
        try:
            value=read_json(path)
            if not isinstance(value,expected):raise ValueError('Unexpected JSON shape')
            return value
        except (ValueError,OSError):
            artifact_errors.append(dict(artifact=name,message='Malformed or unreadable saved JSON'))
            return None
    def rows(name):
        path=run_dir/(name+'.jsonl')
        if not path.is_file():return None
        with path.open() as stream:return list(read_lines(stream))
    names=['candidates','items','changes','eligible','exclusions','decisions','briefs','articles','video_scripts']
    artifacts={name:rows(name) for name in names}
    receipts=[read_json(path) for path in sorted((run_dir/'logs').glob('*.json'))]
    counts={key:len(artifacts[name]) if artifacts[name] is not None else None for key,name in
            [('discovered','candidates'),('extracted','items'),('eligible','eligible'),('excluded','exclusions'),('briefs','briefs'),('articles','articles'),('video_scripts','video_scripts')]}
    for key in ['new','changed','unchanged']:
        counts[key]=sum(row['change']==key for row in artifacts['changes']) if artifacts['changes'] is not None else None
    for key,value in [('accepted','accept'),('rejected','reject'),('deferred','defer')]:
        counts[key]=sum(row['decision']==value for row in artifacts['decisions']) if artifacts['decisions'] is not None else None
    eligible=artifacts['eligible'] or []
    distinct={row['item_id']:row for row in eligible if not row.get('duplicate_of')}
    def coverage(items):
        items=list(items)
        by_kind={kind:sum(row['kind']==kind for row in items) for kind in ['feed','youtube','podcast']}
        by_publisher=dict(collections.Counter(row['publisher_id'] for row in items))
        return dict(distinct_items=len(items),publisher_count=len(by_publisher),publishers=sorted(by_publisher),
                    by_kind=by_kind,by_publisher=by_publisher,
                    passed=len(items)>=12 and len(by_publisher)>=6 and all(value>=2 for value in by_kind.values()))
    collected_coverage=coverage(distinct.values())
    accepted_ids={r['item_id'] for r in artifacts['decisions'] or [] if r['decision']=='accept'}
    accepted_coverage=coverage(row for key,row in distinct.items() if key in accepted_ids)
    used_ids={r['item_id'] for brief in artifacts['briefs'] or [] for claim in brief.get('claims',[]) for r in claim.get('evidence',[])}
    used_coverage=coverage(row for key,row in distinct.items() if key in used_ids)
    failed=[row for row in receipts if row['status']=='failed' and row['stage']!='store-get']
    collection_failures=[row for row in failed if row['stage'] in ['fetch-feeds','fetch-youtube','fetch-podcasts','extract-content','store-init','store-upsert','store-list','filter-items','collect-sources']]
    collection_status='completed' if collected_coverage['passed'] and not collection_failures else 'incomplete'
    review=optional_json('review.json')
    complete=counts['briefs']==counts['articles']==counts['video_scripts']==3 and artifacts['decisions'] is not None and len(artifacts['decisions'])==len(eligible)
    status='awaiting_review' if complete and review and review['passed'] and collected_coverage['passed'] else 'failed'
    approval=optional_json('approval.json')
    if status=='awaiting_review' and approval and approval.get('decision')=='approve' and approval.get('review_id')==review['review_id'] and (run_dir/'package/manifest.json').is_file():
        status='ready_for_production'
    stages={'collect-sources':'eligible.jsonl','select-items':'decisions.jsonl','create-briefs':'briefs.jsonl',
            'write-articles':'articles.jsonl','write-video-scripts':'video_scripts.jsonl','check-content':'review.json'}
    incomplete=[]
    for stage,artifact in stages.items():
        previous=[r for r in receipts if r['stage']==stage]
        latest=max(previous,key=lambda r:r['finished_at']) if previous else None
        if not (run_dir/artifact).is_file() or not latest or latest['status']=='failed':incomplete.append(stage)
    models=[model for row in receipts for model in row.get('models',[])]
    known=[row['cost_usd'] for row in receipts if row.get('cost_usd') is not None]
    unknown=[dict(stage=row['stage'],request_path=model.get('request_path')) for row in receipts for model in row.get('models',[]) if model.get('cost_usd') is None]
    unknown.extend(dict(stage=row['stage'],request_path=None) for row in receipts if row.get('cost_usd') is None and not row.get('models'))
    known_cost=sum(known) if known else None
    links=optional_json('package/publication_links.json',list)
    replay_check=optional_json('replay_check.json')
    policy_diff=optional_json('policy_diff.json')
    operation=run.get('operation')
    operation_complete=bool(replay_check and replay_check['passed']) if operation=='collection_replay' else bool(policy_diff is not None) if operation=='policy_compare' else None
    detail='Drafts passed mechanical checks; human review is required. Collection failures remain listed.' if status=='awaiting_review' else 'Inspect stage failures and review issues before proceeding.'
    actions=['Inspect drafts, synthesis and evidence; provide approval.json with the current review_id.','Render videos in Google Vids or HeyGen, then publish articles/videos.'] if status=='awaiting_review' else ['Repair incomplete stages and blocking review issues.']
    if status=='ready_for_production':
        detail='Approved current content is packaged; production and publishing remain manual.'
        actions=read_json(run_dir/'package/manifest.json').get('remaining_manual_steps',[])
    if operation:
        detail=('Read-only collection replay verified unchanged evidence.' if operation=='collection_replay' else 'Policy comparison completed using saved eligible evidence.') if operation_complete else 'Replay/comparison incomplete; inspect its receipt.'
        detail+=' Draft generation and content review were not run in this labelled replay.'
        actions=['Inspect the replay/comparison evidence; continue the editorial review separately.']
    if artifact_errors:
        status='failed';detail='Saved review, approval or publication metadata is invalid; inspect artifact_errors.'
        actions=['Repair the malformed saved JSON before continuing.']
    receipt.input_count=len(receipts)
    receipt.output_count=1
    emit(dict(run_id=run['run_id'],as_of_date=run['as_of_date'],mode=run['mode'],status=status,phase=run.get('phase'),
              collection_status=collection_status,editorial_status='completed' if complete and review and review['passed'] else 'incomplete',
              status_detail=detail,artifact_errors=artifact_errors,operation=operation,operation_status='completed' if operation_complete else 'incomplete' if operation else None,replay_check=replay_check,policy_diff=policy_diff,
              counts=counts,coverage=collected_coverage,accepted_coverage=accepted_coverage,series_coverage=used_coverage,
              duplicate_observations=[dict(item_id=r['item_id'],duplicate_of=r['duplicate_of']) for r in eligible if r.get('duplicate_of')],
              limited_content=[dict(item_id=r['item_id'],content_access=r['content_access']) for r in eligible if r.get('content_access') in ['paywall_preview','public_text_with_paid_bonus']],
              source_checks=[check for row in receipts for check in row.get('sources',[])],
              source_attempt_failures=[dict(source_id=check['source_id'],**attempt) for row in receipts for check in row.get('sources',[]) for attempt in check.get('attempts',[]) if attempt['status']=='failed'],
              failed_stages=[dict(stage=r['stage'],exit_code=r.get('exit_code'),errors=r['errors']) for r in failed],incomplete_stages=incomplete,
              elapsed_seconds=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(run['started_at'].replace('Z','+00:00'))).total_seconds(),
              tools=sorted({tool for row in receipts for tool in row.get('tools',[])}),models=models,
              failed_model_calls=[dict(stage=r['stage'],**m) for r in receipts for m in r.get('models',[]) if m.get('status')=='failed'],
              input_tokens=sum(m.get('input_tokens') or 0 for m in models) if models else None,
              output_tokens=sum(m.get('output_tokens') or 0 for m in models) if models else None,
              cost_usd=known_cost if not unknown else None,known_cost_usd=known_cost,cost_is_estimate=any(r.get('cost_is_estimate') for r in receipts),unknown_costs=unknown,
              simulated=any(r.get('simulated',False) for r in receipts),review=review,publication_links=links,
              remaining_manual_actions=actions))

if __name__=='__main__':
    stage_main('summarize-run',summarize)
