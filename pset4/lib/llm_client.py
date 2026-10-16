"""One API client: secret-free requests/responses, usage receipts and cost estimates."""
import hashlib
import json
import os
import ssl
from pathlib import Path
import urllib.error
import urllib.request
import uuid
from lib.records import ROOT, StageFailure, now, read_json

class InvalidModelOutput(StageFailure):
    pass

class TransportFailure(StageFailure):
    pass

class LLMClient:
    def __init__(self, run_dir, receipt):
        self.run_dir = Path(run_dir).resolve()
        self.receipt = receipt
        self.model = os.environ.get('OPENAI_MODEL','gpt-4.1-mini')
        self.key = os.environ.get('OPENAI_API_KEY')
        self.prices = read_json(ROOT/'lib/prices.json')

    def save(self, path, body):
        # Authorization headers are never saved. Protect against accidental echo.
        if self.key:
            body = body.replace(self.key.encode(),b'[REDACTED]')
        path.write_bytes(body)

    def check_budget(self, estimate):
        spent = self.receipt.cost
        for path in (self.run_dir/'logs').glob('*.json'):
            spent += read_json(path).get('cost_usd') or 0
        if spent + estimate > 1.50:
            raise StageFailure('Estimated run budget would exceed $1.50; no request sent')

    def request(self, stage, endpoint, payload, body, content_type, call):
        # One retry for observed network/TLS failures; HTTP/account errors stop.
        for attempt in range(2):
            try:
                return self.request_once(stage,endpoint,payload,body,content_type,dict(call,attempt=attempt+1))
            except TransportFailure:
                if attempt==1:raise

    def request_once(self, stage, endpoint, payload, body, content_type, call):
        if not self.key:
            raise StageFailure('OPENAI_API_KEY is not loaded; export it or run through run.sh')
        folder = self.run_dir/'llm'/stage
        folder.mkdir(parents=True,exist_ok=True)
        stem = now().replace(':','').replace('.','')+'-'+uuid.uuid4().hex[:8]
        request_path = folder/(stem+'.request.json')
        response_path = folder/(stem+'.response.json')
        self.save(request_path,(json.dumps(payload,ensure_ascii=False,indent=2)+'\n').encode())
        request = urllib.request.Request('https://api.openai.com/v1/'+endpoint,data=body,
                                         headers={'Authorization':'Bearer '+self.key,'Content-Type':content_type})
        try:
            with urllib.request.urlopen(request,timeout=180) as response:
                raw = response.read()
            self.save(response_path,raw)
            data = json.loads(raw)
        except Exception as error:
            status = error.code if isinstance(error,urllib.error.HTTPError) else None
            self.save(response_path,json.dumps({'request_failed':True,'http_status':status,'error_type':type(error).__name__}).encode())
            call.update(status='failed',cost_usd=None,request_path=str(request_path.relative_to(ROOT)),response_path=str(response_path.relative_to(ROOT)))
            self.receipt.models.append(call)
            self.receipt.details['unknown_api_costs'] = self.receipt.details.get('unknown_api_costs',0)+1
            failure=TransportFailure if isinstance(error,(ssl.SSLError,TimeoutError)) or isinstance(error,urllib.error.URLError) and not isinstance(error,urllib.error.HTTPError) else StageFailure
            raise failure('OpenAI request failed (%s%s); see secret-free response record' % (type(error).__name__,': HTTP '+str(status) if status else '')) from None
        call.update(status='completed',request_path=str(request_path.relative_to(ROOT)),response_path=str(response_path.relative_to(ROOT)))
        self.receipt.models.append(call)
        return data,call

    def chat(self, stage, messages, json_mode=False, max_tokens=3000, schema=None):
        payload = dict(model=self.model,messages=messages,temperature=0.2,max_tokens=max_tokens)
        if json_mode:
            payload['response_format'] = {'type':'json_object'}
        if schema is not None:
            payload['response_format'] = {'type':'json_schema','json_schema':{'name':stage.replace('-','_'),'strict':True,'schema':schema}}
        price = self.prices.get(self.model) or (self.prices['gpt-4.1-mini'] if self.model.startswith('gpt-4.1-mini-') else None)
        if price:
            # Conservative preflight, distinct from provider-reported token usage.
            estimate = (len(json.dumps(messages))*price['input_usd_per_million']+max_tokens*price['output_usd_per_million'])/1_000_000
            self.check_budget(estimate)
        call = dict(model=self.model,input_tokens=None,output_tokens=None,cost_usd=None,cost_is_estimate=True)
        data,call = self.request(stage,'chat/completions',payload,json.dumps(payload).encode(),'application/json',call)
        usage = data.get('usage',{})
        incoming,outgoing = usage.get('prompt_tokens'),usage.get('completion_tokens')
        cached = usage.get('prompt_tokens_details',{}).get('cached_tokens',0)
        call.update(input_tokens=incoming,output_tokens=outgoing,cached_input_tokens=cached)
        if price and incoming is not None and outgoing is not None:
            cost = ((incoming-cached)*price['input_usd_per_million']+cached*price['cached_input_usd_per_million']+outgoing*price['output_usd_per_million'])/1_000_000
            call['cost_usd'] = cost
            self.receipt.cost += cost
        else:
            self.receipt.details['unknown_api_costs'] = self.receipt.details.get('unknown_api_costs',0)+1
        choice = data.get('choices',[{}])[0]
        if choice.get('finish_reason') != 'stop' or not choice.get('message',{}).get('content'):
            raise InvalidModelOutput('Model response incomplete or refused; see saved raw response')
        return choice['message']['content']

    def transcribe(self, audio, duration_seconds, offset_seconds=0):
        audio = Path(audio)
        cost = duration_seconds/60*self.prices['whisper-1']['usd_per_minute']
        self.check_budget(cost)
        fields = {'model':'whisper-1','response_format':'verbose_json','timestamp_granularities[]':'segment'}
        payload = dict(fields,file_path=str(audio.relative_to(ROOT)),file_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),duration_seconds=duration_seconds,offset_seconds=offset_seconds)
        boundary = 'apprentice-'+uuid.uuid4().hex
        body = bytearray()
        for name,value in fields.items():
            body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode())
        body.extend(('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="audio.mp3"\r\nContent-Type: audio/mpeg\r\n\r\n').encode())
        body.extend(audio.read_bytes())
        body.extend(('\r\n--'+boundary+'--\r\n').encode())
        call = dict(model='whisper-1',input_tokens=None,output_tokens=None,audio_minutes=duration_seconds/60,cost_usd=cost,cost_is_estimate=True)
        data,call = self.request('extract-content','audio/transcriptions',payload,bytes(body),'multipart/form-data; boundary='+boundary,call)
        self.receipt.cost += cost
        return data

    def local_transcribe(self, engine, audio):
        audio=Path(audio)
        folder=self.run_dir/'llm/extract-content'
        folder.mkdir(parents=True,exist_ok=True)
        stem=now().replace(':','').replace('.','')+'-'+uuid.uuid4().hex[:8]
        request_path=folder/(stem+'.request.json')
        response_path=folder/(stem+'.response.json')
        self.save(request_path,json.dumps({'model':'local-'+engine,'file_path':str(audio.relative_to(ROOT)),
                                          'file_sha256':hashlib.sha256(audio.read_bytes()).hexdigest()}).encode())
        if engine=='mlx_whisper':
            import mlx_whisper
            data=mlx_whisper.transcribe(str(audio))
        else:
            from faster_whisper import WhisperModel
            chunks,_=WhisperModel('base',device='cpu',compute_type='int8').transcribe(str(audio))
            data={'segments':[{'start':chunk.start,'end':chunk.end,'text':chunk.text} for chunk in chunks]}
        self.save(response_path,json.dumps(data).encode())
        self.receipt.models.append({'model':'local-'+engine,'input_tokens':None,'output_tokens':None,'cost_usd':0.0,
                                    'cost_is_estimate':False,'status':'completed','request_path':str(request_path.relative_to(ROOT)),
                                    'response_path':str(response_path.relative_to(ROOT))})
        return data
