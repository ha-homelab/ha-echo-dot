#!/usr/bin/env python3
"""Loopback-only, deliberate browser microphone collection. No HA access."""
from __future__ import annotations
import argparse, base64, hashlib, io, json, math, os, re, secrets, shutil, subprocess, sys, threading, uuid, wave
from array import array
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).with_name('web')
LIMIT = 12
SPLITS = ('train', 'val', 'test')

# Exact legacy presentation strings only. Existing campaign provenance stays intact;
# translated hints must not permit a change to phrases, labels, order, or splits.
LEGACY_HINTS = {
    'Обычным голосом. Не повышайте тон специально.': 'Use your normal voice. Do not deliberately raise your pitch.',
    'Чуть тише, но отчётливо; без шёпота.': 'Speak a little more softly, but clearly. Do not whisper.',
    'Спокойно, в удобном низком регистре. Не изображайте чужой голос.': 'Speak calmly in a comfortable lower register. Do not imitate another voice.',
    'Естественная вопросительная интонация.': 'Use a natural questioning intonation.',
    'Отодвиньтесь от Mac примерно на метр, говорите как обычно.': 'Move about one metre away from your Mac and speak normally.',
    'Похожее слово или обычная команда. Говорите естественно.': 'Say this similar word or everyday command naturally.',
}

def english_plan(plan):
    """Normalize known legacy hints for comparison without rewriting saved data."""
    if not isinstance(plan, list): return plan
    return [{**task, 'hint': LEGACY_HINTS.get(task.get('hint'), task.get('hint'))}
            if isinstance(task, dict) and isinstance(task.get('hint'), str) else task for task in plan]

def now(): return datetime.now(timezone.utc).isoformat()
def digest(data): return hashlib.sha256(data).hexdigest()
def atomic(path, data):
    tmp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    with tmp.open('x', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def make_plan():
    result = []
    normal = 'Use your normal voice. Do not deliberately raise your pitch.'
    soft = 'Speak a little more softly, but clearly. Do not whisper.'
    low = 'Speak calmly in a comfortable lower register. Do not imitate another voice.'
    question = 'Use a natural questioning intonation.'
    far = 'Move about one metre away from your Mac and speak normally.'
    styles = {'train': [normal]*10 + [soft]*4 + [low]*4 + [question]*2 + [far]*4,
              'val': [normal]*4 + [soft, low, question, far],
              'test': [normal]*4 + [low, soft, far, question]}
    negatives = {
      'train': ['Мишка', 'Миша', 'Мышь', 'Книжка', 'Привет, Мишка', 'Привет, Миша', 'Привет', 'Пышка', 'Включи свет', 'Сделай потише', 'Какая завтра погода', 'Останови музыку'],
      'val': ['Мишка спит', 'Миша, иди сюда', 'Привет, Маша', 'Где лежат ключи', 'Расскажи стишок', 'Поставь таймер', 'Открой дверь', 'Доброе утро'],
      'test': ['Привет, Мишенька', 'Маша, подойди', 'Большая книжка', 'Сколько сейчас времени', 'Закрой шторы', 'Спасибо, всё готово', 'Мы сегодня смотрим кино', 'До свидания']}
    for split in SPLITS:
        items = []
        for target, phrase in [('myshka', 'Мышка'), ('privet_myshka', 'Привет, Мышка')]:
            for i, style in enumerate(styles[split]):
                items.append({'id': f'{split}-{target}-{i+1:02}', 'split': split, 'target': target, 'text': phrase, 'hint': style,
                              'labels': {'myshka': 1, 'privet_myshka': int(target == 'privet_myshka')}})
        for i, phrase in enumerate(negatives[split]):
            items.append({'id': f'{split}-negative-{i+1:02}', 'split': split, 'target': 'negative', 'text': phrase,
                          'hint': 'Say this similar word or everyday command naturally.', 'labels': {'myshka': 0, 'privet_myshka': 0}})
        result.extend(items)
    return result
PLAN = make_plan()
TASKS = {t['id']: t for t in PLAN}

def inspect_wav(data, max_seconds=LIMIT):
    try:
        with wave.open(io.BytesIO(data), 'rb') as w:
            rate, frames = w.getframerate(), w.getnframes()
            if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getcomptype()!='NONE' or not 8000 <= rate <= 192000:
                raise ValueError('Expected mono PCM16 WAV at 8–192 kHz.')
            if not 0.20 <= frames/rate <= max_seconds + 0.1: raise ValueError('Record between 0.2 and 12 seconds.')
            pcm = w.readframes(frames+1)
            if len(pcm)!=frames*2: raise ValueError('Truncated audio payload.')
    except (wave.Error, EOFError) as e: raise ValueError('Invalid WAV.') from e
    samples = array('h', pcm)
    if sys.byteorder != 'little': samples.byteswap()
    peak = max(abs(x) for x in samples)/32768
    rms = math.sqrt(sum(x*x for x in samples)/len(samples))/32768
    clipping = sum(abs(x)>=32700 for x in samples)/len(samples)
    flags=[]
    if peak<0.008: flags.append('Almost silent: check the selected microphone and record again.')
    elif rms<0.002: flags.append('Very quiet recording: listen to it before continuing.')
    if clipping>0.002: flags.append('Audio is clipping: move farther from the microphone and record again.')
    if frames/rate<0.65: flags.append('Very short recording: the beginning or end of the phrase may be cut off.')
    return {'sample_rate': rate, 'samples': frames, 'duration': round(frames/rate,4), 'peak': round(peak,5),
            'rms_dbfs': round(20*math.log10(max(rms,1e-9)),1), 'clipped_fraction': round(clipping,6), 'flags': flags}

class Store:
    def __init__(self, root, ffmpeg):
        self.root=root.resolve(); self.ffmpeg=ffmpeg; self.lock=threading.RLock()
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        (self.root/'takes').mkdir(exist_ok=True,mode=0o700)
        self.path=self.root/'campaign.json'
        if self.path.exists():
            self.state=json.loads(self.path.read_text())
            if self.state.get('schema')!=1 or english_plan(self.state.get('plan'))!=PLAN: raise ValueError('Collection plan changed; use a new data directory.')
        else:
            self.state={'schema':1,'created_at':now(),'plan':PLAN,'sessions':{},'takes':[], 'analysis_requests':[]}
            self.save()
    def save(self): atomic(self.path,self.state)
    def public(self):
        with self.lock:
            return {'plan': PLAN, 'sessions': self.state['sessions'], 'takes': self.state['takes'], 'max_seconds': LIMIT,
                    'storage': str(self.root), 'analysis_requests': self.state['analysis_requests']}
    def session(self, split):
        with self.lock:
            if split not in SPLITS: raise ValueError('Unknown session.')
            if split not in self.state['sessions']:
                self.state['sessions'][split]={'id':split+'-'+uuid.uuid4().hex[:12], 'started_at':now(), 'split':split}
                self.save()
            return self.state['sessions'][split]
    def capture(self, body):
        with self.lock:
            task=TASKS.get(body.get('task_id'))
            if not task: raise ValueError('Unknown prompt.')
            session=self.state['sessions'].get(task['split'])
            if not session or session['id']!=body.get('session_id'): raise ValueError('Start the matching session first.')
            take_id=body.get('take_id','')
            if not re.fullmatch(r'[0-9a-f]{32}',take_id): raise ValueError('Invalid take ID.')
            data=base64.b64decode(body.get('wav',''),validate=True)
            if len(data)>5_000_000: raise ValueError('Audio too large.')
            rawstats=inspect_wav(data)
            existing=next((t for t in self.state['takes'] if t['id']==take_id),None)
            if existing:
                if existing['source_sha256']!=digest(data) or existing['task_id']!=task['id']: raise ValueError('Take ID already has different audio.')
                return existing
            if any(t['source_sha256']==digest(data) for t in self.state['takes']): raise ValueError('Duplicate audio: record a fresh attempt.')
            converted=subprocess.run([self.ffmpeg,'-hide_banner','-loglevel','error','-f','wav','-i','pipe:0','-ac','1','-ar','16000','-c:a','pcm_s16le','-f','wav','pipe:1'],input=data,capture_output=True,timeout=15,check=True).stdout
            # ffmpeg's pipe header has an unknown length. Repack to a finite canonical WAV.
            with wave.open(io.BytesIO(converted),'rb') as w: pcm=w.readframes(LIMIT*16000+1600)
            b=io.BytesIO()
            with wave.open(b,'wb') as w: w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
            canonical=b.getvalue(); stats=inspect_wav(canonical)
            if any(t.get('pcm_sha256')==digest(pcm) for t in self.state['takes']): raise ValueError('Duplicate PCM audio.')
            meta=body.get('microphone',{})
            if not isinstance(meta,dict) or len(json.dumps(meta))>4000: raise ValueError('Invalid microphone metadata.')
            folder=self.root/'takes'/take_id
            if folder.exists():
                previous=json.loads((folder/'metadata.json').read_text())
                if previous['source_sha256']!=digest(data) or previous['task_id']!=task['id']: raise ValueError('Orphaned take needs inspection.')
            else:
                temporary=self.root/'takes'/('.'+take_id+'-'+uuid.uuid4().hex)
                temporary.mkdir(mode=0o700)
                (temporary/'source.wav').write_bytes(data); (temporary/'audio.wav').write_bytes(canonical)
            record={'id':take_id,'task_id':task['id'],'session_id':session['id'],'split':task['split'],'intended_text':task['text'],
                    'intended_labels':task['labels'],'content_review':'pending','selected':True,'recorded_at':now(),
                    'source_sha256':digest(data),'sha256':digest(canonical),'pcm_sha256':digest(pcm),'source_stats':rawstats,'stats':stats,
                    'microphone':meta,'device_domain':'mac_browser','path':f'takes/{take_id}/audio.wav'}
            if not folder.exists():
                atomic(temporary/'metadata.json',record)
                os.replace(temporary,folder)
            for old in self.state['takes']:
                if old['task_id']==task['id']: old['selected']=False
            self.state['takes'].append(record); self.save()
            return record
    def finish(self, split):
        with self.lock:
            if split not in self.state['sessions']: raise ValueError('No session has started.')
            selected={t['task_id'] for t in self.state['takes'] if t['selected'] and t['split']==split}
            expected={t['id'] for t in PLAN if t['split']==split}
            if selected!=expected: raise ValueError('Complete every prompt in this session first.')
            selected_ids=[t['id'] for t in self.state['takes'] if t['selected'] and t['split']==split]
            previous=next((r for r in self.state['analysis_requests'] if r['split']==split and r['selected_ids']==selected_ids),None)
            if previous:return previous
            request={'split':split,'requested_at':now(),'selected_ids':selected_ids}
            self.state['analysis_requests'].append(request);self.save();return request

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def reply(self,status,body,kind='application/json'):
        if isinstance(body,(dict,list)): body=json.dumps(body,ensure_ascii=False).encode()
        if isinstance(body,str): body=body.encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def allowed(self, api=False):
        if self.headers.get('Host')!=self.server.host: return False
        if self.headers.get('Sec-Fetch-Site') not in (None,'same-origin','none'): return False
        if self.headers.get('Origin') not in (None,self.server.origin): return False
        if api and self.headers.get('X-Recorder-Token')!=self.server.token: return False
        return True
    def do_GET(self):
        path=self.path.split('?',1)[0]
        if not self.allowed(path.startswith('/api/')): return self.reply(403,{'error':'Local same-origin access required.'})
        if path=='/api/status': return self.reply(200,self.server.store.public())
        if path.startswith('/api/audio/'):
            take=next((t for t in self.server.store.public()['takes'] if t['id']==path.rsplit('/',1)[-1]),None)
            if not take:return self.reply(404,{'error':'Unknown take.'})
            return self.reply(200,(self.server.store.root/take['path']).read_bytes(),'audio/wav')
        files={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css'),'/capture.js':('capture.js','text/javascript')}
        if path not in files:return self.reply(404,{'error':'Not found.'})
        name,kind=files[path];data=(WEB/name).read_bytes()
        if path=='/':data=data.replace(b'__TOKEN__',self.server.token.encode())
        return self.reply(200,data,kind)
    def do_POST(self):
        if not self.allowed(True):return self.reply(403,{'error':'Local same-origin access required.'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<7_000_000:raise ValueError('Invalid request length.')
            self.connection.settimeout(20)
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('Expected an object.')
            if self.path=='/api/session':result=self.server.store.session(body.get('split'))
            elif self.path=='/api/take':result=self.server.store.capture(body)
            elif self.path=='/api/finish':result=self.server.store.finish(body.get('split'))
            else:return self.reply(404,{'error':'Not found.'})
            self.reply(200,result)
        except (ValueError,KeyError,TypeError) as e:self.reply(400,{'error':str(e)})
        except (OSError,subprocess.SubprocessError):self.reply(500,{'error':'Local save failed. Keep this page open and retry saving.'})

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[2]/'private/mac-wakeword-recordings');p.add_argument('--port',type=int,default=8766)
    a=p.parse_args();os.umask(0o077)
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:p.error('ffmpeg is required for anti-aliased 16 kHz conversion.')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.daemon_threads=True
    server.host=f'127.0.0.1:{server.server_port}';server.origin='http://'+server.host;server.token=secrets.token_urlsafe(32);server.store=Store(a.data_dir,ffmpeg)
    print(server.origin,flush=True);print('Private recordings: '+str(server.store.root),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
