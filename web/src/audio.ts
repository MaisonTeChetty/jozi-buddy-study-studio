export type VoiceState = 'stopped'|'connecting'|'listening'|'thinking'|'speaking'|'muted'
export class VoiceController {
  private socket?:WebSocket
  private stream?:MediaStream
  private context?:AudioContext
  private capture?:AudioWorkletNode
  private sources = new Set<AudioBufferSourceNode>()
  private scheduled = 0
  private muted=false
  private cleaned=false
  private ready=false
  constructor(private onState:(state:VoiceState)=>void, private onEvent:(event:Record<string,unknown>)=>void){}
  async start(csrf:string, documentId?:string) {
    this.cleaned=false
    this.ready=false;this.muted=false
    this.onState('connecting')
    try {
      this.stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1},video:false})
      if(this.cleaned) { this.stream.getTracks().forEach(track=>track.stop()); return }
      this.context=new AudioContext()
      await this.context.resume()
      await this.context.audioWorklet.addModule(new URL('./capture-worklet.js?no-inline',import.meta.url).href)
      if(this.cleaned)return
      this.socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/v1/voice`)
      this.socket.binaryType='arraybuffer'
      await new Promise<void>((resolve,reject)=>{
        this.socket!.onopen=()=>resolve()
        this.socket!.onerror=()=>reject(new Error('Could not open a voice connection.'))
        this.socket!.onclose=()=>reject(new Error('Voice connection was not accepted. Check your session and voice allowance.'))
      })
      if(this.cleaned){this.socket.close();return}
      this.socket.send(JSON.stringify({csrf,document_id:documentId}))
      this.socket.onmessage=event=>this.receive(JSON.parse(event.data))
      this.socket.onclose=()=>this.stop()
      this.socket.onerror=()=>this.onEvent({type:'error',message:'The voice connection was interrupted. You can reconnect.'})
      this.capture=new AudioWorkletNode(this.context,'jozi-capture')
      this.capture.port.onmessage=event=>{if(this.ready && this.socket?.readyState===WebSocket.OPEN && !this.muted) this.socket.send(event.data)}
      const input=this.context.createMediaStreamSource(this.stream)
      const silent=this.context.createGain(); silent.gain.value=0
      input.connect(this.capture); this.capture.connect(silent); silent.connect(this.context.destination)
    } catch(error) { this.stop(); throw error }
  }
  private receive(event:Record<string,unknown>) {
    if(this.cleaned) return
    if(event.type==='state'&&event.state==='listening')this.ready=true
    if(event.type==='audio' && this.context) {
      const raw=atob(event.audio as string), data=new Uint8Array(raw.length)
      for(let index=0;index<raw.length;index++) data[index]=raw.charCodeAt(index)
      const view=new DataView(data.buffer), samples=this.context.createBuffer(1,raw.length/2,Number(event.sample_rate)||16000)
      const channel=samples.getChannelData(0)
      for(let index=0;index<channel.length;index++) channel[index]=view.getInt16(index*2,true)/32768
      const source=this.context.createBufferSource(); source.buffer=samples; source.connect(this.context.destination)
      const start=Math.max(this.context.currentTime+0.03,this.scheduled)
      this.scheduled=start+samples.duration; this.sources.add(source)
      source.onended=()=>{this.sources.delete(source); if(!this.cleaned&&!this.sources.size) this.onState(this.muted?'muted':'listening')}
      source.start(start); this.onState(this.muted?'muted':'speaking')
    } else if(event.type==='interrupt') {this.clearPlayback();this.onState(this.muted?'muted':'listening')}
    else if(event.type==='state') {if(!this.sources.size) this.onState(this.muted?'muted':event.state as VoiceState)}
    else if(event.type==='transcript' && event.role==='user') this.onState(this.muted?'muted':'thinking')
    this.onEvent(event)
  }
  private clearPlayback(){for(const source of this.sources){try{source.stop()}catch{/*already ended*/}}this.sources.clear();this.scheduled=0}
  mute(){this.muted=!this.muted;this.stream?.getAudioTracks().forEach(track=>track.enabled=!this.muted);if(this.socket?.readyState===WebSocket.OPEN)this.socket.send(JSON.stringify({type:'mute',muted:this.muted}));this.onState(this.muted?'muted':'listening')}
  stop(){if(this.cleaned)return;this.cleaned=true;this.ready=false;this.clearPlayback();this.stream?.getTracks().forEach(track=>track.stop());this.capture?.disconnect();void this.context?.close();if(this.socket?.readyState===WebSocket.OPEN)this.socket.send(JSON.stringify({type:'stop'}));this.socket?.close();this.onState('stopped')}
}

export function localVoices(){return window.speechSynthesis?.getVoices().filter(voice=>voice.localService)??[]}
