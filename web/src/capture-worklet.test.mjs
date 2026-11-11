import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { expect, it } from 'vitest'

it.each([16000,44100,48000])('keeps ten seconds of %i Hz microphone audio at the advertised 16 kHz rate',rate=>{
  const packets=[]
  let Processor
  class AudioProcessor {port={postMessage:(buffer)=>packets.push(buffer)}}
  const source=readFileSync(new URL('./capture-worklet.js',import.meta.url),'utf8')
  runInNewContext(source,{AudioWorkletProcessor:AudioProcessor,sampleRate:rate,registerProcessor:(_name,value)=>{Processor=value}})
  if(!Processor)throw new Error('Processor was not registered')
  const capture=new Processor()
  for(let offset=0;offset<rate*10;offset+=128){
    capture.process([[new Float32Array(Math.min(128,rate*10-offset)).fill(.25)]])
  }
  // At most one 20 ms packet remains buffered at the end of the stream.
  expect(packets.length).toBeGreaterThanOrEqual(499)
  expect(packets.length).toBeLessThanOrEqual(500)
  expect(packets.every(packet=>packet.byteLength===640)).toBe(true)
  expect(new DataView(packets[0]).getInt16(0,true)).toBe(8192)
})
