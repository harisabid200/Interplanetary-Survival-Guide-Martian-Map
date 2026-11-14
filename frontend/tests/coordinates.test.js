import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {cellAt, cellCenter, projectionFunctions, sampleAt} from '../src/coordinates.js';

const region = JSON.parse(readFileSync(new URL('../public/data/manifest.json', import.meta.url)));
const functions = projectionFunctions(region.crs);
test('five real Python/PROJ reference points match JS Mars transform and imagery placement', () => {
  for (const p of region.control_points) {
    const coordinate = functions.forward(p.lonlat);
    assert.ok(Math.hypot(coordinate[0] - p.x_m, coordinate[1] - p.y_m) < 1e-6);
    assert.deepEqual(cellAt(coordinate, region), {row: p.row, col: p.col, index: p.row*region.width+p.col});
    const center = cellCenter(p.row, p.col, region);
    assert.ok(Math.hypot(center[0]-p.x_m, center[1]-p.y_m) < 1e-6);
    const [w,s,e,n] = region.imagery_bounds_m;
    const image = [w+p.imagery_pixel[0]/region.imagery_size[0]*(e-w), n-p.imagery_pixel[1]/region.imagery_size[1]*(n-s)];
    assert.ok(Math.hypot(image[0]-p.x_m, image[1]-p.y_m) < 1e-6);
  }
});
test('all 62500 real cell centers roundtrip without Earth CRS shortcuts', () => {
  for (let row=0; row<region.height; row++) for (let col=0; col<region.width; col++) {
    const coordinate=functions.forward(functions.inverse(cellCenter(row,col,region)));
    const cell=cellAt(coordinate,region);
    assert.equal(cell.row,row); assert.equal(cell.col,col);
  }
});
test('edges and invalid coordinates are never clamped into terrain', () => {
  const [w,s,e,n]=region.bounds_m;
  assert.deepEqual(cellAt([w,n],region), {row:0,col:0,index:0});
  for (const point of [[e,n], [w,s], [w-1,n], [w,n+1], [NaN,n], [w,Infinity]]) assert.equal(cellAt(point,region),null);
});
test('synthetic masks distinguish elevation nodata and missing slope', () => {
  const region={width:2,height:2,affine:[20,0,0,0,-20,40],crs:{radius_m:3396190,standard_parallel_deg:18.4663,central_meridian_deg:0}};
  const grids={elevation:[10,20,30,40],slope:[1,2,3,4],valid:[0,1,1,1],slopeValid:[0,0,1,1]};
  assert.equal(sampleAt([10,30],region,grids).status,'nodata');
  assert.equal(sampleAt([30,30],region,grids).slope,null);
  assert.equal(sampleAt([-1,30],region,grids).status,'outside');
});
