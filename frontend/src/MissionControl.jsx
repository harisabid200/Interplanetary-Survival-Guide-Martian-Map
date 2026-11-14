import React, {useEffect, useRef, useState} from 'react';
import {projectionFunctions, sampleAt} from './coordinates.js';
import {apiJson} from './api.js';
import {EnvironmentPanel} from './EnvironmentPanel.jsx';

export const CATALOG = [
  {id:'temperature',group:'Environmental',label:'Temperature & weather',stage:'M4',source:'MEDA Â· Perseverance / Jezero',url:'https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/PERSEVERANCE/meda.html',kind:'Historical rover observations',description:'Sol 15 temperature and pressure imported with PDS checksums, clocks and same-sol landing-site-relative rover positions. Wind and humidity not imported.',limit:'Rover-local historical samples cannot describe current weather across the pilot.'},
  {id:'dust',group:'Environmental',label:'Atmospheric dust & storms',stage:'M4',source:'MARCI Â· Mars Reconnaissance Orbiter',url:'https://pds.nasa.gov/ds-view/pds/viewDataset.jsp?dsid=MRO-M-MARCI-2-EDR-L0-V1.0',kind:'Historical regional context',description:'Dated MSSS-606 regional report for 17?23 January 2022 imported as context. No calibrated, geolocated dust raster imported.',limit:'No local storm boundary, dust hazard distribution or forecast is available.'},
  {id:'radiation',group:'Environmental',label:'Radiation reference',stage:'M4',source:'RAD Â· Curiosity / Gale Crater',url:'https://doi.org/10.17189/1519761',kind:'Gale reference only Â· not Jezero',description:'Gale surface-sol-1 PDS product label, README and errata verified. Numeric science transfer incomplete; no dose value imported. MEDA optical radiation is a different measurement.',limit:'Gale radiation is not measured Jezero radiation. No Jezero dose map or exposure calculation is available.'},
  {id:'minerals',group:'Scientific',label:'CRISM D2300 spectral index',stage:'M5',source:'CRISM MTRDR Â· FRT000047A3 Â· PDS Geosciences Node',url:'https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/2007/2007_057/frt000047a3/',kind:'Observed spectral parameter Â· 18 m source',description:'D2300 is one dimensionless 2.3 Âµm spectral-drop parameter from the noise-remediated CRISM spectral summary. The real targeted scene overlaps 45.4% of the pilot footprint; the nearest-neighbour display is aligned to the 20 m app grid.',limit:'D2300 can be sensitive to hydrated minerals, including clays, but is not a unique mineral identification, concentration, deposit, accessible water, or safety measurement. CRISM summary processing spatially interpolates flagged outliers; surface is incomplete.'},
  {id:'geology',group:'Scientific',label:'Geological features',stage:'M5',source:'USGS Â· Sun & Stack (2020), SIM 3464',url:'https://doi.org/10.3133/sim3464',kind:'Published geological interpretation',description:'The actual GeoUnits_v1 polygons are transformed from the published Mars Transverse Mercator geodatabase into the pilot map CRS. Only polygons whose source geometry intersects the 5 Ã— 5 km pilot are served.',limit:'Source warns of random 100â€“200 m offsets versus the controlled CTX map. This qualitative regional interpretation does not establish mineral concentration, accessible water, or safe terrain.'},
  {id:'water',group:'Scientific',label:'Ancient-water evidence',stage:'M5',source:'Published Jezero lake / delta context',url:'https://science.nasa.gov/resource/jezero-craters-ancient-lakeshore/',kind:'Past geological processes',description:'Published regional interpretation is a candidate context source. No validated aqueous-feature polygons or resource inventory imported.',limit:'Ancient water evidence is not accessible drinking water, extractable ice or a present resource estimate.'},
];

function endpointValues(inputs, prefix) {
  const raw=[inputs[`${prefix}Lon`],inputs[`${prefix}Lat`]];
  if (raw.some(value => value.trim()==='')) throw new Error('Choose both start and destination coordinates.');
  const values=raw.map(Number);
  if (!values.every(Number.isFinite) || values[0]<0 || values[0]>=360 || Math.abs(values[1])>90) throw new Error('Use finite positive-east longitude [0,360) and planetocentric latitude [âˆ’90,90].');
  return values;
}

export function useMission(data) {
  const [inputs,setInputs]=useState({startLon:'',startLat:'',endLon:'',endLat:'',weight:'100',limit:'',objective:'distance'});
  const [mode,setMode]=useState('inspect');
  const [result,setResult]=useState(null);
  const [status,setStatus]=useState('idle');
  const [error,setError]=useState('');
  const [api,setApi]=useState({status:'connecting',message:'Checking local routing serviceâ€¦'});
  const [activeRoute,setActiveRoute]=useState('distance');
  const controller=useRef(null);
  const generation=useRef(0);
  async function connect() {
    if (!data) return;
    setApi({status:'connecting',message:'Checking local routing serviceâ€¦'});
    try {
      const response=await fetch(`/api/region?region_id=${encodeURIComponent(data.regionId)}`,{signal:AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('Routing service unavailable. Terrain inspection still works. Start the local API, then reconnect.');
      const region=await apiJson(response);
      if (!region.routing_available || region.region_manifest_sha256!==data.manifestHash) throw new Error('Map and routing datasets differ. Regenerate data and reload before planning.');
      setApi({status:'ready',message:'Verified terrain connected Â· local routing'});
    } catch(error) {setApi({status:'unavailable',message:error.message});}
  }
  useEffect(() => {connect(); return () => controller.current?.abort();},[data]);
  useEffect(() => {
    if ((status==='ok'||status==='no_path')&&window.matchMedia('(max-width:760px)').matches) {
      document.getElementById('mission-results')?.scrollIntoView({block:'start'});
    }
  },[status]);
  function invalidate() {
    generation.current++;
    controller.current?.abort();
    setResult(null); setStatus('idle'); setError('');
  }
  function change(patch) {invalidate(); setInputs(old=>({...old,...patch}));}
  function pick(sample) {
    if (sample.status!=='valid' || sample.slope===null) {setError('Select a cell inside valid elevation and slope coverage.'); return;}
    const prefix=mode==='start'?'start':'end';
    change({[`${prefix}Lon`]:sample.lonlat[0].toFixed(9),[`${prefix}Lat`]:sample.lonlat[1].toFixed(9)});
    setMode('inspect');
  }
  function verificationPair() {
    if (!data) return;
    const [start,end]=data.region.control_points;
    change({startLon:String(start.lonlat[0]),startLat:String(start.lonlat[1]),endLon:String(end.lonlat[0]),endLat:String(end.lonlat[1])});
    setMode('inspect');
  }
  async function compare(event) {
    event?.preventDefault();
    invalidate();
    const version=generation.current;
    try {
      if (api.status!=='ready') throw new Error(api.message);
      const start=endpointValues(inputs,'start'),end=endpointValues(inputs,'end');
      const weight=Number(inputs.weight),limit=inputs.limit.trim()===''?null:Number(inputs.limit);
      if (inputs.weight.trim()==='' || !Number.isFinite(weight) || weight<0 || weight>1e6) throw new Error('Terrain weight must be between 0 and 1,000,000.');
      if (limit!==null && (!Number.isFinite(limit) || limit<0 || limit>90)) throw new Error('Assumed cell-slope limit must be between 0Â° and 90Â°.');
      const {forward}=projectionFunctions(data.region.crs);
      for (const ll of [start,end]) {
        const sample=sampleAt(forward(ll),data.region,data.grids);
        if (sample.status!=='valid' || sample.slope===null) throw new Error('Endpoint is outside valid elevation/slope coverage. No route was calculated.');
        if (limit!==null && sample.slope>limit) throw new Error('Endpoint exceeds the assumed cell-slope limit.');
      }
      setStatus('loading');
      controller.current=new AbortController();
      const response=await fetch('/api/routes',{method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.any([controller.current.signal,AbortSignal.timeout(30000)]),
        body:JSON.stringify({start_lonlat:start,end_lonlat:end,terrain_weight:weight,max_cell_slope_deg:limit,
          primary_objective:inputs.objective,region_manifest_sha256:data.manifestHash,region_id:data.regionId})});
      const body=await apiJson(response);
      if (!response.ok) throw new Error(body.message||'Route request failed.');
      if (body.region_manifest_sha256!==data.manifestHash) throw new Error('Route dataset differs from the displayed map. Reload the verified data.');
      if (version===generation.current) {setResult(body);setActiveRoute(inputs.objective);setStatus(body.status);}
    } catch(error) {
      if (error.name!=='AbortError' && version===generation.current) {setError(error.message||'Routing service unavailable.');setStatus('error');}
    }
  }
  const markers=[];
  if (data) for (const [prefix,label] of [['start','A'],['end','B']]) {
    try {
      const ll=endpointValues(inputs,prefix);
      const sample=sampleAt(projectionFunctions(data.region.crs).forward(ll),data.region,data.grids);
      if (sample.status==='valid' && sample.slope!==null) markers.push({label,center:sample.center});
    } catch { /* Unset/invalid inputs have no fabricated map marker. */ }
  }
  return {inputs,change,mode,setMode,pick,result,status,error,api,connect,compare,verificationPair,markers,activeRoute,setActiveRoute,regionId:data?.regionId||'jezero-m1',
    clear:()=>{change({startLon:'',startLat:'',endLon:'',endLat:''});setMode('inspect');}};
}

export function MissionPlanner({mission}) {
  const {inputs,change}=mission;
  return <section className="mission-planner" id="mission-planner">
    <div className="section-heading"><h2>Mission planning</h2><span>01</span></div>
    <p className="planner-intro">Choose a simulated start and destination inside the selected verified terrain region.</p>
    <form onSubmit={mission.compare} noValidate>
      {[['start','A','Starting location'],['end','B','Destination']].map(([prefix,letter,label])=><fieldset key={prefix}>
        <legend><span className={`endpoint-letter ${prefix}`}>{letter}</span>{label}</legend>
        <div className="coordinate-inputs">
          <label>Longitude Â°E<input aria-label={`${label} longitude`} type="number" step="any" value={inputs[`${prefix}Lon`]} onChange={e=>change({[`${prefix}Lon`]:e.target.value})} placeholder="Positive east"/></label>
          <label>Latitude Â°N<input aria-label={`${label} latitude`} type="number" step="any" value={inputs[`${prefix}Lat`]} onChange={e=>change({[`${prefix}Lat`]:e.target.value})} placeholder="Planetocentric"/></label>
        </div>
        <button type="button" className={`pick-button ${mission.mode===(prefix==='start'?'start':'destination')?'active':''}`} aria-pressed={mission.mode===(prefix==='start'?'start':'destination')} onClick={()=>mission.setMode(prefix==='start'?'start':'destination')}>âŒ– Pick {prefix==='start'?'start':'destination'} on map</button>
      </fieldset>)}
      <label className="form-label">Exploration objective<select aria-label="Exploration objective" value={inputs.objective} onChange={e=>change({objective:e.target.value})}><option value="distance">Distance priority</option><option value="terrain">Terrain priority</option></select></label>
      <details className="route-assumptions"><summary>Terrain assumptions</summary><label className="form-label">Grade penalty weight<input aria-label="Grade penalty weight" type="number" min="0" max="1000000" step="any" value={inputs.weight} onChange={e=>change({weight:e.target.value})}/></label><label className="form-label">Optional cell-slope limit (Â°)<input aria-label="Cell-slope limit" type="number" min="0" max="90" step="any" placeholder="No exclusion" value={inputs.limit} onChange={e=>change({limit:e.target.value})}/></label><p>Assumptions, not safety thresholds. Local cell-gradient limits do not cap segment slope. Weight is a heuristic, not a physiological model.</p></details>
      <button className="compare-button" type="submit" disabled={mission.api.status!=='ready'||mission.status==='loading'}>{mission.status==='loading'?'Calculating on verified terrain...':'Compare routes'}</button>
      <div className="planner-actions"><button type="button" onClick={mission.verificationPair}>Load verification pair</button><button type="button" onClick={mission.clear}>Clear</button></div>
      <p className="verification-note">Verification locations are test selections, not designated science sites.</p>
    </form>
    <div className={`api-state ${mission.api.status}`} role="status">{mission.api.message}{mission.api.status==='unavailable'&&<button onClick={mission.connect}>Reconnect routing</button>}</div>
    {mission.error&&<p role="alert" className="mission-error">{mission.error}</p>}
  </section>;
}

export function ContextLayers({group,enabled,onToggle,geologyAvailable=false,geologyError='',geologyMeta,crismAvailable=false,crismError='',crismMeta,regionId='jezero-m1'}) {
  return <section className="context-layers"><div className="section-heading"><h2>{group} intelligence</h2><span>{group==='Environmental'?'M4':'M5'}</span></div>
    {CATALOG.filter(item=>item.group===group).map(item=>{const geo=item.id==='geology',crism=item.id==='minerals';const available=geo?geologyAvailable:crism?crismAvailable:false;const error=geo?geologyError:crism?crismError:'';const coverage=geo?`${geologyMeta?.region_intersecting_feature_count??geologyMeta?.pilot_intersecting_feature_count??0} intersecting polygons, 100-200 m registration uncertainty`:`${((crismMeta?.valid_fraction??0)*100).toFixed(1)}% valid cells`;const status=available?(geo?`VERIFIED GIS / ${regionId==='expanded-7p5km'?'7.5 KM':'5 KM'} / ${coverage}`:`VERIFIED CRISM / ${coverage}`):error?'SOURCE DATA UNAVAILABLE':crism?'PDS MTRDR / LOAD ON ENABLE':geo?'USGS GIS / LOAD ON ENABLE':'HISTORICAL CONTEXT / CHECK AVAILABILITY';return <label className="context-layer" key={item.id}><input type="checkbox" aria-label={`${item.label} context`} checked={enabled.includes(item.id)} onChange={()=>onToggle(item.id)}/><span><b>{item.label}</b><small>{status}</small></span><span className="pending-dot" title={available?'Verified source-derived map overlay':'Context only; no areal overlay'}>{available?'ON':'--'}</span></label>;})}
    <p className="context-help">{group==='Scientific'?'Geology draws published map units; CRISM draws the measured D2300 spectral index within its observation footprint. Coverage and missing cells vary by selected region. Remaining science layers are context-only.':'Toggles open source/availability context. No unverified geographic overlay is drawn.'}</p>
  </section>;
}

function ElevationProfile({routes,active}) {
  const usable=routes.filter(r=>r.status==='ok');
  const elevations=usable.flatMap(r=>r.profile.map(p=>p.elevation_m));
  if (!elevations.length) return null;
  const low=Math.min(...elevations),high=Math.max(...elevations),span=Math.max(high-low,1);
  const length=Math.max(...usable.map(r=>r.metrics.distance_m),1);
  const point=p=>[42+p.distance_m/length*244,14+(high-p.elevation_m)/span*78];
  return <section className="profile-panel"><h3>Elevation profile <span>DERIVED</span></h3><svg viewBox="0 0 310 125" role="img" aria-label="Actual route elevation profiles in metres versus horizontal Mars distance">
    <line x1="42" y1="14" x2="42" y2="93" stroke="#657779"/><line x1="42" y1="93" x2="286" y2="93" stroke="#657779"/>
    <text x="3" y="18">{high.toFixed(0)} m</text><text x="3" y="94">{low.toFixed(0)} m</text><text x="42" y="113">0 m</text><text x="245" y="113">{length.toFixed(0)} m</text>
    {usable.map(route=>{const points=route.profile.map(point);const color=route.objective==='distance'?'#67e0ef':'#ffb176';return <g key={route.objective} opacity={active===route.objective?1:.6}><polyline points={points.map(p=>p.join(',')).join(' ')} fill="none" stroke={color} strokeWidth={active===route.objective?2.5:1.5}/>{points.length===1&&<circle cx={points[0][0]} cy={points[0][1]} r="3" fill={color}/>}</g>;})}
  </svg><p>Native DEM samples Â· each route has its own cumulative distance. Snap offsets excluded.</p></section>;
}

export function MissionInsights({mission,contexts,geologyMeta,crismMeta}) {
  const result=mission.result;
  return <aside className="mission-insights" id="mission-results" aria-label="Mission intelligence and context">
    <div className="eyebrow orange">MISSION INTELLIGENCE</div><h2>Route comparison</h2>
    {!result&&<div className="empty-routes"><span aria-hidden="true">A â”€â”€ B</span><h3>{mission.status==='loading'?'Computing both objectivesâ€¦':'Plan your traverse.'}</h3><p>Choose two locations and compare actual distance and terrain costs. No route is inferred before calculation.</p></div>}
    {result?.status==='no_path'&&<div role="status" className="no-path"><h3>No connected route</h3><p>No path exists through the eligible grid under these assumptions. Change endpoints or the assumed cell-slope limit.</p></div>}
    {result?.status==='ok'&&<>
      {result.identical_paths&&<p className="coincident" role="status">Both objectives use the same native path.{result.routes[0].geometry.type==='Point'?' Start and destination share one cell.':''}</p>}
      {result.routes.map(route=><button type="button" className={`route-card ${route.objective} ${mission.activeRoute===route.objective?'selected':''}`} key={route.objective} aria-pressed={mission.activeRoute===route.objective} onClick={()=>mission.setActiveRoute(route.objective)} aria-label={`Focus ${route.objective} route`}>
        <span className="route-name"><i/>{route.objective==='distance'?'Distance objective':'Terrain objective'}<small>{mission.activeRoute===route.objective?'FOCUSED':'VIEW'}</small></span>
        <strong data-testid={`${route.objective}-distance`}>{route.metrics.distance_m.toLocaleString('en-US',{minimumFractionDigits:1,maximumFractionDigits:1})}<small> m</small></strong>
        <span className="route-metrics"><span>Ascent <b data-testid={`${route.objective}-ascent`}>{route.metrics.positive_ascent_m.toFixed(1)} m</b></span><span>Max segment <b data-testid={`${route.objective}-slope`}>{route.metrics.max_sampled_segment_slope_deg.toFixed(2)}Â°</b></span></span>
        <span className="local-slope">Max local cell {route.metrics.max_sampled_cell_slope_deg.toFixed(2)}Â° Â· {route.coverage.native_cells} native cells</span>
      </button>)}
      <ElevationProfile routes={result.routes} active={mission.activeRoute}/>
      <details className="result-method"><summary>Cost, coverage & provenance</summary><p>Distance = sum of Mars-geodesic segments. Terrain cost = d Ã— (1 + weight Ã— gradeÂ²). Current weight: {result.parameters.terrain_weight}; cell limit: {result.parameters.max_cell_slope_deg??'none'}Â°.</p>{result.routes.map(route=><p key={route.objective}>{route.objective}: objective cost {route.metrics.objective_cost_m.toFixed(2)}; penalty {route.metrics.terrain_penalty_cost_m.toFixed(2)} penalized metres. This is not time, effort or physical distance.</p>)}<p>All path and diagonal-support cells eligible. Start snap {result.endpoints.start.snap_distance_m.toFixed(2)} m; destination snap {result.endpoints.end.snap_distance_m.toFixed(2)} m, excluded from path distance.</p><p className="hash-text">Region {mission.regionId} manifest {result.region_manifest_sha256}<br/>Engine {result.routing_source_sha256}</p></details>
    </>}
    <div className="context-heading"><div className="eyebrow">EVIDENCE & AVAILABILITY</div><p>Observation, derived result and planned capability remain separate.</p></div>
    {!contexts.length&&<p className="context-empty">Enable environmental or scientific context in the left sidebar to inspect candidate sources and limits.</p>}
    {contexts.map(id=>{const item=CATALOG.find(row=>row.id===id);const description=id==='geology'?`${geologyMeta?.region_intersecting_feature_count??geologyMeta?.pilot_intersecting_feature_count??'Source-derived'} published SIM 3464 unit polygons intersect this selected region; source registration uncertainty remains 100-200 m.`:id==='minerals'?`The verified CRISM scene intersects ${(((crismMeta?.region_area_intersection_fraction??crismMeta?.pilot_area_intersection_fraction??crismMeta?.valid_fraction??0)*100)).toFixed(1)}% of this region by area; ${((crismMeta?.valid_fraction??0)*100).toFixed(1)}% of target grid cells have valid values. D2300 is a spectral-shape parameter, not a mineral identification.`:item.description;return <section className="context-card" key={id}><span className="type-label">{item.group.toUpperCase()} / {item.stage}{item.group==='Scientific'?' SOURCE DATA':' ARCHIVE CONTEXT'}</span><h3>{item.label}</h3>{item.group==='Environmental'?<><EnvironmentPanel id={id}/>{id==='temperature'&&<a href={item.url} target="_blank" rel="noreferrer">{item.source}</a>}<p className="unavailable-label">Spatial layer unavailable / historical context only</p></>:<><span className="evidence-kind">{item.kind}</span><p>{description}</p><p className="context-limit">{item.limit}</p><a href={item.url} target="_blank" rel="noreferrer">{item.source}</a><p className="unavailable-label">{id==='geology'?'Map overlay uses source unit polygons; it is not a mineral or water resource inventory.':id==='minerals'?'Map overlay shows a measured spectral parameter, not identified mineral deposits.':'Spatial layer unavailable / no measurements shown'}</p></>}</section>;})}
    <div className="mission-future"><span className="type-label">M6 Â· PLANNED</span><p>Mission budgets and candidate recommendations await explicit assumptions and verified criteria. No travel time or site suitability is calculated yet.</p></div>
  </aside>;
}
