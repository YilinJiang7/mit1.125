"""Sample timed evidence across the retained transcript, within a character cap."""
import re

STOP=set('a an and are as at be by can do for from how in is it of on or that the their this to what which with your you month people should'.split())
SPONSOR=re.compile(r"today(?:'s|’s) sponsor|sponsored by|thanks to .{0,70} for sponsoring|thanks to our sponsor|(?:episode|show|podcast|video) (?:is )?brought to you by|a word from our sponsor|promo code|discount code|quick (?:break|word) for|use (?:my|our) code",re.I)

def sample_segments(segments,project,limit,stamp):
    text=' '.join(str(project.get(key,'')) for key in ['topic','central_question','scope_includes'])
    keywords={word.rstrip('s') for word in re.findall(r'\b[a-z][a-z-]{1,}\b',text.lower()) if word not in STOP}
    usable=[]
    sponsor_until=-1
    skipped=[]
    for index,segment in enumerate(segments):
        if SPONSOR.search(segment['text']):sponsor_until=segment['start_seconds']+120
        if segment['start_seconds']<=sponsor_until:
            skipped.append(segment['segment_id']);continue
        usable.append(index)
    priorities=[]
    if usable:
        start=segments[usable[0]]['start_seconds'];end=segments[usable[-1]]['start_seconds']
        # Four short windows distribute the first half of the budget over time.
        for n in range(4):
            target=start+(end-start)*n/3
            index=min(usable,key=lambda i:abs(segments[i]['start_seconds']-target))
            if index not in priorities:priorities.append(index)
    def score(index):
        words={w.rstrip('s') for w in re.findall(r'\b[a-z][a-z-]{1,}\b',segments[index]['text'].lower())}
        return len(words & keywords)
    ranked=sorted(usable,key=lambda i:(-score(i),i))
    # Reserve coverage across time before filling with relevant segments.
    order=priorities+[i for i in ranked if score(i)>0]
    order.extend(usable)
    selected=[];used=0
    def line_for(index):
        s=segments[index]
        return '[%s %s] %s'%(s['segment_id'],stamp(s['start_seconds']),re.sub(r'\s+',' ',s['text']).strip())
    for index in order:
        if index in selected:continue
        line=line_for(index)
        if used+len(line)+1<=limit:
            selected.append(index);used+=len(line)+1
    selected.sort()
    lines=[line_for(i) for i in selected]
    details={'method':'evenly_spaced_windows_and_project_keyword_matches','character_limit':limit,
             'character_count':used,'total_segments':len(segments),'selected_segment_ids':[segments[i]['segment_id'] for i in selected],
             'skipped_sponsor_segment_ids':skipped,'topic_keywords':sorted(keywords),
             'selected_span_seconds':[segments[selected[0]]['start_seconds'],segments[selected[-1]]['end_seconds']] if selected else None}
    return '\n'.join(lines),details
