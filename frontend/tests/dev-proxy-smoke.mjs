// Run against a fresh Vite dev server, with the real Python API on port 8000.
// This HTTP-client probe sends no browser Origin; browser origin policy is
// separately tested by the API/Chrome suite for the supported port 5173.
import assert from 'node:assert/strict';
import {mkdirSync,writeFileSync} from 'node:fs';
const base=new URL(process.argv[2]||'http://127.0.0.1:5173');
assert.ok(['127.0.0.1','localhost'].includes(base.hostname),'Use a loopback development server');
async function json(path,options) {
  const response=await fetch(new URL(path,base),options);
  assert.equal(response.status,200,`${path}: HTTP ${response.status}`);
  assert.match(response.headers.get('content-type')||'',/application\/json/,`${path} returned the SPA HTML fallback`);
  return response.json();
}
const health=await json('/api/health');
assert.equal(health.status,'ready');
const region=await json('/api/region');
assert.ok(region.routing_available);
const points=region.region.control_points;
const routes=await json('/api/routes',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({start_lonlat:points[0].lonlat,end_lonlat:points[1].lonlat,terrain_weight:100,
    primary_objective:'distance',region_manifest_sha256:region.region_manifest_sha256})});
assert.equal(routes.status,'ok');
assert.ok(Math.abs(routes.routes[0].metrics.distance_m-3507.303793900053)<1e-6);
assert.ok(Math.abs(routes.routes[1].metrics.distance_m-3964.3021282773148)<1e-6);
const report={status:'passed',base_url:base.origin,health_and_region_json:true,real_route_post_json:true,
  distance_m:routes.routes[0].metrics.distance_m,terrain_distance_m:routes.routes[1].metrics.distance_m,
  note:'Fresh dev server; existing user-owned 5173 process left running and requires restart.'};
const directory=new URL('../../evidence/fixes/',import.meta.url);
mkdirSync(directory,{recursive:true});
writeFileSync(new URL('dev-proxy.json',directory),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
