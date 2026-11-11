import { readdir, readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const directory=fileURLToPath(new URL('../dist/assets/',import.meta.url))
const files=await readdir(directory)
const worklets=files.filter(name=>/^capture-worklet-.*\.js$/.test(name))
if(worklets.length!==1)throw new Error('The microphone worklet must be emitted as one local JavaScript asset.')
const worklet=worklets[0]
const source=await readFile(path.join(directory,worklet),'utf8')
if(!source.includes("registerProcessor('jozi-capture'"))throw new Error('The microphone processor is missing from its asset.')
const bundles=await Promise.all(files.filter(name=>/^index-.*\.js$/.test(name)).map(name=>readFile(path.join(directory,name),'utf8')))
if(!bundles.some(bundle=>bundle.includes(worklet)))throw new Error('The browser bundle does not reference the local worklet.')
if(bundles.some(bundle=>bundle.includes('data:text/javascript;base64,')))throw new Error('An inline script URL would be blocked by the studio CSP.')
console.log('Microphone worklet asset check passed.')
