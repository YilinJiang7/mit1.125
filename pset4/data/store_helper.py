"""SQLite items, immutable versions, run observations and duplicate flags."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT, Receipt, emit, read_json, read_lines

def version_id(item):
    payload = {key: item[key] for key in ['item_id', 'title', 'url', 'published_at', 'media_url']}
    for key in ['text_path', 'segments_path']:
        path = item[key]
        payload['sha256_' + key] = hashlib.sha256((ROOT/path).read_bytes()).hexdigest() if path else None
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()

def title_key(title):
    return re.sub(r'[^a-z0-9]', '', title.casefold())

def duplicate(item, rows):
    if item['kind'] not in ['youtube', 'podcast'] or not item['published_at']:
        return None
    for row in rows:
        other = json.loads(row[0])
        if other['item_id'] == item['item_id'] or other['kind'] == item['kind'] or other['kind'] not in ['youtube', 'podcast']:
            continue
        if title_key(other['title']) != title_key(item['title']) or not other['published_at']:
            continue
        try:
            first = dt.datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
            second = dt.datetime.fromisoformat(other['published_at'].replace('Z', '+00:00'))
            if abs((first - second).total_seconds()) <= 3*86400:
                return other.get('duplicate_of') or other['item_id']
        except ValueError:
            continue
    return None

def main():
    args = sys.argv[1:]
    command = args[0] if args else ''
    run_dir = args[1] if command == 'upsert' and len(args) == 2 else os.environ.get('RUN_DIR')
    receipt = Receipt(run_dir, 'store-' + (command or 'invalid'), ['python3', 'sqlite3'])
    code = 0
    try:
        valid = (command in ['init', 'list','stats'] and len(args) == 1 or
                 command == 'upsert' and len(args) == 2 or
                 command == 'get' and len(args) in [2, 3])
        if not valid:
            raise ValueError('usage: store.sh init | upsert RUN_DIR | list | stats | get ITEM_ID [VERSION_ID]')
        records = list(read_lines(sys.stdin)) if command == 'upsert' else []
        # Validate the entire ingestion before opening a transaction.
        for item in records:
            for field in ['item_id','source_id','publisher_id','kind','title','url','retrieved_at','version_id','text_path']:
                if not isinstance(item.get(field), str) or not item[field]:
                    raise ValueError('missing or invalid item field: ' + field)
            for field in ['published_at','media_url','segments_path']:
                if field not in item or item[field] is not None and not isinstance(item[field], str):
                    raise ValueError('invalid optional field: ' + field)
            if item['kind'] not in ['feed','youtube','podcast']:
                raise ValueError('invalid kind')
            if item['kind'] != 'feed' and not item['segments_path']:
                raise ValueError('media item requires timestamp segments')
            if version_id(item) != item['version_id']:
                raise ValueError('version fingerprint does not match assets')
        folder = Path(os.environ.get('EVIDENCE_DIR', str(ROOT/'data/evidence')))
        replay=command=='upsert' and read_json(Path(run_dir)/'run.json').get('operation')=='collection_replay'
        readonly=command in ['list','get','stats'] or replay
        database=folder/'evidence.db'
        if readonly:
            connection=sqlite3.connect(database.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)
        else:
            folder.mkdir(parents=True, exist_ok=True)
            connection=sqlite3.connect(database)
        connection.execute('PRAGMA foreign_keys=ON')
        if not readonly:connection.executescript('''
            CREATE TABLE IF NOT EXISTS items (item_id TEXT PRIMARY KEY, latest_version TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS versions (item_id TEXT NOT NULL, version_id TEXT NOT NULL,
                first_run_id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(item_id,version_id));
            CREATE TABLE IF NOT EXISTS observations (run_id TEXT NOT NULL, item_id TEXT NOT NULL,
                version_id TEXT NOT NULL, retrieved_at TEXT NOT NULL,
                PRIMARY KEY(run_id,item_id,version_id),
                FOREIGN KEY(item_id,version_id) REFERENCES versions(item_id,version_id));
        ''')
        if command == 'upsert':
            run_id = read_json(Path(run_dir)/'run.json')['run_id']
            changes = []
            with connection:
                for item in records:
                    receipt.input_count += 1
                    current = connection.execute('SELECT latest_version FROM items WHERE item_id=?', (item['item_id'],)).fetchone()
                    existing = connection.execute('SELECT 1 FROM versions WHERE item_id=? AND version_id=?', (item['item_id'],item['version_id'])).fetchone()
                    change = 'unchanged' if existing else 'changed' if current else 'new'
                    if replay:
                        if not existing:
                            raise ValueError('Read-only replay requires an existing item/version; no changes applied')
                        changes.append(dict(item_id=item['item_id'],version_id=item['version_id'],change='unchanged'))
                        continue
                    if not existing:
                        latest = connection.execute('SELECT v.record FROM versions v JOIN items i ON v.item_id=i.item_id AND v.version_id=i.latest_version').fetchall()
                        item = dict(item, duplicate_of=duplicate(item, latest))
                        connection.execute('INSERT INTO versions VALUES(?,?,?,?)', (item['item_id'],item['version_id'],run_id,json.dumps(item)))
                    connection.execute('INSERT OR REPLACE INTO items VALUES(?,?)', (item['item_id'],item['version_id']))
                    connection.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?)', (run_id,item['item_id'],item['version_id'],item['retrieved_at']))
                    changes.append(dict(item_id=item['item_id'],version_id=item['version_id'],change=change))
            for change in changes:
                emit(change)
                receipt.output_count += 1
            receipt.details['store_counts'] = {table:connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
                                               for table in ['items','versions','observations']}
            receipt.details['read_only_replay']=replay
        elif command=='stats':
            counts={table:connection.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ['items','versions','observations']}
            emit(dict(**counts,database_sha256=hashlib.sha256(database.read_bytes()).hexdigest()))
            receipt.output_count=1
            receipt.details['store_counts']=counts
        elif command == 'list':
            for row in connection.execute('SELECT v.record FROM versions v JOIN items i ON v.item_id=i.item_id AND v.version_id=i.latest_version ORDER BY v.item_id'):
                emit(json.loads(row[0]))
                receipt.output_count += 1
        elif command == 'get':
            if len(args) == 3:
                row = connection.execute('SELECT record FROM versions WHERE item_id=? AND version_id=?',args[1:]).fetchone()
            else:
                row = connection.execute('SELECT v.record FROM versions v JOIN items i ON v.item_id=i.item_id AND v.version_id=i.latest_version WHERE i.item_id=?', (args[1],)).fetchone()
            if not row:
                receipt.errors.append({'message':'item/version absent'})
                code = 1
            else:
                emit(json.loads(row[0]))
                receipt.output_count = 1
        connection.close()
    except (ValueError, KeyError, TypeError) as error:
        receipt.errors.append({'message':str(error)})
        code = 2
    except Exception as error:
        receipt.errors.append({'message':type(error).__name__})
        code = 1
    for error in receipt.errors:
        print(error['message'], file=sys.stderr)
    receipt.finish(code)
    sys.exit(code)

if __name__ == '__main__':
    main()
