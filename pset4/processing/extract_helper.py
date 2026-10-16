"""Full article text, captions, podcast transcripts and immutable version assets."""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from lib.records import ROOT, StageFailure, emit, read_json, read_lines, stage_main
from transcripts import json_segments, timed_text, transcribe, retrieve_audio

class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ignored = 0
        self.selected = 0
        self.all_text = []
        self.article = []

    def handle_starttag(self,tag,attrs):
        if tag in ['script','style','nav','header','footer','aside']:
            self.ignored += 1
        if tag in ['article','main']:
            self.selected += 1
        if tag in ['p','div','br','li','h1','h2','h3']:
            self.handle_data('\n')

    def handle_endtag(self,tag):
        if tag in ['script','style','nav','header','footer','aside']:
            self.ignored = max(0,self.ignored-1)
        if tag in ['article','main']:
            self.selected = max(0,self.selected-1)
        if tag in ['p','div','li']:
            self.handle_data('\n')

    def handle_data(self,data):
        if not self.ignored:
            self.all_text.append(data)
            if self.selected:
                self.article.append(data)

def readable(content):
    parser = ReadableHTML()
    parser.feed(content)
    text = ''.join(parser.article or parser.all_text)
    lines = [re.sub(r'\s+',' ',line).strip() for line in text.splitlines()]
    return '\n'.join(line for line in lines if line)

def content_access(text):
    if 'this post is for paid subscribers' in text.lower():
        return 'paywall_preview'
    if 'bonus content for paid subscribers' in text.lower():
        return 'public_text_with_paid_bonus'
    return 'public_text'

def fetch(url):
    request = urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (Apprentice Mode)'})
    with urllib.request.urlopen(request,timeout=35) as response:
        return response.read().decode('utf-8',errors='replace')

def fingerprint(item, text_bytes, segment_bytes):
    payload = {key:item[key] for key in ['item_id','title','url','published_at','media_url']}
    payload['sha256_text_path'] = hashlib.sha256(text_bytes).hexdigest()
    payload['sha256_segments_path'] = hashlib.sha256(segment_bytes).hexdigest() if segment_bytes is not None else None
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',', ':'),ensure_ascii=False).encode()).hexdigest()

def save_new(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise OSError('immutable asset collision')
    else:
        with path.open('xb') as stream:
            stream.write(content)

def previous(item,version=None):
    args=['bash','data/store.sh','get',item['item_id']]
    if version:args.append(version)
    result = subprocess.run(args,capture_output=True,text=True)
    if result.returncode == 0:
        return json.loads(result.stdout)
    if result.returncode != 1:
        raise OSError('store lookup failed')
    return None

def extract(run_dir, receipt):
    rows = list(read_lines(sys.stdin))
    metadata=read_json(run_dir/'run.json')
    if metadata.get('operation')=='collection_replay':
        with (ROOT/metadata['source_run_dir']/'items.jsonl').open() as stream:
            originals={r['item_id']:r for r in read_lines(stream)}
        receipt.details.update(network_disabled=True,reused_count=0,method='offline_pinned_store_versions')
        for candidate in rows:
            receipt.input_count+=1
            original=originals.get(candidate['item_id'])
            if not original:raise StageFailure('Replay candidate has no saved extraction: '+candidate['item_id'])
            for key in ['source_id','publisher_id','kind','title','url','published_at','media_url']:
                if candidate.get(key)!=original.get(key):raise StageFailure('Replay candidate metadata differs from its saved extraction: '+candidate['item_id'])
            saved=previous(original,original['version_id'])
            if not saved:raise StageFailure('Replay source version is missing from the store: '+candidate['item_id'])
            for key in ['text_path','segments_path']:
                if saved[key] and not (ROOT/saved[key]).is_file():raise StageFailure('Replay retained asset is absent: '+saved[key])
            emit(dict(saved,retrieved_at=candidate['retrieved_at']))
            receipt.output_count+=1;receipt.details['reused_count']+=1
        return 0
    cap_minutes = float(os.environ.get('MAX_AUDIO_MINUTES','45'))
    if cap_minutes <= 0 or cap_minutes > 45:
        raise ValueError('MAX_AUDIO_MINUTES must be greater than zero and at most 45')
    cap = int(cap_minutes*60)
    receipt.details['max_audio_minutes'] = cap_minutes
    receipt.details['reused_count'] = 0
    run_id = read_json(run_dir/'run.json')['run_id']
    required = ['item_id','source_id','publisher_id','kind','title','url','published_at','retrieved_at','media_url']
    for row in rows:
        if any(key not in row for key in required) or row.get('kind') not in ['feed','youtube','podcast']:
            raise ValueError('malformed candidate')
    for candidate in rows:
        receipt.input_count += 1
        item = {key:candidate[key] for key in required}
        safe_id = re.sub(r'[^A-Za-z0-9_-]','_',item['item_id'])
        folder = ROOT/'data/media'/run_id/safe_id
        folder.mkdir(parents=True,exist_ok=True)
        try:
            saved = previous(item)
            metadata_same = saved and all(saved[key] == item[key] for key in ['item_id','title','url','published_at','media_url'])
            # Native recordings are stable; written pages must be re-fetched to
            # detect actual revisions. Changing the audio cap also re-extracts.
            if metadata_same and item['kind'] != 'feed' and (item['kind'] != 'podcast' or saved.get('max_audio_minutes') == cap_minutes and saved.get('raw_media_path') and (ROOT/saved['raw_media_path']).is_file()):
                if (ROOT/saved['text_path']).is_file() and (ROOT/saved['segments_path']).is_file():
                    emit(dict(saved,retrieved_at=item['retrieved_at']))
                    receipt.output_count += 1
                    receipt.details['reused_count'] += 1
                    continue
            transcript = None
            if item['kind'] == 'feed':
                try:
                    page = fetch(item['url'])
                    (folder/'article.html').write_text(page)
                    text = readable(page)
                    item['extraction_method'] = 'full_page'
                    if len(text.split()) < 40:
                        raise OSError('article too short')
                except Exception:
                    text = readable(candidate.get('feed_text',''))
                    item['extraction_method'] = 'feed_fallback'
                if len(text.split()) < 40:
                    raise OSError('No substantive article or feed text')
                item['content_access'] = content_access(text)
            elif item['kind'] == 'youtube':
                receipt.tools.append('yt-dlp')
                p = subprocess.run(['yt-dlp','--skip-download','--write-subs','--write-auto-subs','--sub-langs','en.*','--sub-format','vtt','--no-warnings','--retries','0','--socket-timeout','20','-o',str(folder/'captions.%(ext)s'),item['url']],capture_output=True,timeout=150)
                files = sorted(folder.glob('*.vtt'))
                if not files:
                    raise OSError('No reachable YouTube captions')
                transcript = timed_text(files[0].read_text())
                item['extraction_method'] = 'youtube_captions'
            else:
                item['max_audio_minutes'] = cap_minutes
                transcript = []
                for location in candidate.get('transcript_urls',[]):
                    try:
                        content = fetch(location['url'])
                        transcript = json_segments(content,cap) if 'json' in location.get('type','') else timed_text(content,cap)
                        if transcript:
                            item['extraction_method'] = 'published_transcript'
                            break
                    except Exception:
                        continue
                if not transcript:
                    transcript = timed_text(candidate.get('feed_text',''),cap)
                    item['extraction_method'] = 'published_feed_transcript'
                if not transcript:
                    try:
                        transcript = timed_text(fetch(item['url']),cap)
                        item['extraction_method'] = 'published_page_transcript'
                    except Exception:
                        pass
                if not transcript:
                    transcript = transcribe(item['media_url'],folder,cap,receipt)
                    item['extraction_method'] = 'audio_transcription'
                item['raw_media_path'] = str(retrieve_audio(item['media_url'],folder).relative_to(ROOT))
            if item['kind'] != 'feed':
                if not transcript:
                    raise OSError('Transcript has no usable timed segments')
                text = '\n'.join(segment['text'] for segment in transcript)
                item['transcript_end_seconds'] = transcript[-1]['end_seconds']
                item['audio_cap_applied'] = item['kind'] == 'podcast' and transcript[-1]['end_seconds'] >= cap
            text_bytes = (text.strip()+'\n').encode()
            segment_bytes = (json.dumps(transcript,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode() if transcript is not None else None
            item['version_id'] = fingerprint(item,text_bytes,segment_bytes)
            asset_dir = ROOT/'data/assets'/safe_id
            asset_dir.mkdir(parents=True,exist_ok=True)
            text_path = asset_dir/(item['version_id']+'.txt')
            save_new(text_path,text_bytes)
            item['text_path'] = str(text_path.relative_to(ROOT))
            item['segments_path'] = None
            if segment_bytes is not None:
                segment_path = asset_dir/(item['version_id']+'.segments.json')
                save_new(segment_path,segment_bytes)
                item['segments_path'] = str(segment_path.relative_to(ROOT))
            if metadata_same and saved['version_id'] == item['version_id']:
                receipt.details['reused_count'] += 1
            emit(item)
            receipt.output_count += 1
        except Exception as error:
            receipt.errors.append({'item_id':item['item_id'],'source_id':item['source_id'],
                                   'message':str(error) if isinstance(error,(OSError,StageFailure)) and not hasattr(error,'url') else type(error).__name__})
    receipt.tools = sorted(set(receipt.tools))
    return 1 if receipt.errors else 0

if __name__ == '__main__':
    stage_main('extract-content', extract, ['python3'])
