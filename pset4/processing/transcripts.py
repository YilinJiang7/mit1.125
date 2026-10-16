"""Parse timed transcript formats and transcribe capped podcast audio."""
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request
from lib.llm_client import LLMClient

def seconds(value):
    parts = value.replace(',', '.').split(':')
    return sum(float(part)*60**index for index,part in enumerate(reversed(parts)))

def segments(cues, cap=None):
    result = []
    for start,end,text in cues:
        text = html.unescape(re.sub('<[^>]+>', '', text)).strip()
        if not text or end <= start or cap is not None and start >= cap:
            continue
        if cap is not None:
            end = min(end, cap)
        # Merge contiguous short cues into about 30 seconds, suppress roll-up repeats.
        if result and start <= result[-1]['end_seconds']+2 and end-result[-1]['start_seconds'] <= 40:
            previous = result[-1]
            if text not in previous['text']:
                words = text.split()
                old = previous['text'].split()
                overlap = 0
                for size in range(1,min(len(old),len(words))+1):
                    if old[-size:] == words[:size]:
                        overlap = size
                previous['text'] += ' ' + ' '.join(words[overlap:])
            previous['end_seconds'] = max(previous['end_seconds'],end)
        else:
            result.append(dict(segment_id='seg-%04d' % (len(result)+1),start_seconds=float(start),end_seconds=float(end),text=text))
    return result

def timed_text(content, cap=None):
    cues = []
    pattern = r'(\d{1,2}:\d{2}(?::\d{2})?[.,]\d+)\s*-->\s*(\d{1,2}:\d{2}(?::\d{2})?[.,]\d+)[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
    for match in re.finditer(pattern,content,re.S):
        cues.append((seconds(match[1]),seconds(match[2]),match[3].replace('\n',' ')))
    if cues:
        return segments(cues,cap)
    # Published HTML transcripts have paragraph start times. The next paragraph
    # provides the end; omit the final paragraph when no end is supplied.
    paragraphs = re.findall(r'<p\b[^>]*>(.*?)</p>',content,re.S|re.I)
    timed = []
    for paragraph in paragraphs:
        text = html.unescape(re.sub('<[^>]+>','',paragraph))
        match = re.search(r'\[(\d{1,2}:\d{2}(?::\d{2})?)\]',text)
        if match:
            timed.append((seconds(match[1]), re.sub(r'\[\d{1,2}:\d{2}(?::\d{2})?\]','',text).strip()))
    return segments([(start,timed[index+1][0],text) for index,(start,text) in enumerate(timed[:-1])],cap)

def json_segments(content, cap):
    data = json.loads(content)
    values = data.get('segments', []) if isinstance(data,dict) else data
    return segments([(float(s.get('start_seconds',s.get('start',0))),float(s.get('end_seconds',s.get('end',0))),s['text']) for s in values],cap)

def retrieve_audio(audio_url, folder):
    if not audio_url:
        raise OSError('Podcast has no audio enclosure')
    raw = folder/'audio.original'
    if not raw.exists():
        request = urllib.request.Request(audio_url,headers={'User-Agent':'Mozilla/5.0'})
        temporary = folder/'audio.part'
        with urllib.request.urlopen(request,timeout=60) as response,temporary.open('wb') as output:
            while True:
                chunk = response.read(1024*1024)
                if not chunk:break
                output.write(chunk)
        temporary.rename(raw)
    return raw

def transcribe(audio_url, folder, cap, receipt):
    engine = next((name for name in ['mlx_whisper','faster_whisper'] if importlib.util.find_spec(name)),None)
    key = os.environ.get('OPENAI_API_KEY')
    if not engine and not key:
        raise OSError('No published timed transcript, local Whisper engine, or OPENAI_API_KEY')
    receipt.tools.extend(['ffmpeg','ffprobe'])
    raw = retrieve_audio(audio_url, folder)
    audio = folder/'capped.mp3'
    p = subprocess.run(['ffmpeg','-y','-i',str(raw),'-t',str(cap),'-vn','-ac','1','-ar','16000','-b:a','32k',str(audio)],capture_output=True,timeout=180)
    if p.returncode:
        raise OSError('ffmpeg compression failed')
    client = LLMClient(receipt.run_dir,receipt)
    if engine:
        return json_segments(json.dumps(client.local_transcribe(engine,audio)),cap)
    cues = []
    # Ten-minute mono MP3 chunks are well below the provider upload limit.
    for offset in range(0,cap,600):
        chunk_path = folder/('chunk-%04d.mp3' % offset)
        p = subprocess.run(['ffmpeg','-y','-ss',str(offset),'-i',str(audio),'-t','600','-c','copy',str(chunk_path)],capture_output=True,timeout=60)
        if p.returncode:
            raise OSError('ffmpeg chunking failed')
        probe = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(chunk_path)],capture_output=True,text=True)
        if probe.returncode:break
        duration = float(probe.stdout.strip())
        if duration <= 0:break
        data = client.transcribe(chunk_path,duration,offset)
        (folder/('transcription-%04d.json' % offset)).write_text(json.dumps(data))
        cues.extend((s['start']+offset,s['end']+offset,s['text']) for s in data['segments'])
        if duration < 599:break
    return segments(cues,cap)
