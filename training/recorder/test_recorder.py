import base64, io, json, math, os, shutil, tempfile, threading, unittest, urllib.request, urllib.error, uuid, wave
from array import array
from pathlib import Path
from server import Store, Handler, ThreadingHTTPServer, PLAN, LEGACY_HINTS, inspect_wav
from review import labels, export, review

def wav(rate=48000,seconds=1.2,freq=370,amplitude=6000):
    out=io.BytesIO();samples=array('h',(int(amplitude*math.sin(i*2*math.pi*freq/rate)) for i in range(int(seconds*rate))))
    with wave.open(out,'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())
    return out.getvalue()

class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.store=Store(self.root/'capture',shutil.which('ffmpeg'))
    def body(self,split='train',freq=370):
        session=self.store.session(split);task=next(t for t in PLAN if t['split']==split)
        return {'task_id':task['id'],'session_id':session['id'],'take_id':uuid.uuid4().hex,'wav':base64.b64encode(wav(freq=freq)).decode(),'microphone':{'label':'SYNTHETIC TEST'}}
    def test_conversion_retry_retake_resume(self):
        body=self.body();take=self.store.capture(body)
        self.assertEqual(take['stats']['sample_rate'],16000);self.assertEqual(take['source_stats']['sample_rate'],48000)
        self.assertAlmostEqual(take['stats']['duration'],1.2,places=3);self.assertEqual(self.store.capture(body),take)
        self.assertEqual(len(self.store.state['takes']),1)
        second=self.store.capture(self.body(freq=530));self.assertFalse(take['selected']);self.assertTrue(second['selected'])
        reopened=Store(self.root/'capture',shutil.which('ffmpeg'));self.assertEqual(reopened.state,self.store.state)
    def test_split_duplicate_and_invalid_format(self):
        self.store.capture(self.body())
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.store.capture(self.body('val'))
        wrong=self.body(freq=380);wrong['session_id']='wrong'
        with self.assertRaisesRegex(ValueError,'matching session'):self.store.capture(wrong)
        with self.assertRaises(ValueError):inspect_wav(b'bad')
        with self.assertRaises(ValueError):inspect_wav(wav(seconds=13))
        self.assertTrue(inspect_wav(wav(amplitude=0))['flags'])
    def test_legacy_campaign_resumes_without_rewriting_recordings(self):
        take=self.store.capture(self.body())
        reverse={english:russian for russian,english in LEGACY_HINTS.items()}
        self.store.state['plan']=[{**task,'hint':reverse[task['hint']]} for task in PLAN]
        self.store.save()
        before={p.relative_to(self.store.root):p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()}
        resumed=Store(self.store.root,shutil.which('ffmpeg'))
        self.assertEqual(resumed.public()['plan'],PLAN)
        self.assertEqual(resumed.public()['takes'],[take])
        self.assertEqual(resumed.public()['sessions'],self.store.state['sessions'])
        after={p.relative_to(self.store.root):p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_hint_compatibility_still_rejects_protocol_changes(self):
        original=json.loads(self.store.path.read_text())
        mutations=[('text','different phrase'),('split','test'),('labels',{'myshka':0,'privet_myshka':0}),('hint','unknown instruction'),('id','different-id')]
        for key,value in mutations:
            with self.subTest(key=key):
                changed=json.loads(json.dumps(original));changed['plan'][0][key]=value
                self.store.path.write_text(json.dumps(changed))
                with self.assertRaisesRegex(ValueError,'plan changed'):Store(self.store.root,shutil.which('ffmpeg'))
        changed=json.loads(json.dumps(original));changed['plan'].reverse()
        self.store.path.write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'plan changed'):Store(self.store.root,shutil.which('ffmpeg'))
    def test_review_gate_labels_and_frozen_test(self):
        take=self.store.capture(self.body());test=self.store.capture(self.body('test',freq=390));dest=self.root/'export'
        with self.assertRaisesRegex(ValueError,'transcript'):export(self.store.root,dest)
        review(self.store.root,take['id'],'Привет, Мышка!');counts=export(self.store.root,dest)
        self.assertEqual(counts['myshka']['train']['positive'],1);self.assertEqual(counts['privet_myshka']['train']['positive'],1)
        self.assertEqual(counts['myshka']['test']['positive'],0)
        with self.assertRaisesRegex(ValueError,'transcript'):export(self.store.root,dest,True)
        self.assertEqual(labels('Мышка'),{'myshka':1,'privet_myshka':0})
        self.assertEqual(labels('Привет, Мишка'),{'myshka':0,'privet_myshka':0})
    def test_plan_has_no_conflicting_negatives(self):
        self.assertEqual([sum(t['split']==s for t in PLAN) for s in ['train','val','test']],[60,24,24])
        for task in PLAN:self.assertEqual(labels(task['text']),task['labels'])
        for split,n in [('train',24),('val',8),('test',8)]:
            targets=[t['target'] for t in PLAN if t['split']==split]
            self.assertEqual(targets[:n],['myshka']*n)
            self.assertEqual(targets[n:2*n],['privet_myshka']*n)
            self.assertTrue(all(t=='negative' for t in targets[2*n:]))
    def test_loopback_origin_and_path_protection(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.store=self.store;server.token='test-token';server.host=f'127.0.0.1:{server.server_port}';server.origin='http://'+server.host
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def get(path,headers={}):return urllib.request.urlopen(urllib.request.Request(server.origin+path,headers=headers))
        self.assertEqual(get('/').status,200)
        for path,headers in [('/api/status',{}),('/api/status',{'X-Recorder-Token':'test-token','Origin':'https://evil.example'}),('/',{'Host':'evil.example'}),('/../campaign.json',{})]:
            with self.assertRaises(urllib.error.HTTPError):get(path,headers)
        self.assertEqual(get('/api/status',{'X-Recorder-Token':'test-token'}).status,200)

if __name__=='__main__':unittest.main()
