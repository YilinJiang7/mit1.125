"""RSS/Atom metadata parsing shared by the feed and podcast collectors."""
import datetime as dt
import email.utils
import hashlib
from pathlib import Path
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.records import emit, now, read_json, stage_main

def download(url):
    request = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Apprentice Mode source collector)'})
    with urllib.request.urlopen(request, timeout=35) as response:
        return response.read()

def canonical(url):
    parts = urllib.parse.urlsplit(url)
    query = [(key,value) for key,value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith('utm_') and key.lower() not in ['fbclid','gclid','mc_cid','mc_eid']]
    return urllib.parse.urlunsplit((parts.scheme,parts.netloc.lower(),parts.path.rstrip('/'),urllib.parse.urlencode(query),''))

def published(value):
    if not value:
        return None
    try:
        try:
            value = dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        except ValueError:
            value = email.utils.parsedate_to_datetime(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=dt.timezone.utc)
        return value.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z')
    except (ValueError, TypeError):
        return None

def parse_feed(body, source):
    root = ET.fromstring(body)
    rows = []
    for entry in root.findall('.//item') + root.findall('{http://www.w3.org/2005/Atom}entry'):
        fields = {}
        transcripts = []
        for child in entry:
            tag = child.tag.split('}')[-1]
            if tag == 'link' and child.attrib.get('rel','alternate') == 'alternate':
                fields['url'] = child.attrib.get('href') or child.text
            elif tag == 'enclosure':
                fields['media_url'] = child.attrib.get('url')
            elif tag == 'transcript':
                transcripts.append(child.attrib)
            elif tag in ['title','published','pubDate','guid','encoded','description','content','summary','videoId']:
                fields[tag] = child.text
        if not fields.get('url') or not fields.get('title'):
            raise ValueError('feed entry missing title or URL')
        url = canonical(fields['url'])
        kind = source['kind']
        identity = fields.get('videoId') if kind == 'youtube' else fields.get('guid') or fields.get('media_url') if kind == 'podcast' else url
        if not identity:
            raise ValueError('podcast missing GUID and enclosure URL')
        item_id = kind + ':' + (identity if kind == 'youtube' else hashlib.sha1(identity.encode()).hexdigest())
        rows.append(dict(item_id=item_id, source_id=source['source_id'], publisher_id=source['publisher_id'],
                         kind=kind, title=fields['title'], url=url,
                         published_at=published(fields.get('published') or fields.get('pubDate')),
                         retrieved_at=now(), media_url=fields.get('media_url'),
                         feed_text=fields.get('encoded') or fields.get('content') or fields.get('description') or fields.get('summary') or '',
                         transcript_urls=transcripts))
    return rows

def limited(rows, source, run_dir):
    # Prefer dated, recent candidates before spending time extracting media.
    as_of = dt.date.fromisoformat(read_json(run_dir/'run.json')['as_of_date'])
    start = as_of - dt.timedelta(days=29)
    recent = [row for row in rows if row['published_at'] and start <= dt.date.fromisoformat(row['published_at'][:10]) <= as_of]
    return sorted(recent, key=lambda row:row['published_at'], reverse=True)[:source.get('max_items', len(recent))]

def collect(run_dir, receipt, kind):
    coverage = []
    for source in read_json(run_dir/'config/sources.json'):
        if source['kind'] != kind:
            continue
        receipt.input_count += 1
        check = {'source_id':source['source_id'], 'status':'completed'}
        try:
            if os.environ.get('SIMULATE_FAIL_SOURCE') == source['source_id']:
                check['simulated'] = True
                receipt.details['simulated'] = True
                raise OSError('simulated source failure')
            body = download(source['url'])
            media = Path('data/media') / read_json(run_dir/'run.json')['run_id']
            media.mkdir(parents=True, exist_ok=True)
            (media/(source['source_id']+'.xml')).write_bytes(body)
            rows = limited(parse_feed(body, source), source, run_dir)
            check['output_count'] = len(rows)
            for row in rows:
                emit(row)
                receipt.output_count += 1
        except Exception as error:
            check['status'] = 'failed'
            check['message'] = 'simulated source failure' if check.get('simulated') else type(error).__name__ + (': HTTP '+str(error.code) if hasattr(error,'code') else '')
            receipt.errors.append(check)
        coverage.append(check)
    receipt.details['sources'] = coverage
    return 1 if receipt.errors else 0

if __name__ == '__main__':
    stage_main('fetch-feeds', lambda run, receipt:collect(run, receipt, 'feed'))
