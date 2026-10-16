"""Prefer channel RSS dates; fall back to flat IDs plus per-video upload dates."""
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.parse
from feeds_helper import download, limited, parse_feed, published
from lib.records import emit, now, read_json, stage_main

def fetch_attempts(urls, label, attempts):
    for index,url in enumerate(urls):
        try:
            body=download(url)
            attempts.append({'endpoint':label,'attempt':index+1,'status':'completed'})
            return body
        except Exception as error:
            attempts.append({'endpoint':label,'attempt':index+1,'status':'failed','message':type(error).__name__+(': HTTP '+str(error.code) if hasattr(error,'code') else '')})
            if index==len(urls)-1:raise

def yt_metadata(url):
    p=subprocess.run(['yt-dlp','--skip-download','--no-playlist','--dump-single-json','--no-warnings','--retries','0','--socket-timeout','20',url],capture_output=True,timeout=90)
    if p.returncode:raise OSError('yt-dlp per-video metadata failed')
    return json.loads(p.stdout)

def yt_discover(source,run_dir,attempts):
    url=source['url']
    if 'feeds/videos.xml' in url:
        channel_id=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('channel_id',[''])[0]
        if not channel_id:raise OSError('Channel RSS URL has no channel_id')
        url='https://www.youtube.com/channel/'+channel_id
    if '/@' in url or '/channel/' in url:
        if not url.rstrip('/').endswith(('/videos','/shorts','/streams')):url=url.rstrip('/')+'/videos'
    try:
        p=subprocess.run(['yt-dlp','--flat-playlist','--dump-single-json','--playlist-end',str(max(12,source.get('max_items',3)*4)),
                          '--no-warnings','--retries','0','--socket-timeout','20',url],capture_output=True,timeout=120)
    except Exception as error:
        attempts.append({'endpoint':'yt-dlp-flat-playlist','status':'failed','message':type(error).__name__})
        raise OSError('yt-dlp flat playlist request failed')
    if p.returncode:
        attempts.append({'endpoint':'yt-dlp-flat-playlist','status':'failed','message':'yt-dlp flat playlist failed'})
        raise OSError('yt-dlp flat playlist failed')
    attempts.append({'endpoint':'yt-dlp-flat-playlist','status':'completed'})
    entries=json.loads(p.stdout)
    rows=[];errors=[]
    for entry in entries.get('entries',[entries]):
        if not entry or not entry.get('id'):continue
        video_id=entry['id']
        try:
            video=yt_metadata('https://www.youtube.com/watch?v='+video_id)
            date=video.get('upload_date')
            if not date or not re.fullmatch(r'\d{8}',date):raise OSError('Video upload_date absent')
            date=published(date[:4]+'-'+date[4:6]+'-'+date[6:8]+'T00:00:00Z')
            if not date:raise OSError('Video upload_date invalid')
            attempts.append({'endpoint':'yt-dlp-video-metadata','video_id':video_id,'status':'completed','published_at':date,'title':video['title']})
            rows.append(dict(item_id='youtube:'+video_id,source_id=source['source_id'],publisher_id=source['publisher_id'],kind='youtube',
                             title=video['title'],url='https://www.youtube.com/watch?v='+video_id,published_at=date,retrieved_at=now(),media_url=None,
                             discovery_method='yt_dlp_flat_playlist_and_video_metadata'))
            if len(limited(rows,source,run_dir))>=source.get('max_items',3):break
        except Exception as error:
            attempts.append({'endpoint':'yt-dlp-video-metadata','video_id':video_id,'status':'failed','message':type(error).__name__})
            errors.append(error)
    if not rows and errors:raise OSError('All per-video metadata requests failed')
    return limited(rows,source,run_dir)

def discover(source, run_dir, attempts):
    url = source['url']
    if '/@' in url or '/channel/' in url or 'feeds/videos.xml' in url:
        try:
            channel = re.search(r'/channel/(UC[\w-]{22})', url)
            if '/@' in url:
                page = fetch_attempts([url,url.rstrip('/')+'/videos'],'handle',attempts).decode('utf-8', errors='replace')
                channel = re.search(r'"externalId":"(UC[\w-]{22})"', page) or re.search(r'channel_id=(UC[\w-]{22})', page)
                if not channel:raise OSError('cannot resolve channel handle')
            rss='https://www.youtube.com/feeds/videos.xml?channel_id='+channel.group(1) if channel else url
            body=fetch_attempts([rss,rss],'channel-rss',attempts)
            media=Path('data/media')/read_json(run_dir/'run.json')['run_id'];media.mkdir(parents=True,exist_ok=True)
            (media/(source['source_id']+'.xml')).write_bytes(body)
            return [dict(row,discovery_method='channel_rss') for row in limited(parse_feed(body,source),source,run_dir)]
        except Exception as error:
            attempts.append({'endpoint':'rss-discovery','status':'failed','message':type(error).__name__})
    return yt_discover(source,run_dir,attempts)

def collect(run_dir, receipt):
    checks = []
    for source in read_json(run_dir/'config/sources.json'):
        if source['kind'] != 'youtube':
            continue
        receipt.input_count += 1
        check = {'source_id':source['source_id'], 'status':'completed'}
        check['attempts']=[]
        try:
            if os.environ.get('SIMULATE_FAIL_SOURCE') == source['source_id']:
                check['simulated'] = True
                receipt.details['simulated'] = True
                raise OSError('simulated source failure')
            rows = discover(source, run_dir, check['attempts'])
            check['output_count'] = len(rows)
            check['method']=rows[0]['discovery_method'] if rows else ('yt_dlp_flat_playlist_and_video_metadata' if any(a['endpoint']=='yt-dlp-flat-playlist' for a in check['attempts']) else 'channel_rss')
            for row in rows:
                emit(row)
                receipt.output_count += 1
        except Exception as error:
            check.update(status='failed',message='simulated source failure' if check.get('simulated') else type(error).__name__ + (': HTTP '+str(error.code) if hasattr(error,'code') else ''))
            receipt.errors.append(check)
        checks.append(check)
    receipt.details['sources'] = checks
    return 1 if receipt.errors else 0

if __name__ == '__main__':
    stage_main('fetch-youtube', collect, ['python3','yt-dlp'])
