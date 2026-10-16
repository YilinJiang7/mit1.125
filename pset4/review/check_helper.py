"""Mechanical content assessment and reproducible fingerprints, never human approval."""
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT, StageFailure, emit, read_json, read_lines, stage_main
from editorial.evidence_helper import Evidence,validate_briefs
from processing.filter_helper import reason
import datetime as dt
from content.word_counts import word_count

def build_review(run_dir,receipt):
    issues=[]
    fingerprint={}
    def issue(artifact,message,severity='error',piece=None):
        row=dict(artifact=artifact,severity=severity,message=message)
        if piece:row['piece_id']=piece
        issues.append(row)
    def load(name):
        path=run_dir/(name+'.jsonl')
        fingerprint[name]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if not path.is_file():
            issue(str(path),'Required artifact missing');return []
        try:
            with path.open() as stream:return list(read_lines(stream))
        except ValueError:
            issue(str(path),'Malformed JSONL artifact');return []
    run=read_json(run_dir/'run.json')
    as_of=dt.date.fromisoformat(run['as_of_date'])
    fingerprint['as_of_date']=run['as_of_date']
    briefs=load('briefs')
    manifests={name:load(name) for name in ['articles','video_scripts']}
    evidence=Evidence()
    decisions=load('decisions')
    accepted={(r.get('item_id'),r.get('version_id')) for r in decisions if r.get('decision')=='accept'}
    try:
        for error in validate_briefs(briefs,evidence,accepted):issue('briefs.jsonl',error)
    except (TypeError,KeyError,ValueError):
        issue('briefs.jsonl','Malformed brief fields prevent evidence validation')
    claims={}
    for brief in briefs:
        piece=brief.get('piece_id')
        if piece not in ['01','02','03']:continue
        valid_claims=brief.get('claims',[]) if isinstance(brief.get('claims'),list) else []
        claims[piece]={c['claim_id']:c for c in valid_claims if isinstance(c,dict) and isinstance(c.get('claim_id'),str)}
        for claim in claims[piece].values():
            refs=claim.get('evidence',[]) if isinstance(claim.get('evidence'),list) else []
            for reference in refs:
                try:
                    item,_=evidence.resolve(reference)
                    if reason(item['published_at'],as_of):issue('briefs.jsonl','Referenced publication date is outside the UTC window',piece=piece)
                    key=item['item_id']+'@'+item['version_id']
                    fingerprint[key]={'reference':reference,'text_sha256':hashlib.sha256((ROOT/item['text_path']).read_bytes()).hexdigest(),
                                      'segments_sha256':hashlib.sha256((ROOT/item['segments_path']).read_bytes()).hexdigest() if item['segments_path'] else None}
                except (StageFailure,KeyError,TypeError,OSError,ValueError) as error:
                    issue('briefs.jsonl',str(error),piece=piece)
        issue('briefs.jsonl','Needs human judgment: inspect synthesis, evidence support, incentives and limitations.','warning',piece)
    marker_sets={}
    word_counts={}
    for name,rows in manifests.items():
        ids=[row.get('piece_id') for row in rows]
        if len(ids)!=3 or set(ids)!={'01','02','03'}:issue(name+'.jsonl','Exactly three distinct piece manifests required')
        for row in rows:
            piece=row.get('piece_id')
            path_value=row.get('path')
            if not isinstance(path_value,str):
                issue(name+'.jsonl','Manifest path required',piece=piece);continue
            path=ROOT/path_value
            fingerprint[path_value]=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
            if not path.is_file():
                issue(path_value,'Draft file missing',piece=piece);continue
            text=path.read_text()
            body=text.split('\n## Sources',1)[0]
            markers=set(re.findall(r'\[(\d{2}-c\d+)\]',body))
            expected=set(claims.get(piece,{}))
            marker_sets[(name,piece)]=markers
            if set(re.findall(r'\[(\d{2}-c\d+)\]',text))-expected:issue(path_value,'Unknown claim marker in draft or source notes',piece=piece)
            if markers!=expected:issue(path_value,'Body markers do not match the brief claim set',piece=piece)
            if set(row.get('claim_ids',[]))!=expected:issue(path_value,'Manifest claim_ids do not match the brief',piece=piece)
            if '\n## Sources\n' not in text:issue(path_value,'Code-generated source notes missing',piece=piece)
            if name=='articles':
                count=word_count(body,'article')
                low,high=600,900
            else:
                narration=re.findall(r'\*\*Narration\s*:?\*\*\s*:?\s*(.*?)(?=\*\*(?:On screen|Sources)\s*:?\*\*|\n#{1,3} |\Z)',body,re.S|re.I)
                count=word_count(body,'script')
                low,high=450,700
                if not narration:issue(path_value,'No inspectable Narration fields found',piece=piece)
            if not low<=count<=high:issue(path_value,'Approximate word count %d; target %d-%d'%(count,low,high),'warning',piece)
            word_counts.setdefault(piece,{})['article' if name=='articles' else 'spoken']=count
    for piece in ['01','02','03']:
        if marker_sets.get(('articles',piece))!=marker_sets.get(('video_scripts',piece)):
            issue('manifests','Article/script claim sets differ',piece=piece)
    review_id=hashlib.sha256(json.dumps(fingerprint,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    result=dict(review_id=review_id,passed=not any(row['severity']=='error' for row in issues),issues=issues,word_counts=word_counts)
    receipt.input_count=len(briefs)+sum(len(rows) for rows in manifests.values())
    receipt.output_count=1
    return result

def assess(run_dir,receipt):
    emit(build_review(run_dir,receipt))

if __name__=='__main__':
    stage_main('check-content',assess)
