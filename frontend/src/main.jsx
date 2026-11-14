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
import GeoJSON from 'ol/format/GeoJSON.js';
import Point from 'ol/geom/Point.js';
import Polygon from 'ol/geom/Polygon.js';
import LineString from 'ol/geom/LineString.js';
import {Style, Stroke, Fill, Circle as CircleStyle, Text} from 'ol/style.js';
import {defaults as defaultControls} from 'ol/control/defaults.js';
import ScaleLine from 'ol/control/ScaleLine.js';
import {projectionFunctions, sampleAt} from './coordinates.js';
import {loadCrism,sampleCrism} from './crismMap.js';
import {useMission, MissionPlanner, MissionInsights, ContextLayers} from './MissionControl.jsx';
import {loadThermal,sampleThermal} from './environmentMap.js';
import 'ol/ol.css';
import './style.css';
import './mission.css';

const GEOLOGY_COLORS = ['#e7b673', '#9cc9b4', '#9ab8da', '#d99b83', '#bfaddb', '#cbd17c', '#70c5c5', '#e2a1b8', '#afc5dd', '#d4a85d', '#8ec69e', '#cf998c', '#8dbbc0', '#c1a9d9'];

async function response(path, prefix='') {
  const result = await fetch(`/data/${prefix}${path}`);
  if (!result.ok) throw new Error(`Could not load ${path}`);
  return result;
}

async function loadRegion(regionId='jezero-m1') {
  const dataPrefix=regionId==='expanded-7p5km'?'expanded/':'';
  const manifestBytes = await (await response('manifest.json',dataPrefix)).arrayBuffer();
  const region = JSON.parse(new TextDecoder().decode(manifestBytes));
  const digest = await crypto.subtle.digest('SHA-256', manifestBytes);
  const manifestHash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2,'0')).join('');
  if (region.schema_version !== 1 || region.width*region.height !== region.statistics.valid_elevation_cells || region.crs.radius_m !== 3396190) {
    throw new Error('Unsupported region manifest');
  }
  const files = ['elevation.f32', 'slope.f32', 'valid.u8', 'slope-valid.u8'];
  const buffers = await Promise.all(files.map(async name => (await response(name,dataPrefix)).arrayBuffer()));
  const n = region.width * region.height;
  if (buffers.some((buffer, i) => buffer.byteLength !== n * (i < 2 ? 4 : 1))) throw new Error('Incomplete terrain grids');
  const hashes=await Promise.all(buffers.map(async buffer=>Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',buffer)),byte=>byte.toString(16).padStart(2,'0')).join('')));
  if (hashes.some((hash,i)=>hash!==region.outputs[files[i]].sha256)) throw new Error('Terrain grids differ from their scientific manifest');
  // Explicit DataView decoding works on either browser endianness.
  const floats = buffer => {
    const view = new DataView(buffer);
    return Float32Array.from({length: n}, (_, i) => view.getFloat32(i * 4, true));
  };
  const sourceManifestHash=region.expansion?.source_m1_manifest_sha256||manifestHash;
  let imagery={url:`/data/${dataPrefix}imagery.png`,bounds:region.imagery_bounds_m,detail:false,error:''};
  const detailManifestResponse=await fetch('/data/imagery-detail-manifest.json');
  if(detailManifestResponse.ok){
    try{
      const meta=await detailManifestResponse.json();
      const image=await response('imagery-detail.png');
      const imageBytes=await image.arrayBuffer();
      const imageHash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',imageBytes)),byte=>byte.toString(16).padStart(2,'0')).join('');
      const sameBounds=meta.image_bounds_m?.length===4&&meta.image_bounds_m.every((value,index)=>Math.abs(value-region.imagery_bounds_m[index])<1e-6);
      if(meta.schema_version!==1||meta.status!=='source-derived'||meta.matrix_id!=='13'||meta.layer!=='JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0'||meta.region_manifest_sha256!==sourceManifestHash||!sameBounds||imageBytes.byteLength!==meta.output?.bytes||imageHash!==meta.output?.sha256)throw new Error('High-detail CTX basemap integrity/footprint validation failed.');
      imagery={url:'/data/imagery-detail.png',bounds:meta.image_bounds_m,detail:true,error:''};
    }catch(error){imagery.error=`High-detail CTX basemap rejected; using validated M1 imagery. ${error.message}`;}
  }
  return {region, manifestHash, sourceManifestHash, regionId, dataPrefix, imagery, grids: {elevation: floats(buffers[0]), slope: floats(buffers[1]), valid: new Uint8Array(buffers[2]), slopeValid: new Uint8Array(buffers[3])}};
}

function TerrainMap({data, thermal, thermalOn, crism, crismOn, geology, geologyOn, imageryOn, elevationOn, slopeOn, opacity, referencesOn, onSample, onGeologySample, onImageError, mapRef, markers, routeResult, activeRoute, routeVisibility}) {
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
    const imagerySource = new ImageStatic({url: data.imagery.url, projection: mars, imageExtent: data.imagery.bounds,
      interpolate: false, attributions: `${data.imagery.detail?'Detailed ':'Cached '}imagery: NASA/JPL Mars Trek · USGS · MRO CTX | DEM: Fred Calef / USGS / PDS (2021)`});
    const slopeSource = new ImageStatic({url: `/data/${data.dataPrefix}slope.png`, projection: mars, imageExtent: region.bounds_m, interpolate: false});
    imagerySource.on('imageloaderror', () => onImageError(`${data.imagery.detail?'High-detail CTX imagery':'Imagery'} unavailable. Rebuild local data and reload.`));
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
    const crismLayer = new ImageLayer({opacity,visible:false,extent:region.bounds_m});
    const geologySource = new VectorSource({attributions: 'Geology: Sun & Stack (2020), USGS SIM 3464'});
    const geologyLayer = new VectorLayer({source: geologySource, visible: false, extent: region.bounds_m,
      style: feature => {
        const color = GEOLOGY_COLORS[(Number(feature.get('style_index')) || 0) % GEOLOGY_COLORS.length];
        return new Style({fill: new Fill({color: `${color}38`}), stroke: new Stroke({color: `${color}d0`, width: 1.3})});
      }});
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
    const map = new Map({target: target.current, layers: [imagery, elevation, slope, thermalLayer, crismLayer, geologyLayer, boundary, references, routeLayer, endpointLayer, selected],
      controls: defaultControls({rotate: false, attributionOptions: {collapsible: false}}).extend([new ScaleLine({className:'mars-scale-line',units:'metric',minWidth:100})]),
      view: new View({projection: mars, extent: region.imagery_bounds_m, constrainOnlyCenter: true, minResolution: 2, maxResolution: 80})});
    const inspect = coordinate => {
      const sample = sampleAt(coordinate, region, grids);
      selection.clear();
      if (sample.status === 'valid') selection.addFeature(new Feature(new Point(sample.center)));
      latestSample.current(sample);
    };
    map.on('singleclick', event => {
      inspect(event.coordinate);
      const unit = map.forEachFeatureAtPixel(event.pixel, feature => feature, {layerFilter: layer => layer === geologyLayer, hitTolerance: 4});
      onGeologySample(unit ? {mapUnit: unit.get('map_unit'), unitName: unit.get('unit_name')} : null);
    });
    const fit = () => map.getView().fit(region.bounds_m, {padding: [85, 45, 60, 45], duration: 0});
    const fitWider = () => {
      const [west,south,east,north]=region.bounds_m;
      const dx=(east-west)*.25,dy=(north-south)*.25;
      map.getView().fit([west-dx,south-dy,east+dx,north+dy],{padding:[85,45,60,45],duration:0});
    };
    fitWider();
    const observer = new ResizeObserver(() => map.updateSize());
    observer.observe(target.current);
    mapRef.current = {fit, fitWider, inspect, sampleCenter: () => inspect(map.getView().getCenter()),
      inspectReference: i => inspect([region.control_points[i].x_m, region.control_points[i].y_m])};
    layers.current = {imagery, elevation, slope, thermalLayer, crismLayer, geologyLayer, geologySource, references, routeSource, endpointSource, functions};
    return () => {observer.disconnect(); mapRef.current = null; map.setTarget(undefined);};
  }, [data]);
  useEffect(() => {
    if (!layers.current || !geology) return;
    const source = layers.current.geologySource;
    source.clear();
    source.addFeatures(new GeoJSON().readFeatures(geology.geojson, {dataProjection: layers.current.imagery.getSource().getProjection(), featureProjection: layers.current.imagery.getSource().getProjection()}));
  }, [geology, data]);
  useEffect(() => {layers.current?.geologyLayer.setVisible(Boolean(geology && geologyOn));}, [geology, geologyOn, data]);
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
  useEffect(()=>{
    if(!layers.current)return;
    const layer=layers.current.crismLayer;
    layer.setSource(crism?new ImageStatic({url:crism.imageUrl,projection:layers.current.imagery.getSource().getProjection(),imageExtent:crism.meta.bounds_m,interpolate:false,
      attributions:'CRISM MTRDR D2300 spectral parameter · MRO / PDS Geosciences Node'}):null);
    layer.setVisible(Boolean(crism&&crismOn));
  },[crism,data]);
  useEffect(()=>{layers.current?.crismLayer.setVisible(Boolean(crism&&crismOn));},[crismOn,crism,data]);
  useEffect(()=>{layers.current?.crismLayer.setOpacity(opacity);},[opacity,data]);
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

function Sample({sample,thermal,thermalOn,crism,crismOn,crismSampleValue,geologySample}) {
  const thermalSample=sample?.status==='valid'&&thermal&&thermalOn?sampleThermal(sample.lonlat,thermal):null;
  return <section className="sample" aria-live="polite" aria-atomic="true" data-testid="sample-panel">
      <div className="eyebrow"><span className="small-cross">+</span> TERRAIN INSPECTOR</div>
      {!sample && <><h2>Choose a point.</h2><p>Click inside the dashed DEM boundary to inspect a native terrain cell.</p></>}
      {sample?.status === 'outside' && <><h2>No terrain coverage</h2><p>This point is outside the selected DEM. Choose a point inside the dashed boundary.</p></>}
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
      {crismOn&&crism&&<div className="crism-readout" data-testid="crism-readout"><span className="type-label">MRO CRISM · D2300</span>{crismSampleValue?.status==='valid'?<><strong data-testid="crism-value">{crismSampleValue.value.toFixed(5)}</strong><span>Dimensionless 2.3 µm spectral-drop parameter · 20 m display grid</span><p>One spectral-shape index, not a mineral identification, concentration, or resource measurement. Nearest-neighbour sample at the terrain-cell centre.</p></>:<p>{crismSampleValue?.status==='nodata'?'This terrain cell is outside the CRISM product coverage or has a source missing value.':'No valid CRISM coverage at this location.'}</p>}</div>}
      {geologySample&&<div className="geology-readout" data-testid="geology-readout"><span className="type-label">USGS SIM 3464 · MAPPED UNIT</span><strong>{geologySample.mapUnit}</strong><span>{geologySample.unitName}</span><p>Published regional interpretation at 1:75,000 scale. Source reports 100–200 m random offsets versus the controlled CTX map. This is not a mineral concentration or resource measurement.</p></div>}
    </>}
  </section>;
}

function App() {
  const [data, setData] = useState(null);
  const [regionId,setRegionId]=useState('jezero-m1');
  const [error, setError] = useState('');
  const [imageError, setImageError] = useState('');
  const [sample, setSample] = useState(null);
  const [imageryOn, setImageryOn] = useState(true);
  const [slopeOn, setSlopeOn] = useState(false);
  const [elevationOn, setElevationOn] = useState(false);
  const [referencesOn, setReferencesOn] = useState(false);
  const [opacity, setOpacity] = useState(.55);
  const [thermal,setThermal]=useState(null);
  const [thermalOn,setThermalOn]=useState(false);
  const [thermalError,setThermalError]=useState('');
  const [geology,setGeology]=useState(null);
  const [geologyError,setGeologyError]=useState('');
  const [geologySample,setGeologySample]=useState(null);
  const [crism,setCrism]=useState(null);
  const [crismError,setCrismError]=useState('');
  const [crismSampleValue,setCrismSampleValue]=useState(null);
  const mapRef = useRef(null);
  const mission = useMission(data);
  const [contexts,setContexts]=useState([]);
  const [wideView,setWideView]=useState(true);
  const geologyOn=contexts.includes('geology');
  const crismOn=contexts.includes('minerals');
  const [routeVisibility,setRouteVisibility]=useState({distance:true,terrain:true});
  const toggleContext=id=>setContexts(old=>old.includes(id)?old.filter(value=>value!==id):[...old,id]);
  const handleSample=sample=>{setSample(sample);if(mission.mode!=='inspect')mission.pick(sample);};
  useEffect(() => {let active = true;setData(null);setError('');setThermal(null);setCrism(null);setGeology(null);setCrismError('');setGeologyError('');loadRegion(regionId).then(result => {if (active){setData(result);setWideView(regionId==='jezero-m1');if(result.imagery.error)setImageError(result.imagery.error);}}).catch(error => {if (active) setError(`Terrain data could not be loaded: ${error.message}`);}); return () => {active = false;};}, [regionId]);
  useEffect(()=>{
    if (!data) return;
    let active=true,asset=null;
    loadThermal(data.manifestHash,data.dataPrefix).then(result=>{asset=result;if(active)setThermal(result);else URL.revokeObjectURL(result.imageUrl);}).catch(error=>{if(active)setThermalError(error.message);});
    return ()=>{active=false;if(asset)URL.revokeObjectURL(asset.imageUrl);};
  },[data]);
  useEffect(()=>{
    if(!data||!geologyOn||geology||geologyError)return;
    let active=true;
    (async()=>{
      const base=`/data/${data.dataPrefix}geology/`;
      const [manifestResponse,geoResponse]=await Promise.all([fetch(base+'manifest.json'),fetch(base+'sim3464-units.geojson')]);
      if(!manifestResponse.ok||!geoResponse.ok)throw new Error('Run the SIM 3464 geology preprocessing command, then reload the app.');
      const manifest=await manifestResponse.json();
      const raw=await geoResponse.arrayBuffer();
      const actual=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),byte=>byte.toString(16).padStart(2,'0')).join('');
      if(actual!==manifest.feature_collection_sha256)throw new Error('Geology layer checksum differs from its source-derived manifest.');
      if(data.manifestHash!==manifest.region_manifest_sha256)throw new Error('Geology layer was built for a different terrain region.');
      const geojson=JSON.parse(new TextDecoder().decode(raw));
      if(active)setGeology({manifest,geojson});
    })().catch(error=>{if(active)setGeologyError(error.message);});
    return()=>{active=false;};
  },[data,geologyOn,geology,geologyError]);
  useEffect(()=>{
    if(!data||!crismOn||crism||crismError)return;
    let active=true,asset=null;
    loadCrism(data.manifestHash,data.dataPrefix).then(result=>{asset=result;if(active)setCrism(result);else URL.revokeObjectURL(result.imageUrl);}).catch(error=>{if(active)setCrismError(error.message);});
    return()=>{active=false;if(asset)URL.revokeObjectURL(asset.imageUrl);};
  },[data,crismOn,crism,crismError]);
  useEffect(()=>{setCrismSampleValue(sample?.status==='valid'&&crism&&crismOn?sampleCrism(sample.lonlat,crism):null);},[sample,crism,crismOn]);
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
        <section className="region-card"><span className="type-label">VERIFIED TERRAIN / ROUTE COVERAGE</span><div className="extent-number">~{data?.regionId==='expanded-7p5km'?'7.5':'5'} × {data?.regionId==='expanded-7p5km'?'7.5':'5'} <span>km native DEM</span><span className="corner-arrow">↗</span></div><p>Dashed boundary shows the selected real DEM and routing grid at native 20 m spacing. CTX imagery extends beyond it.</p><label className="region-select">Terrain coverage<select aria-label="Terrain coverage" value={regionId} onChange={e=>setRegionId(e.target.value)}><option value="jezero-m1">Original pilot · 5 × 5 km</option><option value="expanded-7p5km">Expanded · 7.5 × 7.5 km</option></select></label>{regionId==='expanded-7p5km'&&<small>SIM 3464 geology and CRISM use the expanded source intersection. CRISM has uncovered grid cells. THEMIS covers this region with its native 100 m pixels.</small>}</section>
        <section className="layers-section" id="data-layers"><div className="section-heading"><h2>Map layers</h2><span>VERIFIED</span></div>
          <label className="layer-row"><span className="layer-icon">▧</span><span><b>CTX imagery</b><small>NASA / USGS · {data?.imagery.detail?'Z13 · ~5 M TILE PIXEL':'M1 CACHED FALLBACK'}</small></span><input type="checkbox" aria-label="CTX imagery" checked={imageryOn} onChange={e => setImageryOn(e.target.checked)}/></label>
          <label className="layer-row"><span className="layer-icon">▥</span><span><b>Elevation tint</b><small>SOURCE DEM · METRES</small></span><input type="checkbox" aria-label="Elevation tint" checked={elevationOn} onChange={e=>{setElevationOn(e.target.checked);if(e.target.checked)setThermalOn(false);}}/></label>
          {elevationOn&&<p className="elevation-legend">Elevation tint: purple {data?.region.statistics.elevation_range_m[0].toFixed(0)} m → warm {data?.region.statistics.elevation_range_m[1].toFixed(0)} m.</p>}
          <label className="layer-row"><span className="layer-icon slope-icon">▨</span><span><b>Terrain slope</b><small>DERIVED · CTX ELEVATION</small></span><input type="checkbox" aria-label="Terrain slope" checked={slopeOn} onChange={e => {setSlopeOn(e.target.checked);if(e.target.checked)setThermalOn(false);}}/></label>
          <label className="opacity-control">Overlay opacity <span>{Math.round(opacity*100)}%</span><input aria-label="Overlay opacity" type="range" min="0" max="100" value={Math.round(opacity*100)} disabled={!slopeOn&&!thermalOn&&!crismOn} onChange={e => setOpacity(Number(e.target.value)/100)}/></label>
          <label className="references-toggle"><input type="checkbox" checked={referencesOn} onChange={e => setReferencesOn(e.target.checked)}/> Show verification samples</label>
          {referencesOn && data && <div className="reference-buttons">{data.region.control_points.map((_, i) => <button key={i} onClick={() => mapRef.current?.inspectReference(i)} aria-label={`Inspect verification sample ${i+1}`}>{i+1}</button>)}</div>}
        </section>
        <section className="environment-map-controls"><div className="section-heading"><h2>Environmental map</h2><span>SPATIAL DATA</span></div>
          <label className="layer-row"><span className="layer-icon">◧</span><span><b>Surface thermal response</b><small>THEMIS · THERMAL INERTIA · 100 M</small></span><input type="checkbox" aria-label="Surface thermal response map" disabled={!thermal} checked={thermalOn} onChange={event=>{setThermalOn(event.target.checked);if(event.target.checked){setSlopeOn(false);setElevationOn(false);}}}/></label>
          {thermalError?<p role="status" className="context-limit">{thermalError}</p>:!thermal?<p>Checking thermal-map data…</p>:<details><summary>What these colours mean</summary><p>Lower thermal inertia: faster heating/cooling. Higher: stronger resistance to temperature changes. Colours do not show hot/cold temperature or travel safety.</p><p>{thermal.meta.source_pixel_size_m} m source pixels · {thermal.meta.unit}. Published {thermal.meta.published}.</p><p>{thermal.meta.observation_time}</p><p>{thermal.meta.limits}</p><a href={thermal.meta.source_url} target="_blank" rel="noreferrer">Edwards & Buz · source and methods ↗</a></details>}
          <p>Temperature, storm and radiation colour maps remain unavailable: existing rover readings/reports do not establish spatial distributions. Historical context panels below are separate.</p>
        </section>
        <ContextLayers group="Environmental" enabled={contexts} onToggle={toggleContext}/>
        {crismError&&<p role="status" className="context-limit">{crismError}</p>}
        <ContextLayers group="Scientific" enabled={contexts} onToggle={id=>{toggleContext(id);if(id==='geology')setGeologySample(null);if(id==='minerals')setCrismSampleValue(null);}} geologyAvailable={Boolean(geology)} geologyError={geologyError} geologyMeta={geology?.manifest} crismAvailable={Boolean(crism)} crismError={crismError} crismMeta={crism?.meta} regionId={data?.regionId}/>
        <section className="route-layers"><div className="section-heading"><h2>Route layers</h2><span>DERIVED</span></div>{['distance','terrain'].map(objective=><label className={`route-toggle ${objective}`} key={objective}><input type="checkbox" aria-label={`${objective} route layer`} checked={routeVisibility[objective]} onChange={e=>setRouteVisibility(old=>({...old,[objective]:e.target.checked}))}/><i/>{objective==='distance'?'Distance route':'Terrain route'}</label>)}</section>
          <section className="method-note"><div className="eyebrow">HOW TO READ THIS MAP</div><p>Color shows terrain gradient, from gentle to steep. It does not classify safe travel.</p><p className="muted">Environmental context contains dated rover observations and regional reports. No current regional weather, measured Jezero radiation or resource inventory.</p></section>
        <details className="sources"><summary>Sources & processing <span>↗</span></summary><div>
          <p><b>Elevation observation:</b> Fred Calef / USGS / PDS, CTX Science Investigation DEM (2021), version 1.0; native 20 m grid. MRO mission. Public domain; cite authors.</p>
          <p><a href="https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic" target="_blank" rel="noreferrer">USGS DEM catalog ↗</a> · <a href="https://doi.org/10.1126/science.abl4051" target="_blank" rel="noreferrer">Mangold et al. 2021 ↗</a></p>
          <p><b>Imagery observation:</b> NASA/JPL Mars Trek / USGS, controlled Jezero CTX mosaic, cached matrix 11 (~20.35 m/pixel at equator; source imagery nominal ~6 m). <a href="https://doi.org/10.5066/P906QQT8" target="_blank" rel="noreferrer">Fergason et al. 2020 ↗</a></p>
          {data?.imagery.detail&&<p><b>Detailed basemap:</b> same real CTX product, mosaic of 64 NASA Mars Trek matrix-13 tiles, 2048 × 2048 px (~5.09 m tile spacing at the equator; imagery source nominal ~6 m). This sharpens visual detail but does not increase DEM resolution or guarantee obstacle-scale accuracy. <a href="/data/imagery-detail-manifest.json" target="_blank" rel="noreferrer">Tile manifest and checksums ↗</a></p>}
          {data && <><p className="product-id">{data.region.sources.dem.product_id}<br/>{data.region.sources.imagery.layer}</p><p><b>Derived slope:</b> central elevation differences with actual Mars horizontal neighbor distances. Missing neighbors stay masked; no filling or terrain resampling.</p><p><b>Projection:</b> Mars sphere R=3,396,190 m, equirectangular standard parallel 18.4663°. Positive-east longitude; planetocentric latitude. Explicit projected metres, never Earth Web Mercator.</p><p><b>Limits:</b> no explicit vertical CRS in source. Catalog radius conflicts with raster; raster CRS used. Imagery license absent from service response; attribution retained, source terms pending submission review. Both layers use MRO.</p><a href="/data/manifest.json" target="_blank" rel="noreferrer">Full manifest, checksums & method ↗</a></>}
        </div></details>
        <div className="sidebar-footer">NASA SPACE APPS 2026 <span>M3 / MISSION CONTROL</span></div>
      </aside>
      <section className="map-stage" aria-label="Terrain exploration workspace">
        {data && <TerrainMap data={data} thermal={thermal} thermalOn={thermalOn} crism={crism} crismOn={crismOn} geology={geology} geologyOn={geologyOn} imageryOn={imageryOn} elevationOn={elevationOn} slopeOn={slopeOn} opacity={opacity} referencesOn={referencesOn} onSample={handleSample} onGeologySample={setGeologySample} onImageError={setImageError} mapRef={mapRef} markers={mission.markers} routeResult={mission.result} activeRoute={mission.activeRoute} routeVisibility={routeVisibility}/>}
        {!data && <div className="loading" role={error ? 'alert' : 'status'}><span className="eyebrow">MARSWALK / DATA</span><h2>{error ? 'Terrain unavailable' : 'Opening Jezero…'}</h2><p>{error || 'Loading verified local imagery and native elevation cells.'}</p>{error && <button onClick={() => window.location.reload()}>Reload data</button>}</div>}
        {imageError && <div className="image-error" role="alert">{imageError}</div>}
        {data && <>
            <div className="map-toolbar"><span className="map-label"><span className="orange-square"/> JEZERO / {data.regionId==='expanded-7p5km'?'EXPANDED REGION':'PILOT 01'}</span><div><button onClick={() => mapRef.current?.sampleCenter()}>⌖ <span>Sample map center</span></button><button onClick={() => {if(wideView){mapRef.current?.fit();setWideView(false);}else{mapRef.current?.fitWider();setWideView(true);}}}>↗ <span>{wideView?'Fit terrain':'Wider view'}</span></button></div></div>
          <div className="north" aria-label="North is up">N<span>↑</span></div>
          {mission.mode!=='inspect'&&<div className="pick-instruction" role="status">Select {mission.mode==='start'?'starting location A':'destination B'} on the map, or use Sample map center.<button onClick={()=>mission.setMode('inspect')}>Cancel selection</button></div>}
          {mission.result?.status==='ok'&&<div className="map-route-status" data-testid="map-route-status">{mission.result.routes.filter(route=>routeVisibility[route.objective]).length} calculated route layers displayed · A start / B destination</div>}
          <div className="map-bottom"><div className="legend"><div className="eyebrow">{crismOn?'CRISM D2300 · DIMENSIONLESS SPECTRAL INDEX':geologyOn?'USGS GEOLOGIC UNIT INTERPRETATION':thermalOn?'THERMAL INERTIA · NOT TEMPERATURE':slopeOn?'DERIVED SLOPE / DEGREES':elevationOn?'SOURCE ELEVATION / METRES':'NASA / USGS CTX ORBITAL IMAGERY'}</div>{crismOn&&crism?<div className="crism-legend"><div/><span>−0.01</span><span>0</span><span>+0.02</span></div>:geologyOn&&geology?<div className="geology-legend">{[...new globalThis.Map(geology.geojson.features.map(feature=>[feature.properties.map_unit,feature.properties])).values()].sort((a,b)=>a.style_index-b.style_index).map(unit=><div key={unit.map_unit}><i style={{backgroundColor:GEOLOGY_COLORS[unit.style_index%GEOLOGY_COLORS.length]}}/><span><b>{unit.map_unit}</b> {unit.unit_name}</span></div>)}</div>:thermalOn?<div className="legend-colors">{thermal.meta.legend.colors.map((c, i) => <div key={i}><span style={{backgroundColor:`rgb(${c.join(',')})`}}/><small>{thermal.meta.legend.labels[i]}</small></div>)}</div>:slopeOn?<div className="legend-colors">{data.region.legend.colors.map((c, i) => <div key={i}><span style={{backgroundColor:`rgb(${c.join(',')})`}}/><small>{data.region.legend.labels[i]}</small></div>)}</div>:<div className="imagery-legend"><span className="imagery-swatch"/> Optical orbital image</div>}<p>{crismOn?'Continuous D2300 spectral-shape index; no threshold or mineral classification. Blank areas are outside product coverage.':geologyOn?'Categorical colors distinguish map-unit symbols only; they are not measurements. Source positional offset: 100–200 m.':thermalOn?'J m⁻² K⁻¹ s⁻½ · native 100 m source · derived mosaic':slopeOn?'Dashed outline: numeric terrain coverage':elevationOn?'Color tint from measured DEM elevations; 20 m source cells.':'CTX imagery provides surface appearance, not elevation or current conditions.'}</p></div><Sample sample={sample} thermal={thermal} thermalOn={thermalOn} crism={crism} crismOn={crismOn} crismSampleValue={crismSampleValue} geologySample={geologySample}/></div>
          <div className="map-caption"><span>CTX ORBITAL IMAGERY · POSITIVE-EAST LONGITUDE · PLANETOCENTRIC LATITUDE</span><span>PLANNING DEMONSTRATION · NO SAFETY CERTIFICATION</span></div>
        </>}
      </section>
      <MissionInsights mission={mission} contexts={contexts} geologyMeta={geology?.manifest} crismMeta={crism?.meta}/>
    </main>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
