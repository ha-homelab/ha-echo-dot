// No sound is sent to the output. PCM is collected only between explicit commands.
class Capture extends AudioWorkletProcessor {
  constructor() {
    super(); this.active=false;this.frames=0;this.buffer=[];
    this.port.onmessage=({data})=>{
      if(data==='start'){this.active=true;this.frames=0;this.buffer=[];this.port.postMessage({type:'started'});}
      if(data==='stop')this.finish();
    };
  }
  finish(){if(!this.active)return;this.active=false;this.flush();this.port.postMessage({type:'stopped'});}
  flush(){if(this.buffer.length){let pcm=new Float32Array(this.buffer);this.port.postMessage({type:'pcm',pcm},[pcm.buffer]);this.buffer=[];}}
  process(inputs){
    if(this.active && inputs[0]?.length){
      const channels=inputs[0];
      for(let i=0;i<channels[0].length;i++){
        if(this.frames>=sampleRate*12){this.finish();break;}
        let v=0;for(const c of channels)v+=c[i];this.buffer.push(v/channels.length);this.frames++;
      }
      if(this.buffer.length>=2048)this.flush();
    }
    return true;
  }
}
registerProcessor('deliberate-capture',Capture);
