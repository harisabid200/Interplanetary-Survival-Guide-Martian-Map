import {projectionFunctions,cellAt} from './coordinates.js';

const hash=async bytes=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
export async function loadThermal(terrainHash,dataPrefix='') {
  const base=`/data/${dataPrefix}environment-map/`;
  const response=await fetch(base+'manifest.json');
  if (!response.ok) throw new Error('Thermal map unavailable. Run scripts/environment_map.py after downloading its verified source.');
  const meta=await response.json();
  if (meta.schema_version!==1||meta.quantity!=='thermal_inertia'||meta.terrain_manifest_sha256!==terrainHash||
      meta.crs.radius_m!==3396190||meta.crs.standard_parallel_deg!==0||meta.crs.central_meridian_deg!==0||
      meta.width<1||meta.height<1||meta.width*meta.height>1000000||meta.affine[0]!==100||meta.affine[4]!==-100) throw new Error('Thermal map geometry or dataset identity is unsupported.');
  const names=['thermal.f32','valid.u8','thermal.png'];
  const buffers=await Promise.all(names.map(async name=>{
    const result=await fetch(base+name);
    if (!result.ok) throw new Error('Thermal map file unavailable.');
    const bytes=await result.arrayBuffer();
    if (bytes.byteLength!==meta.outputs[name].bytes||await hash(bytes)!==meta.outputs[name].sha256) throw new Error('Thermal map checksum mismatch; overlay disabled.');
    return bytes;
  }));
  if (buffers[0].byteLength!==meta.width*meta.height*4||buffers[1].byteLength!==meta.width*meta.height) throw new Error('Incomplete thermal grid.');
  const view=new DataView(buffers[0]);
  return {meta,values:Float32Array.from({length:meta.width*meta.height},(_,i)=>view.getFloat32(i*4,true)),
    valid:new Uint8Array(buffers[1]),imageUrl:URL.createObjectURL(new Blob([buffers[2]],{type:'image/png'}))};
}

export function sampleThermal(lonlat,data) {
  const cell=cellAt(projectionFunctions(data.meta.crs).forward(lonlat),data.meta);
  if (!cell) return {status:'outside'};
  const value=data.values[cell.index];
  return data.valid[cell.index]&&Number.isFinite(value)?{status:'valid',value,row:cell.row,col:cell.col}:{status:'nodata'};
}
