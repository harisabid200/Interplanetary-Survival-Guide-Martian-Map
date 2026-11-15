import test from 'node:test';
import assert from 'node:assert/strict';
import {marsSurfaceDistanceM,rankScienceStops} from '../src/candidateRanking.js';
import {projectionFunctions} from '../src/coordinates.js';

function fixture(){
  const region={width:50,height:50,affine:[20,0,0,0,-20,1000],bounds_m:[0,0,1000,1000],crs:{radius_m:3396190,standard_parallel_deg:18.4663,central_meridian_deg:0}};
  const data={region,grids:{slope:new Float32Array(2500).fill(1),valid:new Uint8Array(2500).fill(1)}};
  const features=[[500,500],[700,500]].map(([x,y],i)=>({type:'Feature',id:`stop-${i}`,geometry:{type:'Point',coordinates:[x,y]},properties:{feature_type:'small crater',source_feature_id:i}}));
  return {data,features,functions:projectionFunctions(region.crs)};
}

test('Mars surface-distance helper uses the configured Mars sphere radius',()=>{
  assert.equal(marsSurfaceDistanceM([0,0],[0,1]),3396190*Math.PI/180);
});

test('candidates sort deterministically by Mars range after buffered-slope and distance criteria',()=>{
  const {data,features,functions}=fixture();
  const start=functions.inverse([100,100]);
  const result=rankScienceStops(features,data,start,1.1,2);
  assert.deepEqual(result.map(candidate=>candidate.feature.id),['stop-0','stop-1']);
  assert.ok(result[0].buffer_cells>100);
  assert.ok(result.every(candidate=>candidate.maximum_slope_within_uncertainty_buffer_deg===1));
  assert.deepEqual(rankScienceStops(features,data,start,.9,2),[]);
  assert.deepEqual(rankScienceStops(features,data,start,1.1,.1),[]);
});

test('candidate uncertainty buffer requires complete source DEM and slope coverage',()=>{
  const {data,features,functions}=fixture();
  const start=functions.inverse([100,100]);
  data.grids.valid[25*50+25]=0;
  assert.deepEqual(rankScienceStops(features,data,start,90,2).map(candidate=>candidate.feature.id),['stop-1']);
  const edge={...features[0],geometry:{...features[0].geometry,coordinates:[100,500]}};
  assert.deepEqual(rankScienceStops([edge],data,start,90,2),[]);
});

test('candidate criteria reject missing or out-of-range user inputs',()=>{
  const {data,features,functions}=fixture();
  const start=functions.inverse([100,100]);
  assert.throws(()=>rankScienceStops(features,data,null,45,5),/starting coordinate/);
  assert.throws(()=>rankScienceStops(features,data,start,NaN,5),/maximum buffered slope/);
  assert.throws(()=>rankScienceStops(features,data,start,45,0),/maximum straight-line range/);
});
