"""Compare saved editorial decisions without changing either policy or run."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT,emit,read_json,read_lines,stage_main,StageFailure

def diff_text(old,new):
    old={r['item_id']:r for r in old};new={r['item_id']:r for r in new}
    if set(old)!=set(new):raise StageFailure('Policy comparison must contain the same item IDs')
    lines=['# Editorial policy comparison','']
    changed=[]
    for item_id in sorted(old):
        before,after=old[item_id],new[item_id]
        if before['decision']==after['decision'] and set(before['piece_ids'])==set(after['piece_ids']):continue
        changed.append(item_id)
        lines+=['## '+item_id,'','Old: '+before['decision']+'; pieces '+json.dumps(before['piece_ids']),
                'Old reason: '+before['reason'],'','New: '+after['decision']+'; pieces '+json.dumps(after['piece_ids']),
                'New reason: '+after['reason'],'']
    if not changed:lines+=['No decisions or piece assignments changed.','']
    return '\n'.join(lines),changed

def compare(run_dir,receipt):
    source=ROOT/read_json(run_dir/'run.json')['source_run_dir']
    def rows(path):
        with path.open() as stream:return list(read_lines(stream))
    old=rows(source/'decisions.jsonl');new=rows(run_dir/'decisions.jsonl')
    text,changed=diff_text(old,new)
    (run_dir/'policy_diff.md').write_text(text)
    result={'changed_item_ids':changed,'changed_count':len(changed)}
    (run_dir/'policy_diff.json').write_text(json.dumps(result,indent=2)+'\n')
    receipt.input_count=len(old);receipt.output_count=len(changed);emit(result)

if __name__=='__main__':stage_main('policy-diff',compare)
