"""Evidence excerpts and brief validation; the store remains the index owner."""
import json
from pathlib import Path
import re
import subprocess
from lib.records import ROOT, StageFailure, read_json
from editorial.excerpt_helper import sample_segments

def stamp(value):
    value = int(value)
    return '%02d:%02d' % (value//60,value%60)

class Evidence:
    def __init__(self,project=None,receipt=None):
        self.cache = {}
        self.project=project or {}
        self.receipt=receipt

    def get(self, item_id, version_id):
        key = (item_id,version_id)
        if key not in self.cache:
            result = subprocess.run(['bash','data/store.sh','get',item_id,version_id],cwd=ROOT,capture_output=True,text=True)
            if result.returncode != 0:
                raise StageFailure('Evidence version is absent or unreadable: '+item_id+' / '+version_id)
            self.cache[key] = json.loads(result.stdout)
        return self.cache[key]

    def excerpt(self, item, limit=6000):
        record = {key:item[key] for key in ['item_id','version_id','source_id','publisher_id','kind','title','url','published_at']}
        for key in ['duplicate_of','content_access','extraction_method','max_audio_minutes','audio_cap_applied','transcript_end_seconds']:
            if key in item:record[key]=item[key]
        text = (ROOT/item['text_path']).read_text()
        if item['segments_path']:
            segments=read_json(ROOT/item['segments_path'])
            record['excerpt'],details=sample_segments(segments,self.project,limit,stamp)
            record['excerpt_truncated']=len(details['selected_segment_ids'])<len(segments)
            record['excerpt_sampling']=details
            if self.receipt:
                self.receipt.details.setdefault('excerpt_sampling',[]).append(dict(item_id=item['item_id'],**details))
        else:
            record['excerpt'] = text[:limit]
            record['excerpt_truncated'] = len(text)>limit
        return record

    def resolve(self, reference):
        item = self.get(reference['item_id'],reference['version_id'])
        locator = reference['locator']
        if locator.get('type') == 'text':
            if item['kind'] != 'feed' or not isinstance(locator.get('quote'),str) or not locator['quote']:
                raise StageFailure('Written reference requires a nonempty exact quote from feed evidence')
            if locator['quote'] not in (ROOT/item['text_path']).read_text():
                raise StageFailure('Quote is not an exact substring: '+reference['item_id'])
            return item,None
        if locator.get('type') == 'segment' and item['kind'] in ['youtube','podcast']:
            values = read_json(ROOT/item['segments_path'])
            segment = next((s for s in values if s['segment_id']==locator.get('segment_id')),None)
            if not segment:
                raise StageFailure('Segment does not exist: '+str(locator.get('segment_id'))+' in '+item['item_id'])
            return item,segment
        raise StageFailure('Locator type does not match the evidence kind')

def validate_briefs(briefs, evidence, allowed=None):
    errors = []
    if not isinstance(briefs,list):
        return ['briefs must be an array']
    ids = [b.get('piece_id') for b in briefs if isinstance(b,dict)]
    if len(briefs)!=3 or set(ids)!={'01','02','03'}:
        errors.append('Exactly three distinct briefs 01, 02, 03 are required')
    kinds = set()
    for brief in briefs:
        if not isinstance(brief,dict):
            errors.append('Brief must be an object');continue
        piece = brief.get('piece_id','?')
        for key in ['title','question','argument','synthesis','limitations']:
            if not isinstance(brief.get(key),str) or not brief[key].strip():
                errors.append(piece+': missing/non-string '+key)
        claims = brief.get('claims')
        if not isinstance(claims,list) or not 4<=len(claims)<=8:
            errors.append(piece+': requires 4-8 claims');continue
        seen = set()
        publishers = set()
        inference = False
        for claim in claims:
            if not isinstance(claim,dict):
                errors.append(piece+': claim must be an object');continue
            claim_id = claim.get('claim_id','')
            if not isinstance(claim_id,str) or not re.fullmatch(re.escape(piece)+r'-c[1-9]\d*',claim_id) or claim_id in seen:
                errors.append(piece+': invalid or duplicate claim_id '+str(claim_id))
            seen.add(claim_id)
            if claim.get('type') not in ['reported_fact','source_claim','inference']:
                errors.append(str(claim_id)+': invalid claim type')
            if not isinstance(claim.get('statement'),str) or not claim['statement'].strip():
                errors.append(str(claim_id)+': statement required')
            refs = claim.get('evidence')
            if not isinstance(refs,list) or not refs:
                errors.append(str(claim_id)+': evidence required');continue
            linked = set()
            for reference in refs:
                try:
                    key = (reference['item_id'],reference['version_id'])
                    if allowed is not None and key not in allowed:
                        raise StageFailure('Reference is not in the ACCEPTED evidence: '+reference['item_id'])
                    item,_ = evidence.resolve(reference)
                    linked.add(item['publisher_id'])
                    publishers.add(item['publisher_id'])
                    kinds.add(item['kind'])
                except (StageFailure,KeyError,TypeError,OSError,ValueError) as error:
                    errors.append(str(claim_id)+': '+str(error))
            if claim.get('type')=='inference' and len(linked)>=2:
                inference = True
        if len(publishers)<3:
            errors.append(piece+': requires at least 3 distinct publishers; got '+str(len(publishers))+' ('+', '.join(sorted(publishers))+'); multiple items from one publisher count once')
        if not inference:
            errors.append(piece+': requires an inference linking at least 2 publishers')
    if kinds != {'feed','youtube','podcast'}:
        errors.append('Series must use feed, youtube and podcast; got '+', '.join(sorted(kinds)))
    return errors
