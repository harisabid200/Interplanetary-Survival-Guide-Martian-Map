import React, {useEffect, useRef, useState} from 'react';
import {projectionFunctions, sampleAt} from './coordinates.js';
import {apiJson} from './api.js';
import {EnvironmentPanel} from './EnvironmentPanel.jsx';
import {rankScienceStops} from './candidateRanking.js';

export const CATALOG = [
  {id:'temperature',group:'Environmental',label:'Temperature & weather',stage:'M4',source:'MEDA Â· Perseverance / Jezero',url:'https://pds-atmospheres.nmsu.edu/data_and_services/atmospheres_data/PERSEVERANCE/meda.html',kind:'Historical rover observations',description:'Sol 15 temperature and pressure imported with PDS checksums, clocks and same-sol landing-site-relative rover positions. Wind and humidity not imported.',limit:'Rover-local historical samples cannot describe current weather across the pilot.'},
  {id:'dust',group:'Environmental',label:'Atmospheric dust & storms',stage:'M4',source:'MARCI Â· Mars Reconnaissance Orbiter',url:'https://pds.nasa.gov/ds-view/pds/viewDataset.jsp?dsid=MRO-M-MARCI-2-EDR-L0-V1.0',kind:'Historical regional context',description:'Dated MSSS-606 regional report for 17?23 January 2022 imported as context. No calibrated, geolocated dust raster imported.',limit:'No local storm boundary, dust hazard distribution or forecast is available.'},
  {id:'radiation',group:'Environmental',label:'Radiation reference',stage:'M4',source:'RAD Â· Curiosity / Gale Crater',url:'https://doi.org/10.17189/1519761',kind:'Gale reference only Â· not Jezero',description:'Gale surface-sol-1 PDS product label, README and errata verified. Numeric science transfer incomplete; no dose value imported. MEDA optical radiation is a different measurement.',limit:'Gale radiation is not measured Jezero radiation. No Jezero dose map or exposure calculation is available.'},
  {id:'minerals',group:'Scientific',label:'CRISM D2300 spectral index',stage:'M5',source:'CRISM MTRDR Â· FRT000047A3 Â· PDS Geosciences Node',url:'https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/2007/2007_057/frt000047a3/',kind:'Observed spectral parameter Â· 18 m source',description:'D2300 is one dimensionless 2.3 Âµm spectral-drop parameter from the noise-remediated CRISM spectral summary. The real targeted scene overlaps 45.4% of the pilot footprint; the nearest-neighbour display is aligned to the 20 m app grid.',limit:'D2300 can be sensitive to hydrated minerals, including clays, but is not a unique mineral identification, concentration, deposit, accessible water, or safety measurement. CRISM summary processing spatially interpolates flagged outliers; surface is incomplete.'},
  {id:'geology',group:'Scientific',label:'Geological features',stage:'M5',source:'USGS Â· Sun & Stack (2020), SIM 3464',url:'https://doi.org/10.3133/sim3464',kind:'Published geological interpretation',description:'The actual GeoUnits_v1 polygons are transformed from the published Mars Transverse Mercator geodatabase into the pilot map CRS. Only polygons whose source geometry intersects the 5 Ã— 5 km pilot are served.',limit:'Source warns of random 100â€“200 m offsets versus the controlled CTX map. This qualitative regional interpretation does not establish mineral concentration, accessible water, or safe terrain.'},
  {id:'science-stops',group:'Scientific',label:'Mapped science stops',stage:'M5',source:'USGS · Sun & Stack (2020), SIM 3464',url:'https://doi.org/10.3133/sim3464',kind:'Source-mapped point features',description:'The USGS LocationFeatures GIS layer contains mapped small-crater point locations. These can be selected as hypothetical exploration stops.',limit:'Points are not verified crater centroids, ranked science priorities, route-accessible or safety-qualified destinations. SIM 3464 reports 100–200 m random registration offsets.'},
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
  const [budgetInputs,setBudgetInputs]=useState({walkingSpeed:'',availableTime:'',scienceStop:'',reserve:''});
  const [budget,setBudget]=useState(null);
  const [budgetStatus,setBudgetStatus]=useState('idle');
  const [budgetError,setBudgetError]=useState('');
  const [mode,setMode]=useState('inspect');
  const [result,setResult]=useState(null);
  const [status,setStatus]=useState('idle');
  const [error,setError]=useState('');
  const [api,setApi]=useState({status:'connecting',message:'Checking local routing serviceâ€¦'});
  const [activeRoute,setActiveRoute]=useState('distance');
  const controller=useRef(null);
  const budgetController=useRef(null);
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
    budgetController.current?.abort();
    setResult(null); setStatus('idle'); setError('');
    setBudget(null);setBudgetStatus('idle');setBudgetError('');
  }
  function change(patch) {invalidate(); setInputs(old=>({...old,...patch}));}
  function changeBudget(patch) {budgetController.current?.abort();setBudgetInputs(old=>({...old,...patch}));setBudget(null);setBudgetStatus('idle');setBudgetError('');}
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
  function selectScienceStop(feature) {
    if (!data || feature?.geometry?.type!=='Point') return;
    const [lon,lat]=projectionFunctions(data.region.crs).inverse(feature.geometry.coordinates);
    change({endLon:lon.toFixed(9),endLat:lat.toFixed(9)});
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
  async function calculateBudget() {
    budgetController.current?.abort();setBudget(null);setBudgetError('');
    const version=generation.current;
    try{
      if(api.status!=='ready')throw new Error(api.message);
      if(result?.status!=='ok')throw new Error('Compare routes first. A round-trip budget requires connected outbound and return paths.');
      const required=['walkingSpeed','availableTime','scienceStop','reserve'];
      if(required.some(key=>budgetInputs[key].trim()===''))throw new Error('Enter every mission time assumption, including stop and reserve minutes.');
      const values=Object.fromEntries(required.map(key=>[key,Number(budgetInputs[key])]));
      if(!Object.values(values).every(Number.isFinite)||values.walkingSpeed<=0||values.walkingSpeed>20||values.availableTime<=0||values.availableTime>10080||values.scienceStop<0||values.scienceStop>10080||values.reserve<0||values.reserve>10080)throw new Error('Use a walking speed greater than 0 and at most 20 km/h; available time over 0; stop and reserve minutes 0 or greater.');
      const start=endpointValues(inputs,'start'),end=endpointValues(inputs,'end');
      budgetController.current=new AbortController();setBudgetStatus('loading');
      const response=await fetch('/api/mission-budget',{method:'POST',headers:{'Content-Type':'application/json'},signal:AbortSignal.any([budgetController.current.signal,AbortSignal.timeout(30000)]),
        body:JSON.stringify({start_lonlat:start,end_lonlat:end,terrain_weight:Number(inputs.weight),max_cell_slope_deg:inputs.limit.trim()===''?null:Number(inputs.limit),
          primary_objective:inputs.objective,region_manifest_sha256:data.manifestHash,region_id:data.regionId,
          walking_speed_kmh:values.walkingSpeed,available_time_min:values.availableTime,science_stop_min:values.scienceStop,reserve_min:values.reserve})});
      const body=await apiJson(response);
      if(!response.ok)throw new Error(body.message||'Mission budget request failed.');
      if(body.region_manifest_sha256!==data.manifestHash)throw new Error('Budget calculation used a different terrain dataset. Reload the verified map.');
      if(version===generation.current){setBudget(body);setBudgetStatus(body.status);}
    }catch(error){if(error.name!=='AbortError'&&version===generation.current){setBudgetError(error.message||'Mission budget unavailable.');setBudgetStatus('error');}}
  }
  const markers=[];
  if (data) for (const [prefix,label] of [['start','A'],['end','B']]) {
    try {
      const ll=endpointValues(inputs,prefix);
      const sample=sampleAt(projectionFunctions(data.region.crs).forward(ll),data.region,data.grids);
      if (sample.status==='valid' && sample.slope!==null) markers.push({label,center:sample.center});
    } catch { /* Unset/invalid inputs have no fabricated map marker. */ }
  }
  return {inputs,change,mode,setMode,pick,result,status,error,api,connect,compare,verificationPair,selectScienceStop,markers,activeRoute,setActiveRoute,budgetInputs,changeBudget,budget,budgetStatus,budgetError,calculateBudget,regionId:data?.regionId||'jezero-m1',
    clear:()=>{change({startLon:'',startLat:'',endLon:'',endLat:''});setMode('inspect');}};
}

export function MissionPlanner({mission,scienceStops=[],data}) {
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
      {scienceStops.length>0&&<><label className="form-label">USGS mapped science stop<select aria-label="USGS mapped science stop" defaultValue="" onChange={event=>{const stop=scienceStops.find(feature=>feature.id===event.target.value);if(stop)mission.selectScienceStop(stop);}}><option value="">Choose a mapped point…</option>{scienceStops.map(feature=><option key={feature.id} value={feature.id}>{feature.properties.display_name}</option>)}</select></label><p className="science-stop-note">SIM 3464 mapped small-crater points · 1:75,000 · 100–200 m registration uncertainty. Selecting one fills destination B; it does not indicate route safety.</p></>}
      <label className="form-label">Exploration objective<select aria-label="Exploration objective" value={inputs.objective} onChange={e=>change({objective:e.target.value})}><option value="distance">Distance priority</option><option value="terrain">Terrain priority</option></select></label>
      <details className="route-assumptions"><summary>Terrain assumptions</summary><label className="form-label">Grade penalty weight<input aria-label="Grade penalty weight" type="number" min="0" max="1000000" step="any" value={inputs.weight} onChange={e=>change({weight:e.target.value})}/></label><label className="form-label">Optional cell-slope limit (Â°)<input aria-label="Cell-slope limit" type="number" min="0" max="90" step="any" placeholder="No exclusion" value={inputs.limit} onChange={e=>change({limit:e.target.value})}/></label><p>Assumptions, not safety thresholds. Local cell-gradient limits do not cap segment slope. Weight is a heuristic, not a physiological model.</p></details>
      <button className="compare-button" type="submit" disabled={mission.api.status!=='ready'||mission.status==='loading'}>{mission.status==='loading'?'Calculating on verified terrain...':'Compare routes'}</button>
      <fieldset className="mission-budget-controls">
        <legend>Round-trip time budget / M6</legend>
        <label>Assumed walking speed (km/h)<input aria-label="Assumed walking speed km per hour" type="number" min="0.01" max="20" step="any" value={mission.budgetInputs.walkingSpeed} onChange={e=>mission.changeBudget({walkingSpeed:e.target.value})}/></label>
        <label>Available mission time (min)<input aria-label="Available mission time minutes" type="number" min="0.1" max="10080" step="any" value={mission.budgetInputs.availableTime} onChange={e=>mission.changeBudget({availableTime:e.target.value})}/></label>
        <label>Science stop duration (min)<input aria-label="Science stop duration minutes" type="number" min="0" max="10080" step="any" value={mission.budgetInputs.scienceStop} onChange={e=>mission.changeBudget({scienceStop:e.target.value})}/></label>
        <label>Reserve time (min)<input aria-label="Reserve time minutes" type="number" min="0" max="10080" step="any" value={mission.budgetInputs.reserve} onChange={e=>mission.changeBudget({reserve:e.target.value})}/></label>
        <p>All four are user assumptions. Constant walking speed ignores grade, terrain difficulty, fatigue and stops beyond the entered science duration.</p>
        <button type="button" className="budget-button" disabled={mission.status!=='ok'||mission.budgetStatus==='loading'} onClick={mission.calculateBudget}>{mission.budgetStatus==='loading'?'Calculating outbound and return...':'Estimate round-trip time'}</button>
        {mission.budgetError&&<p role="alert" className="mission-error">{mission.budgetError}</p>}
      </fieldset>
      <div className="planner-actions"><button type="button" onClick={mission.verificationPair}>Load verification pair</button><button type="button" onClick={mission.clear}>Clear</button></div>
      <p className="verification-note">Verification locations are test selections, not designated science sites.</p>
    </form>
    <div className={`api-state ${mission.api.status}`} role="status">{mission.api.message}{mission.api.status==='unavailable'&&<button onClick={mission.connect}>Reconnect routing</button>}</div>
    {mission.error&&<p role="alert" className="mission-error">{mission.error}</p>}
    {data&&scienceStops.length>0&&<CandidateRecommendations mission={mission} scienceStops={scienceStops} data={data}/>}
  </section>;
}

function CandidateRecommendations({mission,scienceStops,data}){
  const [maxSlope,setMaxSlope]=useState('');
  const [maxDistance,setMaxDistance]=useState('');
  const [candidates,setCandidates]=useState(null);
  const [error,setError]=useState('');
  function evaluate(){
    setError('');
    try{
      if(maxSlope.trim()===''||maxDistance.trim()==='')throw new Error('Enter both terrain-screen criteria before ranking candidates.');
      const start=endpointValues(mission.inputs,'start');
      setCandidates(rankScienceStops(scienceStops,data,start,Number(maxSlope),Number(maxDistance)));
    }catch(error){setCandidates(null);setError(error.message);}
  }
  return <section className="candidate-panel">
    <div className="section-heading"><h2>Terrain-screened stop candidates</h2><span>M6</span></div>
    <p>Filters source-mapped SIM 3464 points using your maximum buffered slope and straight-line range, then orders matches by Mars surface distance.</p>
    <label>Maximum slope across the 200 m position-uncertainty buffer (degrees)<input aria-label="Candidate maximum buffered slope" type="number" min="0" max="90" step="any" value={maxSlope} onChange={e=>{setMaxSlope(e.target.value);setCandidates(null);}}/></label>
    <label>Maximum straight-line range from start (km)<input aria-label="Candidate maximum distance km" type="number" min="0.01" max="1000" step="any" value={maxDistance} onChange={e=>{setMaxDistance(e.target.value);setCandidates(null);}}/></label>
    <button type="button" className="budget-button" onClick={evaluate}>Filter mapped stops</button>
    {error&&<p role="alert" className="mission-error">{error}</p>}
    {candidates&&<>{candidates.length===0?<p role="status">No mapped points meet these inputs and complete terrain-coverage requirements.</p>:<ol className="candidate-results">{candidates.map((candidate,index)=><li key={candidate.feature.id}><b>{index+1}. {candidate.feature.properties.display_name}</b><span>{(candidate.surface_distance_m/1000).toFixed(2)} km straight-line · {candidate.maximum_slope_within_uncertainty_buffer_deg.toFixed(2)}° maximum local slope across {candidate.buffer_cells} valid cells within 200 m</span><button type="button" onClick={()=>mission.selectScienceStop(candidate.feature)}>Use as destination B</button></li>)}</ol>}</>}
    <p className="candidate-limit">Derived terrain screen only; not a continuous path/access check, hazard assessment, science-value ranking or safety recommendation. Compare routes before planning travel. SIM 3464 source position uncertainty is 100–200 m.</p>
  </section>;
}

export function ContextLayers({group,enabled,onToggle,geologyAvailable=false,geologyError='',geologyMeta,crismAvailable=false,crismError='',crismMeta,scienceStopsAvailable=false,scienceStopsError='',scienceStopsMeta,regionId='jezero-m1'}) {
  return <section className="context-layers"><div className="section-heading"><h2>{group} intelligence</h2><span>{group==='Environmental'?'M4':'M5'}</span></div>
    {CATALOG.filter(item=>item.group===group).map(item=>{
      const geo=item.id==='geology',crism=item.id==='minerals',stops=item.id==='science-stops';
      const available=geo?geologyAvailable:crism?crismAvailable:stops?scienceStopsAvailable:false;
      const error=geo?geologyError:crism?crismError:stops?scienceStopsError:'';
      const panelOnly=!geo&&!crism&&!stops;
      const coverage=geo?`${geologyMeta?.region_intersecting_feature_count??geologyMeta?.pilot_intersecting_feature_count??0} intersecting polygons, 100-200 m registration uncertainty`:crism?`${((crismMeta?.valid_fraction??0)*100).toFixed(1)}% valid cells`:`${scienceStopsMeta?.intersecting_feature_count??0} mapped small-crater points`;
      const status=available?(geo?`VERIFIED GIS / ${regionId==='expanded-7p5km'?'7.5 KM':'5 KM'} / ${coverage}`:crism?`VERIFIED CRISM / ${coverage}`:`VERIFIED SIM 3464 / ${regionId==='expanded-7p5km'?'7.5 KM':'5 KM'} / ${coverage}`):error?'SOURCE DATA UNAVAILABLE':crism?'PDS MTRDR / LOAD ON ENABLE':geo?'USGS GIS / LOAD ON ENABLE':stops?'USGS GIS / CHECKING SOURCE':'PANEL ONLY / NO MAP LAYER';
      return <label className="context-layer" key={item.id}><input type="checkbox" aria-label={`${item.label} context`} checked={enabled.includes(item.id)} onChange={()=>onToggle(item.id)}/><span><b>{item.label}</b><small>{status}</small></span><span className="pending-dot" title={available?'Verified source-derived map overlay':panelOnly?'Context panel only; no validated map overlay':'Source not loaded'}>{available?'ON':panelOnly?'PANEL':'--'}</span></label>;
    })}
    <p className="context-help">{group==='Scientific'?'Geology draws published map units; CRISM draws the measured D2300 index within its footprint. Mapped science stops are user-selected source points, not ranked or safety-qualified destinations.':'These choices show source/context details in the right panel only. Temperature, dust and radiation map layers are unavailable; Surface thermal response above is the separate verified map overlay.'}</p>
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

export function MissionInsights({mission,contexts,geologyMeta,crismMeta,scienceStopsMeta}) {
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
    {mission.budget?.status==='no_path'&&<section className="budget-results" role="status"><h3>Round-trip budget unavailable</h3><p>{mission.budget.message}</p></section>}
    {mission.budget?.status==='ok'&&<section className="budget-results"><h3>Round-trip time estimate <span>DERIVED FROM USER ASSUMPTIONS</span></h3><p>Outbound and return paths were computed separately. Arithmetic only; not an EVA duration or safety guarantee.</p>{Object.entries(mission.budget.budgets).map(([objective,budget])=><article className={`budget-card ${budget.within_time_budget?'within':'over'}`} key={objective}><b>{objective==='distance'?'Distance objective':'Terrain objective'}</b><dl><div><dt>Outbound / return</dt><dd>{budget.outbound_distance_m.toFixed(0)} / {budget.return_distance_m.toFixed(0)} m</dd></div><div><dt>Round-trip walking</dt><dd>{budget.walking_time_min.toFixed(1)} min</dd></div><div><dt>Stop + reserve</dt><dd>{budget.science_stop_min.toFixed(0)} + {budget.reserve_min.toFixed(0)} min</dd></div><div><dt>Required / available</dt><dd>{budget.required_total_min.toFixed(1)} / {budget.available_time_min.toFixed(1)} min</dd></div><div><dt>Arithmetic margin</dt><dd>{budget.remaining_margin_min.toFixed(1)} min</dd></div></dl><strong>{budget.within_time_budget?'Within entered time':'Exceeds entered time'}</strong></article>)}</section>}
    <div className="context-heading"><div className="eyebrow">EVIDENCE & AVAILABILITY</div><p>Observation, derived result and planned capability remain separate.</p></div>
    {!contexts.length&&<p className="context-empty">Enable environmental or scientific context in the left sidebar to inspect candidate sources and limits.</p>}
    {contexts.map(id=>{const item=CATALOG.find(row=>row.id===id);const description=id==='geology'?`${geologyMeta?.region_intersecting_feature_count??geologyMeta?.pilot_intersecting_feature_count??'Source-derived'} published SIM 3464 unit polygons intersect this selected region; source registration uncertainty remains 100-200 m.`:id==='minerals'?`The verified CRISM scene intersects ${(((crismMeta?.region_area_intersection_fraction??crismMeta?.pilot_area_intersection_fraction??crismMeta?.valid_fraction??0)*100)).toFixed(1)}% of this region by area; ${((crismMeta?.valid_fraction??0)*100).toFixed(1)}% of target grid cells have valid values. D2300 is a spectral-shape parameter, not a mineral identification.`:id==='science-stops'?`${scienceStopsMeta?.intersecting_feature_count??0} SIM 3464 mapped small-crater point locations intersect this region. These are optional user-selected stops, not ranked science priorities.`:item.description;return <section className="context-card" key={id}><span className="type-label">{item.group.toUpperCase()} / {item.stage}{item.group==='Scientific'?' SOURCE DATA':' ARCHIVE CONTEXT'}</span><h3>{item.label}</h3>{item.group==='Environmental'?<><EnvironmentPanel id={id}/>{id==='temperature'&&<a href={item.url} target="_blank" rel="noreferrer">{item.source}</a>}<p className="unavailable-label">Spatial layer unavailable / historical context only</p></>:<><span className="evidence-kind">{item.kind}</span><p>{description}</p><p className="context-limit">{item.limit}</p><a href={item.url} target="_blank" rel="noreferrer">{item.source}</a><p className="unavailable-label">{id==='geology'?'Map overlay uses source unit polygons; it is not a mineral or water resource inventory.':id==='minerals'?'Map overlay shows a measured spectral parameter, not identified mineral deposits.':id==='science-stops'?'Source feature markers are not assessed for terrain access or mission suitability.':'Spatial layer unavailable / no measurements shown'}</p></>}</section>;})}
    <div className="mission-future"><span className="type-label">M6 / METHOD LIMITS</span><p>Time estimates use constant user-entered speed and independently routed return paths. Terrain-screened mapped stops are candidates only; neither result is an operational assessment or safety certification.</p></div>
  </aside>;
}
