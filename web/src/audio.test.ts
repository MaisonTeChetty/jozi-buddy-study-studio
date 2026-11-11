import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { VoiceController } from './audio'

class Socket {
  static OPEN=1
  static instances:Socket[]=[]
  readyState=1
  binaryType=''
  onopen?:()=>void
  onclose?:()=>void
  onerror?:()=>void
  onmessage?:(event:{data:string})=>void
  sent:unknown[]=[]
  send(value:unknown){this.sent.push(value)}
  close=vi.fn(()=>{this.readyState=3;this.onclose?.()})
  constructor(){Socket.instances.push(this);queueMicrotask(()=>this.onopen?.())}
  event(value:unknown){this.onmessage?.({data:JSON.stringify(value)})}
}

const track={stop:vi.fn(),enabled:true}
const stream={getTracks:()=>[track],getAudioTracks:()=>[track]}
class Context {
  static instances:Context[]=[]
  currentTime=0
  destination={}
  sources:{stop:ReturnType<typeof vi.fn>;start:ReturnType<typeof vi.fn>}[]=[]
  audioWorklet={addModule:vi.fn().mockResolvedValue(undefined)}
  resume=vi.fn().mockResolvedValue(undefined)
  close=vi.fn().mockResolvedValue(undefined)
  constructor(){Context.instances.push(this)}
  createMediaStreamSource(){return {connect:vi.fn()}}
  createGain(){return {gain:{value:1},connect:vi.fn()}}
  createBuffer(_channels:number,length:number,rate:number){return {duration:length/rate,getChannelData:()=>new Float32Array(length)}}
  createBufferSource(){const source={buffer:undefined,connect:vi.fn(),start:vi.fn(),stop:vi.fn(),onended:undefined};this.sources.push(source);return source}
}
class Capture {
  static current:Capture
  port:{onmessage?: (event:{data:ArrayBuffer})=>void}={}
  connect=vi.fn()
  disconnect=vi.fn()
  constructor(){Capture.current=this}
}
let microphone:ReturnType<typeof vi.fn>
beforeEach(()=>{
  Socket.instances=[];Context.instances=[];track.stop.mockClear();track.enabled=true
  microphone=vi.fn().mockResolvedValue(stream)
  vi.stubGlobal('navigator',{mediaDevices:{getUserMedia:microphone}})
  vi.stubGlobal('location',{protocol:'http:',host:'127.0.0.1:8765'})
  vi.stubGlobal('WebSocket',Socket);vi.stubGlobal('AudioContext',Context);vi.stubGlobal('AudioWorkletNode',Capture)
})
afterEach(()=>vi.unstubAllGlobals())

describe('browser voice lifecycle',()=>{
  it('returns to stopped after microphone permission is denied',async()=>{
    microphone.mockRejectedValue(new DOMException('Microphone denied','NotAllowedError'))
    const states=vi.fn(), voice=new VoiceController(states,vi.fn())
    await expect(voice.start('csrf')).rejects.toThrow('Microphone denied')
    expect(states).toHaveBeenLastCalledWith('stopped')
    expect(Socket.instances).toHaveLength(0)
  })
  it('releases the microphone and audio context when a worklet fails to load',async()=>{
    const brokenContext=class extends Context {
      audioWorklet={addModule:vi.fn().mockRejectedValue(new Error('Worklet blocked'))}
    }
    vi.stubGlobal('AudioContext',brokenContext)
    const state=vi.fn(),voice=new VoiceController(state,vi.fn())
    await expect(voice.start('csrf')).rejects.toThrow('Worklet blocked')
    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(Context.instances[0].close).toHaveBeenCalledTimes(1)
    expect(state).toHaveBeenLastCalledWith('stopped')
  })
  it('clears queued speech on interruption, mutes capture and releases devices on stop',async()=>{
    const states=vi.fn(),voice=new VoiceController(states,vi.fn())
    await voice.start('csrf','selected-document')
    const socket=Socket.instances[0],context=Context.instances[0]
    expect(JSON.parse(socket.sent[0] as string)).toEqual({csrf:'csrf',document_id:'selected-document'})
    socket.event({type:'audio',audio:'AAAAAA==',sample_rate:24000})
    socket.event({type:'audio',audio:'AAAAAA==',sample_rate:24000})
    expect(states).toHaveBeenLastCalledWith('speaking')
    socket.event({type:'interrupt'})
    expect(context.sources.every(source=>source.stop.mock.calls.length===1)).toBe(true)
    expect(states).toHaveBeenLastCalledWith('listening')
    voice.mute();expect(track.enabled).toBe(false)
    const count=socket.sent.length
    Capture.current.port.onmessage?.({data:new ArrayBuffer(640)})
    expect(socket.sent).toHaveLength(count)
    voice.stop();voice.stop()
    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(context.close).toHaveBeenCalledTimes(1)
    expect(states).toHaveBeenLastCalledWith('stopped')
  })
  it('releases a microphone that arrives after Stop was pressed',async()=>{
    let resolve!:(value:unknown)=>void
    microphone.mockImplementation(()=>new Promise(done=>{resolve=done}))
    const voice=new VoiceController(vi.fn(),vi.fn()),starting=voice.start('csrf')
    voice.stop();resolve(stream);await starting
    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(Context.instances).toHaveLength(0)
  })
  it('cleans up a disconnected session and can start a fresh connection',async()=>{
    const states=vi.fn(),voice=new VoiceController(states,vi.fn())
    await voice.start('csrf');Socket.instances[0].close()
    expect(track.stop).toHaveBeenCalledTimes(1)
    expect(states).toHaveBeenLastCalledWith('stopped')
    const second=new VoiceController(states,vi.fn());await second.start('new-csrf')
    expect(Socket.instances).toHaveLength(2)
    second.stop()
  })
  it('sends microphone audio only after the backend confirms readiness',async()=>{
    const voice=new VoiceController(vi.fn(),vi.fn())
    await voice.start('csrf')
    const socket=Socket.instances[0],frame=new ArrayBuffer(640)
    Capture.current.port.onmessage?.({data:frame})
    expect(socket.sent).toHaveLength(1)
    socket.event({type:'state',state:'listening'})
    Capture.current.port.onmessage?.({data:frame})
    expect(socket.sent[1]).toBe(frame)
    voice.stop()
  })
})
