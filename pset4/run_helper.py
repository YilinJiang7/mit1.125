"""Validate editorial configuration and establish immutable run snapshots."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from lib.records import ROOT, now, read_json

def validate(directory=ROOT):
    project = read_json(directory/'config/project.json')
    for key in ['publication_name','topic','audience','central_question']:
        if not isinstance(project.get(key),str) or not project[key].strip():
            raise ValueError('project requires nonempty '+key)
    sources = read_json(directory/'config/sources.json')
    if not isinstance(sources,list) or not sources:
        raise ValueError('sources must be a nonempty array')
    ids = set()
    for source in sources:
        for key in ['source_id','publisher_id','kind','url']:
            if not isinstance(source.get(key),str) or not source[key].strip():
                raise ValueError('source requires nonempty '+key)
        if source['source_id'] in ids or not all(c.isalnum() or c in '-_' for c in source['source_id']):
            raise ValueError('source IDs must be unique safe filenames')
        ids.add(source['source_id'])
        if source['kind'] not in ['feed','youtube','podcast'] or not source['url'].startswith(('https://','http://')):
            raise ValueError('source kind or URL invalid')
        if 'max_items' in source and (type(source['max_items']) is not int or source['max_items'] < 1):
            raise ValueError('max_items must be a positive integer')
    for path in [directory/'config/editorial_policy.md']+list((directory/'prompts').glob('*.md')):
        if not path.read_text().strip():
            raise ValueError('empty policy or prompt')
    for name in ['select_items','create_briefs','write_articles','write_video_scripts']:
        if not (directory/'prompts'/(name+'.md')).is_file():
            raise ValueError('missing required prompt')

def setup():
    validate()
    stamp = dt.datetime.now(dt.timezone.utc)
    run_id = stamp.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run_dir = ROOT/'runs'/run_id
    run_dir.mkdir(parents=True)
    previous = []
    for path in (ROOT/'runs').glob('*/run.json'):
        if path.parent != run_dir:
            saved=read_json(path)
            if saved.get('mode')=='live' and not saved.get('development'):
                previous.append(saved)
    previous.sort(key=lambda row:row['started_at'])
    row = dict(run_id=run_id, started_at=stamp.isoformat().replace('+00:00','Z'),
               as_of_date=str(stamp.date()),mode='live',previous_run_id=previous[-1]['run_id'] if previous else None,
               phase='editorial',development=bool(os.environ.get('EVIDENCE_DIR')),
               max_audio_minutes=float(os.environ.get('MAX_AUDIO_MINUTES','45')),
               model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'))
    (run_dir/'run.json').write_text(json.dumps(row,indent=2)+'\n')
    shutil.copytree(ROOT/'config',run_dir/'config')
    shutil.copytree(ROOT/'prompts',run_dir/'prompts')
    (run_dir/'logs').mkdir()
    print(run_dir.relative_to(ROOT))

def resume(directory):
    """Validate a saved run and print its path without creating or updating it."""
    run_dir=Path(directory).resolve()
    if run_dir.parent!=ROOT/'runs':
        raise ValueError('resume requires an existing directory directly under runs/')
    metadata=read_json(run_dir/'run.json')
    if metadata['run_id']!=run_dir.name:
        raise ValueError('saved run_id does not match its directory')
    dt.date.fromisoformat(metadata['as_of_date'])
    validate(run_dir)
    print(run_dir.relative_to(ROOT))

def derivative(directory,operation):
    """Create a labelled replay, with frozen source dates and an explicit parent."""
    source=Path(directory).resolve()
    if source.parent!=ROOT/'runs':raise ValueError('source run must be directly under runs/')
    original=read_json(source/'run.json')
    validate(source if operation=='collection_replay' else ROOT)
    stamp=dt.datetime.now(dt.timezone.utc)
    run_id=stamp.strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
    run_dir=ROOT/'runs'/run_id
    required='candidates.jsonl' if operation=='collection_replay' else 'eligible.jsonl'
    if not (source/required).is_file():raise ValueError('source run is missing '+required)
    run_dir.mkdir()
    row=dict(run_id=run_id,started_at=stamp.isoformat().replace('+00:00','Z'),as_of_date=original['as_of_date'],
             mode='replay',previous_run_id=original['run_id'],source_run_dir=str(source.relative_to(ROOT)),
             operation=operation,development=bool(os.environ.get('EVIDENCE_DIR')),phase='repeatability',
             max_audio_minutes=original.get('max_audio_minutes',45),model=os.environ.get('OPENAI_MODEL','gpt-4.1-mini'))
    (run_dir/'run.json').write_text(json.dumps(row,indent=2)+'\n')
    snapshots=source if operation=='collection_replay' else ROOT
    for name in ['config','prompts']:shutil.copytree(snapshots/name,run_dir/name)
    shutil.copy(source/required,run_dir/required)
    (run_dir/'logs').mkdir()
    print(run_dir.relative_to(ROOT))

if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['setup']:
            setup()
        elif sys.argv[1:] == ['validate']:
            validate()
        elif len(sys.argv)==3 and sys.argv[1]=='resume':
            resume(sys.argv[2])
        elif len(sys.argv)==3 and sys.argv[1] in ['replay','policy-compare']:
            derivative(sys.argv[2],'collection_replay' if sys.argv[1]=='replay' else 'policy_compare')
        else:
            raise ValueError('usage: run_helper.py validate | setup | resume RUN_DIR')
    except (ValueError,KeyError,TypeError,OSError) as error:
        print('run configuration invalid: '+str(error),file=sys.stderr)
        sys.exit(2)
