import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {sampleThermal} from '../src/environmentMap.js';
import {projectionFunctions} from '../src/coordinates.js';
const base=new URL('../public/data/environment-map/',import.meta.url);
const meta=JSON.parse(readFileSync(new URL('manifest.json',base)));
const bytes=readFileSync(new URL('thermal.f32',base));
const data={meta,values:Float32Array.from({length:meta.width*meta.height},(_,i)=>bytes.readFloatLE(i*4)),valid:readFileSync(new URL('valid.u8',base))};

test('actual native thermal samples agree with Python/PROJ control points',()=>{
  for(const control of meta.controls){
    const lonlat=projectionFunctions(meta.crs).inverse(control.source_xy_m);
    const value=sampleThermal(lonlat,data);
    assert.equal(value.status,'valid');assert.equal(value.row,control.row);assert.equal(value.col,control.col);assert.equal(value.value,control.value);
  }
});
test('thermal coverage and explicitly synthetic missing samples never invent values',()=>{
  assert.equal(sampleThermal([0,0],data).status,'outside');
  const ll=projectionFunctions(meta.crs).inverse(meta.controls[0].source_xy_m);
  assert.equal(sampleThermal(ll,{...data,valid:new Uint8Array(data.valid.length)}).status,'nodata');
});
