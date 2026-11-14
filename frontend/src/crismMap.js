import {cellAt,projectionFunctions} from './coordinates.js';

const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');

export async function loadCrism(terrainHash,dataPrefix='') {
  const base=`/data/${dataPrefix}crism/`;
  const response=await fetch(base+'manifest.json');
  if(!response.ok)throw new Error('CRISM map unavailable. Run scripts/fetch_crism_candidate.py and scripts/build_crism_overlay.py.');
  const meta=await response.json();
  if(meta.schema_version!==1||meta.status!=='source-derived'||meta.quantity!=='D2300 spectral summary parameter'||
     meta.terrain_manifest_sha256!==terrainHash||!Number.isInteger(meta.width)||!Number.isInteger(meta.height)||meta.width<1||meta.height<1||meta.width*meta.height>1000000||
     meta.source_image_sha256!=='10eb37e4dd8f2f95a6c3ebdfda5a0b066bd02c33bb2d1e03558c024f3b16ec2d'||
     meta.resampling!=='nearest-neighbour from native 18 m summary parameter to the 20 m app grid; nodata preserved') {
    throw new Error('CRISM source identity or map geometry is unsupported; layer disabled.');
  }
  const names=['d2300.f32','valid.u8','d2300.png','footprint.geojson'];
  const buffers=await Promise.all(names.map(async name=>{
    const result=await fetch(base+name);
    if(!result.ok)throw new Error('CRISM overlay file unavailable.');
    const bytes=await result.arrayBuffer();
    if(bytes.byteLength!==meta.outputs[name].bytes||await hash(bytes)!==meta.outputs[name].sha256)throw new Error('CRISM overlay checksum mismatch; map disabled.');
    return bytes;
  }));
  const length=meta.width*meta.height;
  if(buffers[0].byteLength!==length*4||buffers[1].byteLength!==length)throw new Error('CRISM numeric grid is incomplete.');
  const view=new DataView(buffers[0]);
  return {meta,values:Float32Array.from({length},(_,i)=>view.getFloat32(i*4,true)),
    valid:new Uint8Array(buffers[1]),imageUrl:URL.createObjectURL(new Blob([buffers[2]],{type:'image/png'})),
    footprint:JSON.parse(new TextDecoder().decode(buffers[3]))};
}

export function sampleCrism(lonlat,data) {
  const cell=cellAt(projectionFunctions(data.meta.crs).forward(lonlat),data.meta);
  if(!cell)return {status:'outside'};
  const value=data.values[cell.index];
  return data.valid[cell.index]&&Number.isFinite(value)?{status:'valid',value,row:cell.row,col:cell.col}:{status:'nodata'};
}
