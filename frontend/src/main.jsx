import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import Map from 'ol/Map.js';
import View from 'ol/View.js';
import Projection from 'ol/proj/Projection.js';
import {addProjection, addCoordinateTransforms} from 'ol/proj.js';
import ImageLayer from 'ol/layer/Image.js';
import ImageStatic from 'ol/source/ImageStatic.js';
import VectorLayer from 'ol/layer/Vector.js';
import VectorSource from 'ol/source/Vector.js';
import Feature from 'ol/Feature.js';
import Point from 'ol/geom/Point.js';
import Polygon from 'ol/geom/Polygon.js';
import LineString from 'ol/geom/LineString.js';
import {Style, Stroke, Fill, Circle as CircleStyle, Text} from 'ol/style.js';
import {defaults as defaultControls} from 'ol/control/defaults.js';
import {projectionFunctions, sampleAt} from './coordinates.js';
import {useMission, MissionPlanner, MissionInsights, ContextLayers} from './MissionControl.jsx';
import {loadThermal,sampleThermal} from './environmentMap.js';
import 'ol/ol.css';
import './style.css';
import './mission.css';

async function response(path) {
  const result = await fetch(`/data/${path}`);
  if (!result.ok) throw new Error(`Could not load ${path}`);
  return result;
}

async function loadRegion() {
  const manifestBytes = await (await response('manifest.json')).arrayBuffer();
  const region = JSON.parse(new TextDecoder().decode(manifestBytes));
  const digest = await crypto.subtle.digest('SHA-256', manifestBytes);
  const manifestHash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2,'0')).join('');
  if (region.schema_version !== 1 || region.width !== 250 || region.height !== 250 || region.crs.radius_m !== 3396190) {
    throw new Error('Unsupported region manifest');
  }
  const files = ['elevation.f32', 'slope.f32', 'valid.u8', 'slope-valid.u8'];
  const buffers = await Promise.all(files.map(async name => (await response(name)).arrayBuffer()));
  const n = region.width * region.height;
  if (buffers.some((buffer, i) => buffer.byteLength !== n * (i < 2 ? 4 : 1))) throw new Error('Incomplete terrain grids');
  const hashes=await Promise.all(buffers.map(async buffer=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),byte=>byte.toString(16).padStart(2,'0')).join('')));
  if (hashes.some((hash,i)=>hash!==region.outputs[files[i]].sha256)) throw new Error('Terrain grids differ from their scientific manifest');
  // Explicit DataView decoding works on either browser endianness.
  const floats = buffer => {
    const view = new DataView(buffer);
    return Float32Array.from({length: n}, (_, i) => view.getFloat32(i * 4, true));
  };
  return {region, manifestHash, grids: {elevation: floats(buffers[0]), slope: floats(buffers[1]), valid: new Uint8Array(buffers[2]), slopeValid: new Uint8Array(buffers[3])}};
}

function TerrainMap({data, thermal, thermalOn, imageryOn, elevationOn, slopeOn, opacity, referencesOn, onSample, onImageError, mapRef, markers, routeResult, activeRoute, routeVisibility}) {
  const target = useRef(null);
  const layers = useRef(null);
  const latestSample = useRef(onSample);
  latestSample.current = onSample;
  useEffect(() => {
    const {region, grids} = data;
    const functions = projectionFunctions(region.crs);
    const mars = new Projection({code: 'MARS:JEZERO', units: 'm', extent: region.imagery_bounds_m,
      getPointResolution: (resolution, [, y]) => resolution * (1 + Math.cos(y / region.crs.radius_m) / Math.cos(region.crs.standard_parallel_deg * Math.PI / 180)) / 2});
    const geographic = new Projection({code: 'MARS:PLANETOCENTRIC', units: 'degrees', metersPerUnit: region.crs.radius_m * Math.PI / 180,
      extent: [-180, -90, 180, 90], axisOrientation: 'enu'});
    addProjection(mars);
    addProjection(geographic);
    addCoordinateTransforms(geographic, mars, functions.forward, functions.inverse);
    const imagerySource = new ImageStatic({url: '/data/imagery.png', projection: mars, imageExtent: region.imagery_bounds_m,
      interpolate: false, attributions: 'Imagery: NASA/JPL Mars Trek · USGS · MRO CTX | DEM: Fred Calef / USGS / PDS (2021)'});
    const slopeSource = new ImageStatic({url: '/data/slope.png', projection: mars, imageExtent: region.bounds_m, interpolate: false});
    imagerySource.on('imageloaderror', () => onImageError('Imagery unavailable. Rebuild local data and reload.'));
    slopeSource.on('imageloaderror', () => onImageError('Slope image unavailable. Numeric terrain remains available.'));
    const imagery = new ImageLayer({source: imagerySource});
    const elevationCanvas = document.createElement('canvas');
    elevationCanvas.width = region.width; elevationCanvas.height = region.height;
    const context = elevationCanvas.getContext('2d');
    const pixels = context.createImageData(region.width,region.height);
    const [low,high] = region.statistics.elevation_range_m;
    for (let i=0;i<grids.elevation.length;i++) if (grids.valid[i] && Number.isFinite(grids.elevation[i])) {
      const value=(grids.elevation[i]-low)/Math.max(high-low,1);
      pixels.data.set([45+value*170,65+value*95,120-value*45,220],i*4);
    }
    context.putImageData(pixels,0,0);
    const elevation = new ImageLayer({opacity:.65,source:new ImageStatic({url:elevationCanvas.toDataURL(),projection:mars,imageExtent:region.bounds_m,interpolate:false})});
    const slope = new ImageLayer({source: slopeSource, opacity});
    const thermalLayer = new ImageLayer({opacity,visible:false,extent:region.bounds_m});
    const [w, s, e, n] = region.bounds_m;
    const footprint = new Feature(new Polygon([[[w, s], [e, s], [e, n], [w, n], [w, s]]]));
    const boundary = new VectorLayer({source: new VectorSource({features: [footprint]}), style: new Style({stroke: new Stroke({color: '#f7e5bd', width: 1.5, lineDash: [7, 6]})})});
    const references = new VectorLayer({source: new VectorSource({features: region.control_points.map((point, i) => {
      const feature = new Feature(new Point([point.x_m, point.y_m]));
      feature.setStyle(new Style({image: new CircleStyle({radius: 4, fill: new Fill({color: '#141d20'}), stroke: new Stroke({color: '#f7e5bd', width: 1.5})}),
        text: new Text({text: String(i+1), offsetY: -14, fill: new Fill({color: '#fff5e2'}), stroke: new Stroke({color: '#11191c', width: 4}), font: 'bold 12px monospace'})}));
      return feature;
    })})});
    const selection = new VectorSource();
    const selected = new VectorLayer({source: selection, style: new Style({image: new CircleStyle({radius: 8, fill: new Fill({color: '#11191caa'}), stroke: new Stroke({color: '#ffffff', width: 2})})})});
    const routeSource = new VectorSource();
    const endpointSource = new VectorSource();
    const routeLayer = new VectorLayer({source:routeSource});
    const endpointLayer = new VectorLayer({source:endpointSource});
    const map = new Map({target: target.current, layers: [imagery, elevation, slope, thermalLayer, boundary, references, routeLayer, endpointLayer, selected],
      controls: defaultControls({rotate: false, attributionOptions: {collapsible: false}}),
      view: new View({projection: mars, extent: region.imagery_bounds_m, constrainOnlyCenter: true, minResolution: 2, maxResolution: 80})});
    const inspect = coordinate => {
      const sample = sampleAt(coordinate, region, grids);
      selection.clear();
      if (sample.status === 'valid') selection.addFeature(new Feature(new Point(sample.center)));
      latestSample.current(sample);
    };
    map.on('singleclick', event => inspect(event.coordinate));
    const fit = () => map.getView().fit(region.bounds_m, {padding: [85, 45, 60, 45], duration: 0});
    fit();
    const observer = new ResizeObserver(() => map.updateSize());
    observer.observe(target.current);
    mapRef.current = {fit, inspect, sampleCenter: () => inspect(map.getView().getCenter()),
      inspectReference: i => inspect([region.control_points[i].x_m, region.control_points[i].y_m])};
    layers.current = {imagery, elevation, slope, thermalLayer, references, routeSource, endpointSource, functions};
    return () => {observer.disconnect(); mapRef.current = null; map.setTarget(undefined);};
  }, [data]);
  useEffect(() => {layers.current?.imagery.setVisible(imageryOn);}, [imageryOn, data]);
  useEffect(() => {layers.current?.elevation.setVisible(elevationOn);}, [elevationOn, data]);
  useEffect(() => {layers.current?.slope.setVisible(slopeOn);}, [slopeOn, data]);
  useEffect(() => {layers.current?.slope.setOpacity(opacity);}, [opacity, data]);
  useEffect(() => {
    if (!layers.current) return;
    const layer=layers.current.thermalLayer;
    layer.setSource(thermal?new ImageStatic({url:thermal.imageUrl,projection:layers.current.imagery.getSource().getProjection(),imageExtent:thermal.meta.bounds_map_m,interpolate:false,
      attributions:'Thermal inertia: Edwards & Buz (2021) · Odyssey THEMIS · CC BY 4.0'}):null);
    layer.setVisible(Boolean(thermal&&thermalOn));
  },[thermal,data]);
  useEffect(()=>{layers.current?.thermalLayer.setVisible(Boolean(thermal&&thermalOn));},[thermalOn,thermal,data]);
  useEffect(()=>{layers.current?.thermalLayer.setOpacity(opacity);},[opacity,data]);
  useEffect(() => {layers.current?.references.setVisible(referencesOn);}, [referencesOn, data]);
  useEffect(() => {
    if (!layers.current) return;
    const {endpointSource}=layers.current;
    endpointSource.clear();
    for (const marker of markers) {
      const feature=new Feature(new Point(marker.center));
      feature.setStyle(new Style({image:new CircleStyle({radius:12,fill:new Fill({color:'#152124'}),stroke:new Stroke({color:marker.label==='A'?'#67e0ef':'#ffb176',width:2})}),
        text:new Text({text:marker.label,font:'bold 12px Arial',fill:new Fill({color:'#fff7e6'})})}));
      endpointSource.addFeature(feature);
    }
  },[markers,data]);
  useEffect(() => {
    if (!layers.current) return;
    const {routeSource,functions}=layers.current;
    routeSource.clear();
    for (const route of routeResult?.routes??[]) {
      if (route.status!=='ok'||!route.geometry||!routeVisibility[route.objective]) continue;
      const geometry=route.geometry.type==='Point'?new Point(functions.forward(route.geometry.coordinates)):
        new LineString(route.geometry.coordinates.map(functions.forward));
      const color=route.objective==='distance'?'#67e0ef':'#ffb176';
      const focused=route.objective===activeRoute;
      const feature=new Feature(geometry);
      feature.setStyle([new Style({stroke:new Stroke({color:'#122023dd',width:focused?8:6})}),
        new Style({stroke:new Stroke({color,width:focused?4:2.5,lineDash:route.objective==='terrain'?[9,5]:undefined}),
          image:new CircleStyle({radius:6,fill:new Fill({color}),stroke:new Stroke({color:'#152124',width:2})})})]);
      routeSource.addFeature(feature);
    }
  },[routeResult,routeVisibility,activeRoute,data]);
  return <div ref={target} id="terrain-map" className="map" tabIndex="0" role="region" aria-label="Interactive Jezero terrain map. Arrow keys pan. Plus and minus zoom. Use Sample map center to inspect with the keyboard." />;
}

function Sample({sample,thermal,thermalOn}) {
  const thermalSample=sample?.status==='valid'&&thermal&&thermalOn?sampleThermal(sample.lonlat,thermal):null;
  return <section className="sample" aria-live="polite" aria-atomic="true" data-testid="sample-panel">
    <div className="eyebrow"><span className="small-cross">+</span> TERRAIN INSPECTOR</div>
    {!sample && <><h2>Choose a point.</h2><p>Click inside the dashed pilot boundary to inspect a native terrain cell.</p></>}
    {sample?.status === 'outside' && <><h2>No terrain coverage</h2><p>This point is outside the pilot DEM. Choose a point inside the dashed boundary.</p></>}
    {sample?.status === 'nodata' && <><h2>Missing elevation</h2><p>This cell is nodata. No terrain value is inferred.</p></>}
    {sample?.status === 'valid' && <>
      <div className="sample-coords" data-testid="sample-coordinates">{sample.lonlat[0].toFixed(6)}°E <span>/</span> {sample.lonlat[1].toFixed(6)}°N</div>
      <div className="sample-metrics">
        <div><span className="type-label">SOURCE DEM</span><strong data-testid="elevation">{sample.elevation.toFixed(2)}<small> m</small></strong><span>Elevation · MOLA localized</span></div>
        <div><span className="type-label derived">DERIVED</span><strong data-testid="slope">{sample.slope === null ? '—' : sample.slope.toFixed(2)}<small>°</small></strong><span>{sample.slope === null ? 'Slope neighbors missing' : 'Local terrain slope'}</span></div>
      </div>
      <div className="cell-readout">CROP ROW <b data-testid="row">{sample.row}</b> <span>COL <b data-testid="col">{sample.col}</b></span><span>20 M CELL</span></div>
      <p className="sample-note">Coordinates snap to the selected cell center. Sampling resolution does not establish obstacle size or travel safety.</p>
      {thermalSample&&<div className="thermal-readout"><span className="type-label">THEMIS · DERIVED THERMAL PROPERTY</span>{thermalSample.status==='valid'?<><strong data-testid="thermal-value">{thermalSample.value.toFixed(2)}</strong><span>J m⁻² K⁻¹ s⁻½ · native 100 m source pixel</span><p>Resistance to heating/cooling; not temperature. Sampled at the terrain sample centre.</p></>:<p>No valid thermal-inertia coverage here.</p>}</div>}
    </>}
  </section>;
}

function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [imageError, setImageError] = useState('');
  const [sample, setSample] = useState(null);
  const [imageryOn, setImageryOn] = useState(true);
  const [slopeOn, setSlopeOn] = useState(true);
  const [elevationOn, setElevationOn] = useState(false);
  const [referencesOn, setReferencesOn] = useState(false);
  const [opacity, setOpacity] = useState(.55);
  const [thermal,setThermal]=useState(null);
  const [thermalOn,setThermalOn]=useState(false);
  const [thermalError,setThermalError]=useState('');
  const mapRef = useRef(null);
  const mission = useMission(data);
  const [contexts,setContexts]=useState([]);
  const [routeVisibility,setRouteVisibility]=useState({distance:true,terrain:true});
  const toggleContext=id=>setContexts(old=>old.includes(id)?old.filter(value=>value!==id):[...old,id]);
  const handleSample=sample=>{setSample(sample);if(mission.mode!=='inspect')mission.pick(sample);};
  useEffect(() => {let active = true; loadRegion().then(result => {if (active) setData(result);}).catch(() => {if (active) setError('Terrain data could not be loaded. Run the preprocessing command in the README, then reload.');}); return () => {active = false;};}, []);
  useEffect(()=>{
    if (!data) return;
    let active=true,asset=null;
    loadThermal(data.manifestHash).then(result=>{asset=result;if(active)setThermal(result);else URL.revokeObjectURL(result.imageUrl);}).catch(error=>{if(active)setThermalError(error.message);});
    return ()=>{active=false;if(asset)URL.revokeObjectURL(asset.imageUrl);};
  },[data]);
  return <div className="app-shell">
    <header className="topbar">
      <a href="#main" className="brand" aria-label="MARSWALK home"><span className="brand-mark" aria-hidden="true">M<span>↗</span></span>MARSWALK<span className="prototype">PROTOTYPE</span></a>
      <div className="location"><span className="orbit-dot"/> MARS <span className="separator">/</span> JEZERO CRATER <span className="location-detail">WESTERN DELTA REGION</span></div>
      <span className="data-badge"><span/> {data ? 'LOCAL DATA READY' : error ? 'DATA UNAVAILABLE' : 'LOADING DATA'}</span>
    </header>
    <main id="main" className="workspace">
      <aside className="sidebar">
        <div className="sidebar-intro"><div className="eyebrow orange">JEZERO / MISSION CONTROL</div><h1>Explore<br/>Jezero.</h1><p>Terrain, scientific context and mission decisions, grounded in evidence.</p></div>
        <MissionPlanner mission={mission}/>
        <section className="region-card"><span className="type-label">PROPOSED PILOT EXTENT</span><div className="extent-number">5 × 5 <span>km</span><span className="corner-arrow">↗</span></div><p>Western Jezero · 20 m DEM grid<br/>A demo footprint, not an EVA limit.</p></section>
        <section className="layers-section" id="data-layers"><div className="section-heading"><h2>Map layers</h2><span>VERIFIED</span></div>
          <label className="layer-row"><span className="layer-icon">▧</span><span><b>CTX imagery</b><small>OBSERVATION · MRO / NASA TREK</small></span><input type="checkbox" aria-label="CTX imagery" checked={imageryOn} onChange={e => setImageryOn(e.target.checked)}/></label>
          <label className="layer-row"><span className="layer-icon">▥</span><span><b>Elevation tint</b><small>SOURCE DEM · METRES</small></span><input type="checkbox" aria-label="Elevation tint" checked={elevationOn} onChange={e=>{setElevationOn(e.target.checked);if(e.target.checked)setThermalOn(false);}}/></label>
          {elevationOn&&<p className="elevation-legend">Elevation tint: purple {data?.region.statistics.elevation_range_m[0].toFixed(0)} m → warm {data?.region.statistics.elevation_range_m[1].toFixed(0)} m.</p>}
          <label className="layer-row"><span className="layer-icon slope-icon">▨</span><span><b>Terrain slope</b><small>DERIVED · CTX ELEVATION</small></span><input type="checkbox" aria-label="Terrain slope" checked={slopeOn} onChange={e => {setSlopeOn(e.target.checked);if(e.target.checked)setThermalOn(false);}}/></label>
          <label className="opacity-control">Overlay opacity <span>{Math.round(opacity*100)}%</span><input aria-label="Overlay opacity" type="range" min="0" max="100" value={Math.round(opacity*100)} disabled={!slopeOn&&!thermalOn} onChange={e => setOpacity(Number(e.target.value)/100)}/></label>
          <label className="references-toggle"><input type="checkbox" checked={referencesOn} onChange={e => setReferencesOn(e.target.checked)}/> Show verification samples</label>
          {referencesOn && data && <div className="reference-buttons">{data.region.control_points.map((_, i) => <button key={i} onClick={() => mapRef.current?.inspectReference(i)} aria-label={`Inspect verification sample ${i+1}`}>{i+1}</button>)}</div>}
        </section>
        <section className="environment-map-controls"><div className="section-heading"><h2>Environmental map</h2><span>SPATIAL DATA</span></div>
          <label className="layer-row"><span className="layer-icon">◧</span><span><b>Surface thermal response</b><small>THEMIS · THERMAL INERTIA · 100 M</small></span><input type="checkbox" aria-label="Surface thermal response map" disabled={!thermal} checked={thermalOn} onChange={event=>{setThermalOn(event.target.checked);if(event.target.checked){setSlopeOn(false);setElevationOn(false);}}}/></label>
          {thermalError?<p role="status" className="context-limit">{thermalError}</p>:!thermal?<p>Checking thermal-map data…</p>:<details><summary>What these colours mean</summary><p>Lower thermal inertia: faster heating/cooling. Higher: stronger resistance to temperature changes. Colours do not show hot/cold temperature or travel safety.</p><p>{thermal.meta.source_pixel_size_m} m source pixels · {thermal.meta.unit}. Published {thermal.meta.published}.</p><p>{thermal.meta.observation_time}</p><p>{thermal.meta.limits}</p><a href={thermal.meta.source_url} target="_blank" rel="noreferrer">Edwards & Buz · source and methods ↗</a></details>}
          <p>Temperature, storm and radiation colour maps remain unavailable: existing rover readings/reports do not establish spatial distributions. Historical context panels below are separate.</p>
        </section>
        <ContextLayers group="Environmental" enabled={contexts} onToggle={toggleContext}/>
        <ContextLayers group="Scientific" enabled={contexts} onToggle={toggleContext}/>
        <section className="route-layers"><div className="section-heading"><h2>Route layers</h2><span>DERIVED</span></div>{['distance','terrain'].map(objective=><label className={`route-toggle ${objective}`} key={objective}><input type="checkbox" aria-label={`${objective} route layer`} checked={routeVisibility[objective]} onChange={e=>setRouteVisibility(old=>({...old,[objective]:e.target.checked}))}/><i/>{objective==='distance'?'Distance route':'Terrain route'}</label>)}</section>
          <section className="method-note"><div className="eyebrow">HOW TO READ THIS MAP</div><p>Color shows terrain gradient, from gentle to steep. It does not classify safe travel.</p><p className="muted">Environmental context contains dated rover observations and regional reports. No current regional weather, measured Jezero radiation or resource inventory.</p></section>
        <details className="sources"><summary>Sources & processing <span>↗</span></summary><div>
          <p><b>Elevation observation:</b> Fred Calef / USGS / PDS, CTX Science Investigation DEM (2021), version 1.0; native 20 m grid. MRO mission. Public domain; cite authors.</p>
          <p><a href="https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic" target="_blank" rel="noreferrer">USGS DEM catalog ↗</a> · <a href="https://doi.org/10.1126/science.abl4051" target="_blank" rel="noreferrer">Mangold et al. 2021 ↗</a></p>
          <p><b>Imagery observation:</b> NASA/JPL Mars Trek / USGS, controlled Jezero CTX mosaic, cached matrix 11 (~20.35 m/pixel at equator; source imagery nominal ~6 m). <a href="https://doi.org/10.5066/P906QQT8" target="_blank" rel="noreferrer">Fergason et al. 2020 ↗</a></p>
          {data && <><p className="product-id">{data.region.sources.dem.product_id}<br/>{data.region.sources.imagery.layer}</p><p><b>Derived slope:</b> central elevation differences with actual Mars horizontal neighbor distances. Missing neighbors stay masked; no filling or terrain resampling.</p><p><b>Projection:</b> Mars sphere R=3,396,190 m, equirectangular standard parallel 18.4663°. Positive-east longitude; planetocentric latitude. Explicit projected metres, never Earth Web Mercator.</p><p><b>Limits:</b> no explicit vertical CRS in source. Catalog radius conflicts with raster; raster CRS used. Imagery license absent from service response; attribution retained, source terms pending submission review. Both layers use MRO.</p><a href="/data/manifest.json" target="_blank" rel="noreferrer">Full manifest, checksums & method ↗</a></>}
        </div></details>
        <div className="sidebar-footer">NASA SPACE APPS 2026 <span>M3 / MISSION CONTROL</span></div>
      </aside>
      <section className="map-stage" aria-label="Terrain exploration workspace">
        {data && <TerrainMap data={data} thermal={thermal} thermalOn={thermalOn} imageryOn={imageryOn} elevationOn={elevationOn} slopeOn={slopeOn} opacity={opacity} referencesOn={referencesOn} onSample={handleSample} onImageError={setImageError} mapRef={mapRef} markers={mission.markers} routeResult={mission.result} activeRoute={mission.activeRoute} routeVisibility={routeVisibility}/>}
        {!data && <div className="loading" role={error ? 'alert' : 'status'}><span className="eyebrow">MARSWALK / DATA</span><h2>{error ? 'Terrain unavailable' : 'Opening Jezero…'}</h2><p>{error || 'Loading verified local imagery and native elevation cells.'}</p>{error && <button onClick={() => window.location.reload()}>Reload data</button>}</div>}
        {imageError && <div className="image-error" role="alert">{imageError}</div>}
        {data && <>
          <div className="map-toolbar"><span className="map-label"><span className="orange-square"/> JEZERO / PILOT 01</span><div><button onClick={() => mapRef.current?.sampleCenter()}>⌖ <span>Sample map center</span></button><button onClick={() => mapRef.current?.fit()}>↗ <span>Fit pilot</span></button></div></div>
          <div className="north" aria-label="North is up">N<span>↑</span></div>
          {mission.mode!=='inspect'&&<div className="pick-instruction" role="status">Select {mission.mode==='start'?'starting location A':'destination B'} on the map, or use Sample map center.<button onClick={()=>mission.setMode('inspect')}>Cancel selection</button></div>}
          {mission.result?.status==='ok'&&<div className="map-route-status" data-testid="map-route-status">{mission.result.routes.filter(route=>routeVisibility[route.objective]).length} calculated route layers displayed · A start / B destination</div>}
          <div className="map-bottom"><div className="legend"><div className="eyebrow">{thermalOn?'THERMAL INERTIA · NOT TEMPERATURE':slopeOn ? 'DERIVED SLOPE / DEGREES' : 'SLOPE OVERLAY HIDDEN'}</div><div className="legend-colors">{(thermalOn?thermal.meta.legend:data.region.legend).colors.map((c, i) => <div key={i}><span style={{backgroundColor:`rgb(${c.join(',')})`}}/><small>{(thermalOn?thermal.meta.legend:data.region.legend).labels[i]}</small></div>)}</div><p>{thermalOn?'J m⁻² K⁻¹ s⁻½ · native 100 m source · derived mosaic':'Dashed outline: numeric terrain coverage'}</p></div><Sample sample={sample} thermal={thermal} thermalOn={thermalOn}/></div>
          <div className="map-caption"><span>POSITIVE-EAST LONGITUDE · PLANETOCENTRIC LATITUDE</span><span>PLANNING DEMONSTRATION · NO SAFETY CERTIFICATION</span></div>
        </>}
      </section>
      <MissionInsights mission={mission} contexts={contexts}/>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
