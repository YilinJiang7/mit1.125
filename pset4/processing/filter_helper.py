"""Keep D-29 through D; previously seen evidence is still eligible."""
import datetime as dt
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.records import emit, read_json, read_lines, stage_main

def reason(value, as_of):
    if value is None:
        return 'unknown_date'
    try:
        timestamp = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        day = timestamp.astimezone(dt.timezone.utc).date()
    except (ValueError, TypeError, AttributeError):
        return 'invalid_date'
    if day > as_of:
        return 'future_date'
    if day < as_of - dt.timedelta(days=29):
        return 'outside_window'
    return None

def filter_items(run_dir, receipt):
    as_of = dt.date.fromisoformat(read_json(run_dir/'run.json')['as_of_date'])
    rows = list(read_lines(sys.stdin))
    for row in rows:
        if not all(key in row for key in ['item_id','version_id','published_at']):
            raise ValueError('filter input missing item identity or publication date')
    receipt.input_count = len(rows)
    with (run_dir/'exclusions.jsonl').open('w') as exclusions:
        for row in rows:
            excluded = reason(row['published_at'], as_of)
            if excluded:
                record = dict(item_id=row['item_id'], version_id=row['version_id'], reason=excluded,
                              detail='UTC window %s through %s; published_at=%s' % (as_of-dt.timedelta(days=29),as_of,row['published_at']))
                exclusions.write(json.dumps(record)+'\n')
            else:
                emit(row)
                receipt.output_count += 1
    receipt.details['excluded_count'] = len(rows)-receipt.output_count

if __name__ == '__main__':
    stage_main('filter-items', filter_items)
