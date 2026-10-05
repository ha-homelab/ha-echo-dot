'use strict';
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name="recorder-token"]').content;
let state,split='train',taskId=null,busy=false,stream=null,context=null,worklet=null,source=null;
let chunks=[],rate=0,started=0,ticker=null,pending=null,backupURL=null,stopping=false,epoch=0,stopWatch=null,capturing=false,armed=false,finishing=false;
const notes={train:'First record 24 takes of “Мышка”, then 24 of “Привет, Мышка”, then 12 similar words and commands. Use one button throughout. Take breaks whenever you need.',val:'After a break: record 8 takes of “Мышка”, then 8 of “Привет, Мышка”, then 8 similar words and commands. Change your position near the Mac slightly.',test:'In a separate final session after a break: record 8 takes of “Мышка”, 8 of “Привет, Мышка”, and 8 similar words and commands. These recordings stay separate from training.'};
async function api(path,body){
 const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),25000);
 try{const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:{'X-Recorder-Token':token,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
 const data=await response.json();if(!response.ok){const e=new Error(data.error||'Save failed');e.status=response.status;throw e;}return data;
 }finally{clearTimeout(timeout);}
}
function message(text,error=false){$('status').textContent=text;$('status').classList.toggle('error',error);}
function tasks(){return state.plan.filter(t=>t.split===split);}
function task(){return state.plan.find(t=>t.id===taskId);}
function selected(id){return state.takes.find(t=>t.task_id===id&&t.selected);}
function pendingGuard(){return !pending&&!busy;}
function buttons(){
 const b=$('record');
 b.textContent=capturing?(armed?(stopping?'Stopping…':'Stop'):'Connecting microphone…'):busy?'Saving…':pending?'Retry save':taskId?'Record':'Session recorded';
 b.disabled=capturing?(!armed||stopping):busy||(!taskId&&!pending);b.classList.toggle('recording',capturing&&armed);
 $('microphone').disabled=busy||!!pending;$('devices').disabled=busy||!!pending;
 document.querySelectorAll('.tab').forEach(b=>b.disabled=busy||!!pending);
}
function render(){
 const list=tasks(),done=list.filter(t=>selected(t.id)).length,current=task();
 $('progress-text').textContent=`Saved ${done} of ${list.length}`;$('saved-count').textContent=`${done} / ${list.length}`;
 $('progress').max=list.length;$('progress').value=done;$('session-note').textContent=notes[split];$('session-intro').hidden=!!state.sessions[split];
 $('storage').textContent='Folder: '+state.storage;
 document.querySelectorAll('.tab').forEach(b=>b.classList.toggle('selected',b.dataset.split===split));
 $('takes').replaceChildren();
 for(const [i,t] of list.entries()){
  const take=selected(t.id),row=document.createElement('div');row.className='take'+(t.id===taskId?' current':'');
  const title=document.createElement('span');title.textContent=`${i+1}. ${t.text}`;title.lang='ru';
  const mark=document.createElement('span');mark.textContent=take?'Saved':t.id===taskId?'Current':'—';row.append(title,mark);$('takes').append(row);
 }
 if(current){const batch=list.filter(t=>t.target===current.target),names={myshka:'Мышка',privet_myshka:'Привет, Мышка',negative:'Similar words and commands'},number=['myshka','privet_myshka','negative'].indexOf(current.target)+1;
 $('batch').textContent=`Batch ${number} of 3 · ${names[current.target]} · ${batch.findIndex(t=>t.id===taskId)+1} / ${batch.length}`;}
 else $('batch').textContent='All three batches complete';
 $('finished').hidden=done!==list.length;$('kind').hidden=!current;$('kind').textContent=current?.target==='negative'?'SAY THE DISPLAYED PHRASE':'SAY IT ONCE';
 $('phrase').textContent=current?.text||'Session complete';$('phrase').lang=current?'ru':'en';$('hint').textContent=current?.hint||'Thank you. All recordings are saved on this Mac.';buttons();
}
async function markFinished(){
 if(finishing)return;const currentSplit=split;finishing=true;
 try{const result=await api('/api/finish',{split:currentSplit});state.analysis_requests.push(result);if(split===currentSplit)$('finish-status').textContent='Ready for analysis. Tell the assistant which session you completed.';}
 catch(e){if(split===currentSplit)$('finish-status').textContent='All WAV files are saved. Could not mark this session ready; reload the page to retry.';}
 finally{finishing=false;}
}
function advance(saved=false){
 taskId=tasks().find(t=>!selected(t.id))?.id||null;$('timer').textContent='00.0';render();
 message(!taskId?'Session complete. Take a break before the next session.':saved?'Saved. Click Record for the next take.':'Click Record when you are ready.');
 if(!taskId){$('finish-status').textContent='Marking this session ready for analysis…';markFinished();}
}
function encodeWav(parts,sampleRate){
 const frames=parts.reduce((n,p)=>n+p.length,0),buffer=new ArrayBuffer(44+frames*2),view=new DataView(buffer);
 const str=(at,s)=>{for(let i=0;i<s.length;i++)view.setUint8(at+i,s.charCodeAt(i));};
 str(0,'RIFF');view.setUint32(4,36+frames*2,true);str(8,'WAVE');str(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);str(36,'data');view.setUint32(40,frames*2,true);
 let at=44;for(const p of parts)for(const x of p){const v=Math.max(-1,Math.min(1,x));view.setInt16(at,v<0?v*32768:v*32767,true);at+=2;}return buffer;
}
function b64(buffer){const a=new Uint8Array(buffer);let s='';for(let i=0;i<a.length;i+=16384)s+=String.fromCharCode(...a.subarray(i,i+16384));return btoa(s);}
function release(){
 clearInterval(ticker);clearTimeout(stopWatch);ticker=null;stopWatch=null;
 if(stream)stream.getTracks().forEach(t=>{t.onended=null;t.stop();});stream=null;
 if(source){try{source.disconnect();}catch{}source=null;}
 if(worklet){worklet.port.onmessage=null;try{worklet.disconnect();}catch{}worklet=null;}
 if(context){context.close().catch(()=>{});context=null;}
 armed=false;$('mic-state').textContent='Microphone off';$('mic-state').classList.remove('live');$('level').style.width='0%';
}
async function record(){
 if(!pendingGuard()||!taskId)return;
 busy=true;capturing=true;armed=false;stopping=false;chunks=[];const myEpoch=++epoch,chosen=task();let mic={};
 $('download').hidden=true;if(backupURL){URL.revokeObjectURL(backupURL);backupURL=null;}
 message('Connecting microphone…');render();
 const ensureActive=()=>{if(myEpoch!==epoch||document.hidden)throw new Error('Recording cancelled. Return to this tab and click Record again.');};
 try{
  if(!navigator.mediaDevices?.getUserMedia||!window.AudioWorkletNode)throw new Error('Open this page in Chrome or Safari on your Mac.');
  context=new AudioContext();await context.resume();ensureActive();
  if(!state.sessions[split]){state.sessions[split]=await api('/api/session',{split});ensureActive();}
  stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:false,noiseSuppression:false,autoGainControl:false,...($('microphone').value?{deviceId:{exact:$('microphone').value}}:{})},video:false});ensureActive();
  const track=stream.getAudioTracks()[0],s=track.getSettings();mic={label:track.label,sampleRate:s.sampleRate,channelCount:s.channelCount,echoCancellation:s.echoCancellation,noiseSuppression:s.noiseSuppression,autoGainControl:s.autoGainControl};
  await context.audioWorklet.addModule('/capture.js');ensureActive();rate=context.sampleRate;mic.contextSampleRate=rate;
  worklet=new AudioWorkletNode(context,'deliberate-capture');source=context.createMediaStreamSource(stream);
  worklet.port.onmessage=({data})=>{
   if(data.type==='started'){armed=true;started=performance.now();$('timer').textContent='00.0';message('SPEAK — recording');$('mic-state').textContent='Recording';$('mic-state').classList.add('live');ticker=setInterval(()=>{$('timer').textContent=((performance.now()-started)/1000).toFixed(1);if(performance.now()-started>12500)stop();},80);buttons();}
   if(data.type==='pcm'){chunks.push(data.pcm);let peak=0;for(const x of data.pcm)peak=Math.max(peak,Math.abs(x));$('level').style.width=Math.min(100,peak*220)+'%';}
   if(data.type==='stopped')complete(chosen,mic);
  };
  source.connect(worklet);worklet.connect(context.destination);track.onended=()=>stop();worklet.port.postMessage('start');
 }catch(e){release();capturing=false;busy=false;stopping=false;message(e.name==='NotAllowedError'?'Allow microphone access for your browser, then click Record again.':e.message,true);render();}
}
function stop(){
 if(!capturing||stopping)return;
 if(!worklet){epoch++;release();message('Start cancelled. Dismiss the microphone permission dialog if it is still open.');return;}
 stopping=true;message('Stopping recording…');buttons();worklet.port.postMessage('stop');
 stopWatch=setTimeout(()=>{release();capturing=false;busy=false;stopping=false;message('The audio stream stopped without confirmation. Record this take again.',true);render();},2500);
}
async function complete(chosen,mic){
 if(!capturing)return;capturing=false;const wav=encodeWav(chunks,rate);release();chunks=[];stopping=false;
 pending={body:{take_id:crypto.randomUUID().replaceAll('-',''),task_id:chosen.id,session_id:state.sessions[chosen.split].id,microphone:mic,wav:b64(wav)},wav};busy=false;await savePending();
}
async function savePending(){
 if(!pending||busy)return;busy=true;message('Saving to your Mac…');render();
 try{
  const take=await api('/api/take',pending.body);state.takes=state.takes.filter(t=>t.id!==take.id).map(t=>t.task_id===take.task_id?{...t,selected:false}:t);state.takes.push(take);
  pending=null;busy=false;$('download').hidden=true;if(backupURL){URL.revokeObjectURL(backupURL);backupURL=null;}advance(true);
 }catch(e){
  busy=false;if(backupURL)URL.revokeObjectURL(backupURL);backupURL=URL.createObjectURL(new Blob([pending.wav],{type:'audio/wav'}));$('download').href=backupURL;$('download').download='wakeword-unsaved-'+pending.body.take_id+'.wav';$('download').hidden=false;
  if(e.status===400){pending=null;message('Could not accept this WAV: '+e.message+'. Click Record for a new take.',true);}
  else message('Not saved: '+e.message+'. The microphone is off; click the same button to retry saving.',true);render();
 }
}
$('record').onclick=()=>{if(capturing)stop();else if(pending)savePending();else record();};
for(const b of document.querySelectorAll('.tab'))b.onclick=()=>{if(!pendingGuard())return;split=b.dataset.split;advance();};
$('devices').onclick=async()=>{
 if(!pendingGuard())return;busy=true;buttons();let permission;
 try{permission=await navigator.mediaDevices.getUserMedia({audio:true,video:false});const devices=await navigator.mediaDevices.enumerateDevices(),current=$('microphone').value;$('microphone').replaceChildren(new Option('Default Mac microphone',''));for(const d of devices.filter(d=>d.kind==='audioinput'))$('microphone').add(new Option(d.label||'Microphone',d.deviceId));if([...$('microphone').options].some(o=>o.value===current))$('microphone').value=current;message('List refreshed. Microphone off.');}
 catch(e){message('Could not list microphones: '+e.message,true);}finally{permission?.getTracks().forEach(t=>t.stop());busy=false;buttons();}
};
document.addEventListener('visibilitychange',()=>{if(document.hidden&&capturing)stop();});window.addEventListener('pagehide',release);
window.addEventListener('beforeunload',e=>{if(busy||pending){e.preventDefault();e.returnValue='';}});
api('/api/status').then(data=>{state=data;advance();}).catch(e=>message('Local server unavailable: '+e.message,true));
