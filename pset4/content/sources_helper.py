"""Build audience-readable source notes in code from validated evidence locators."""
from editorial.evidence_helper import stamp
import json

def source_notes(brief,evidence):
    lines=['## Sources','']
    groups={}
    for claim in brief['claims']:
        for reference in claim['evidence']:
            key=(reference['item_id'],json.dumps(reference['locator'],sort_keys=True))
            group=groups.setdefault(key,{'reference':reference,'claim_ids':[]})
            if claim['claim_id'] not in group['claim_ids']:group['claim_ids'].append(claim['claim_id'])
    for group in groups.values():
        reference=group['reference']
        item,segment=evidence.resolve(reference)
        url=item['url']
        timing=''
        if segment:
            timing='; '+stamp(segment['start_seconds'])+'–'+stamp(segment['end_seconds'])
            if item['kind']=='youtube':
                url='https://www.youtube.com/watch?v='+item['item_id'].split(':',1)[1]+'&t='+str(int(segment['start_seconds']))
        title=item['title'].replace('[','(').replace(']',')')
        passage=''
        if not segment:passage='; passage: '+json.dumps(reference['locator']['quote'],ensure_ascii=False)
        markers=' '.join('['+claim_id+']' for claim_id in group['claim_ids'])
        lines.append('- %s [%s](%s) — %s; published %s%s%s.' % (markers,title,url,item['publisher_id'],item['published_at'][:10],timing,passage))
    return '\n'.join(lines)+'\n'
