import { renderToStaticMarkup } from 'react-dom/server'
import { expect, it } from 'vitest'
import { HeardQuestion, SourceReferences } from './App'

it('renders an accessible page link and the supporting excerpt as visible text',()=>{
  const html=renderToStaticMarkup(<SourceReferences citations={[{document_id:'sample',page:2,excerpt:'AES-GCM detects changes to encrypted content.'}]} onSelect={()=>{}}/>)
  expect(html).toContain('Open source PDF page 2')
  expect(html).toContain('<blockquote>AES-GCM detects changes to encrypted content.</blockquote>')
})

it('escapes untrusted source markup instead of executing or embedding it',()=>{
  const html=renderToStaticMarkup(<SourceReferences citations={[{document_id:'sample',page:1,excerpt:'<img src=x onerror=alert(1)>'}]} onSelect={()=>{}}/>)
  expect(html).not.toContain('<img')
  expect(html).toContain('&lt;img')
})

it('keeps the heard question and correction action visible independently of the answer',()=>{
  const html=renderToStaticMarkup(<HeardQuestion text={'What does A U B S dash G C M do? <script>bad()</script>'} onCorrect={()=>{}}/>)
  expect(html).toContain('What Jozi heard')
  expect(html).toContain('Correct in text')
  expect(html).toContain('A U B S dash G C M')
  expect(html).not.toContain('<script>')
})
