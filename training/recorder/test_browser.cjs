// Run with Playwright available via NODE_PATH. Uses only a synthetic microphone.
const {chromium}=require('playwright');
const {spawn,execFileSync}=require('node:child_process');const fs=require('node:fs');const path=require('node:path');const os=require('node:os');const assert=require('node:assert/strict');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'wake-recorder-qa-'));const fake=path.join(dir,'synthetic.wav');
 execFileSync('ffmpeg',['-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=523:duration=20','-ar','48000','-ac','1',fake]);
 const server=spawn('python3',[path.join(__dirname,'server.py'),'--port','0','--data-dir',path.join(dir,'data')]);
 let browser;
 try{
 const url=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(new Error('Server timeout')),10000);server.stdout.on('data',chunk=>{output+=chunk;const match=output.match(/http:\/\/127\.0\.0\.1:\d+/);if(match){clearTimeout(timer);resolve(match[0]);}});server.on('error',reject);server.on('exit',code=>reject(new Error('Server exit '+code)));});
 browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--use-file-for-fake-audio-capture='+fake]});
 const page=await browser.newPage({viewport:{width:1180,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.qaTracks=[];const original=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);navigator.mediaDevices.getUserMedia=async c=>{const s=await original(c);window.qaTracks.push(...s.getTracks());return s;};});
 await page.goto(url);await page.getByText('First record 24 takes',{exact:false}).waitFor();
 assert.equal(await page.locator('.controls button').count(),1);assert.equal(await page.locator('#next, #retake, #stop, #session-start, #finish').count(),0);
 assert.equal(await page.evaluate(()=>window.qaTracks.length),0,'no microphone on page load');
 await page.getByRole('button',{name:'Record',exact:true}).click();await page.getByText('SPEAK — recording',{exact:true}).waitFor();await page.waitForTimeout(1100);await page.getByRole('button',{name:'Stop',exact:true}).click();await page.getByText('Saved. Click Record for the next take.',{exact:true}).waitFor();
 assert.equal(await page.evaluate(()=>window.qaTracks.every(t=>t.readyState==='ended')),true,'stop releases every mic track');
 let campaign=JSON.parse(fs.readFileSync(path.join(dir,'data/campaign.json')));assert.equal(campaign.takes.length,1);assert.equal(campaign.takes[0].stats.sample_rate,16000);assert.equal(campaign.takes[0].content_review,'pending');assert.equal(await page.locator('#phrase').textContent(),'Мышка');assert.match(await page.locator('#batch').textContent(),/2 \/ 24$/);
 await page.reload();await page.getByText('Saved 1 of 60',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Record',exact:true}).click();await page.getByText('SPEAK — recording',{exact:true}).waitFor();await page.waitForTimeout(1400);
 await page.route('**/api/take',route=>route.abort());await page.getByRole('button',{name:'Stop',exact:true}).click();await page.getByRole('button',{name:'Retry save',exact:true}).waitFor();assert.equal(await page.evaluate(()=>window.qaTracks.every(t=>t.readyState==='ended')),true,'save failure leaves mic off');
 await page.unroute('**/api/take');await page.getByRole('button',{name:'Retry save',exact:true}).click();await page.getByText('Saved. Click Record for the next take.',{exact:true}).waitFor();
 campaign=JSON.parse(fs.readFileSync(path.join(dir,'data/campaign.json')));assert.equal(campaign.takes.length,2);
await page.getByRole('button',{name:'Record',exact:true}).click();await page.getByText('SPEAK — recording',{exact:true}).waitFor();
 await page.getByText('Saved. Click Record for the next take.',{exact:true}).waitFor({timeout:18000});
 campaign=JSON.parse(fs.readFileSync(path.join(dir,'data/campaign.json')));assert.equal(campaign.takes.length,3);assert.equal(campaign.takes[2].stats.duration,12,'worklet hard cap');assert.equal(await page.evaluate(()=>window.qaTracks.every(t=>t.readyState==='ended')),true);


 const token=await page.locator('meta[name="recorder-token"]').getAttribute('content');
 const session=campaign.sessions.train.id;
 const tone=n=>{const rate=16000,frames=12000,b=Buffer.alloc(44+2*frames);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(rate,24);b.writeUInt32LE(rate*2,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(frames*2,40);for(let i=0;i<frames;i++)b.writeInt16LE(Math.round(4000*Math.sin(i*2*Math.PI*(800+n*13)/rate)),44+i*2);return b.toString('base64');};
 const seed=async(n,task)=>{const r=await page.request.post(url+'/api/take',{headers:{'X-Recorder-Token':token},data:{take_id:require('node:crypto').randomUUID().replaceAll('-',''),task_id:task.id,session_id:session,wav:tone(n),microphone:{label:'SYNTHETIC BOUNDARY TEST'}}});assert.equal(r.status(),200,await r.text());};
 const train=campaign.plan.filter(t=>t.split==='train');
 for(let i=3;i<23;i++)await seed(i,train[i]);
 await page.reload();await page.getByText('Saved 23 of 60',{exact:true}).waitFor();assert.equal(await page.locator('#phrase').textContent(),'Мышка');assert.match(await page.locator('#batch').textContent(),/24 \/ 24$/);
 await page.getByRole('button',{name:'Record',exact:true}).click();await page.getByText('SPEAK — recording',{exact:true}).waitFor();await page.waitForTimeout(1650);await page.getByRole('button',{name:'Stop',exact:true}).click();await page.getByText('Saved 24 of 60',{exact:true}).waitFor();
 assert.equal(await page.locator('#phrase').textContent(),'Привет, Мышка');assert.match(await page.locator('#batch').textContent(),/1 \/ 24$/);
 if(process.env.QA_SCREENSHOT)await page.screenshot({path:process.env.QA_SCREENSHOT,fullPage:true});
 for(let i=24;i<60;i++)await seed(i,train[i]);
 await page.reload();await page.getByText('Ready for analysis. Tell the assistant which session you completed.',{exact:true}).waitFor();
 campaign=JSON.parse(fs.readFileSync(path.join(dir,'data/campaign.json')));assert.equal(campaign.analysis_requests.length,1);assert.equal(campaign.analysis_requests[0].selected_ids.length,60);
 await page.reload();await page.getByText('Ready for analysis. Tell the assistant which session you completed.',{exact:true}).waitFor();
 campaign=JSON.parse(fs.readFileSync(path.join(dir,'data/campaign.json')));assert.equal(campaign.analysis_requests.length,1,'completion marker is idempotent');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:true,checks:['no capture on load','single-button start/stop','automatic advance','whole Myshka batch before Privet','automatic idempotent completion','16 kHz saved WAV','tracks stopped','reload resume','failed save recovery','12-second hard cap','no JS errors'],syntheticOnly:true}));
 }finally{if(browser)await browser.close();server.kill('SIGTERM');fs.rmSync(dir,{recursive:true,force:true});}
})().catch(e=>{console.error(e);process.exitCode=1;});
