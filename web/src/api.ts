let csrf = ''
export const setCsrf = (value:string) => { csrf = value }
export const getCsrf = () => csrf
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string,string> = {}
  if (!['GET','HEAD'].includes(method)) headers['X-CSRF-Token'] = csrf
  let payload: BodyInit | undefined
  if (body instanceof File) { headers['Content-Type']='application/pdf'; headers['X-File-Name']=encodeURIComponent(body.name); payload=body }
  else if (body !== undefined) { headers['Content-Type']='application/json'; payload=JSON.stringify(body) }
  const response = await fetch('/api/v1'+path, {method, headers, body:payload, credentials:'same-origin'})
  const value = await response.json().catch(()=>({detail:'The server did not return a readable response.'}))
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth')) window.dispatchEvent(new Event('auth-expired'))
    throw new Error(typeof value.detail === 'string' ? value.detail : 'Check the form and try again.')
  }
  return value as T
}
export function parsePages(value:string):number[] {
  if(!value.trim()) return []
  const result = new Set<number>()
  for (const item of value.split(',')) {
    if(!/^\s*\d+(?:\s*-\s*\d+)?\s*$/.test(item)) throw new Error('Use page ranges such as 1-3, 5.')
    const [start, end=start] = item.trim().split('-').map(Number)
    if(start<1 || end>100 || end<start) throw new Error('Choose page numbers from 1 to 100.')
    for(let page=start; page<=end; page++) result.add(page)
  }
  return [...result].sort((a,b)=>a-b)
}
export const formatDate = (value:number) => new Intl.DateTimeFormat('en-ZA',{day:'numeric',month:'short',timeZone:'Africa/Johannesburg'}).format(value*1000)
