class Capture extends AudioWorkletProcessor {
  constructor(){super();this.samples=[];this.position=0;this.ratio=sampleRate/16000;this.packet=[]}
  process(inputs){
    const channel=inputs[0]?.[0]
    if(!channel)return true
    this.samples.push(...channel)
    while(this.position+1<this.samples.length){
      const index=Math.floor(this.position),fraction=this.position-index
      const sample=this.samples[index]*(1-fraction)+this.samples[index+1]*fraction
      this.packet.push(Math.max(-32768,Math.min(32767,Math.round(sample*32767))))
      this.position+=this.ratio
      if(this.packet.length===320){const data=new Int16Array(this.packet);this.port.postMessage(data.buffer,[data.buffer]);this.packet=[]}
    }
    const consumed=Math.max(0,Math.min(Math.floor(this.position),this.samples.length-1));this.samples.splice(0,consumed);this.position-=consumed
    return true
  }
}
registerProcessor('jozi-capture',Capture)
