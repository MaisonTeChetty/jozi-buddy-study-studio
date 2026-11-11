import {describe,it,expect} from 'vitest'
import {parsePages} from './api'
describe('page ranges',()=>{
  it('supports whole document, ranges, ordering, and duplicate removal',()=>{expect(parsePages('')).toEqual([]);expect(parsePages('3, 1-3, 5')).toEqual([1,2,3,5])})
  it('rejects malformed and unbounded ranges',()=>{for(const value of ['0','2-1','1-101','1; process.exit()','hello'])expect(()=>parsePages(value)).toThrow()})
})
