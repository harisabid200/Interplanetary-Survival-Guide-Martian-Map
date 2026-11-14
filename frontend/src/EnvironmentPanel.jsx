import React, {useEffect,useState} from 'react';
import {apiJson} from './api.js';

function Series({series}) {
  const span=Math.max(series.maximum-series.minimum,1);
  const y=value=>14+(series.maximum-value)/span*88;
  return <div className="environment-series">
    <div className="environment-range"><strong>{series.minimum.toFixed(2)}–{series.maximum.toFixed(2)} <small>{series.unit==='kelvin'?'K':'Pa'}</small></strong><span>OBSERVED SAMPLE RANGE</span></div>
    <svg viewBox="0 0 310 136" role="img" aria-label={`${series.field}: five-minute LMST bin means; gaps not interpolated`}>
      <line x1="43" y1="14" x2="43" y2="102" stroke="#657779"/><line x1="43" y1="102" x2="295" y2="102" stroke="#657779"/>
      <text x="0" y="18">{series.maximum.toFixed(1)}</text><text x="0" y="103">{series.minimum.toFixed(1)}</text>
      {[0,6,12,18,24].map(hour=><text key={hour} x={43+hour/24*252-5} y="119">{hour}</text>)}<text x="128" y="134">LMST hours</text>
      {series.bins.filter(bin=>bin.count>0).map(bin=><circle key={bin.lmst_start_seconds} cx={43+(bin.lmst_start_seconds+150)/86400*252} cy={y(bin.mean)} r="1.4" fill="#85dfc8"><title>{`${(bin.lmst_start_seconds/3600).toFixed(2)} LMST h: ${bin.mean.toFixed(2)} ${series.unit}; ${bin.count} samples`}</title></circle>)}
    </svg>
    <p>DERIVED · dots are 5-minute means of accepted samples; empty bins stay empty. No interpolation. Range above uses native samples, not bin means.</p>
    <p>{series.accepted.toLocaleString()} accepted · {series.rejected.toLocaleString()} excluded. Largest accepted-sample gap: {series.max_accepted_gap_sclk_seconds.toFixed(1)} spacecraft-clock seconds.</p>
    <p className="context-limit">{series.quality}</p>
  </div>;
}

function Weather({data}) {
  const [sensor,setSensor]=useState('ATS_LOCAL_TEMP1');
  const meda=data.meda;
  return <>
    <span className="evidence-kind">HISTORICAL OBSERVATIONS · JEZERO ROVER</span>
    <p>Perseverance / MEDA · Sol {meda.sol}<br/>{meda.temperature_product.start_utc} → {meda.temperature_product.stop_utc}</p>
    <label className="form-label">Air-temperature detector<select aria-label="Air-temperature detector" value={sensor} onChange={event=>setSensor(event.target.value)}>{meda.temperature.map(item=><option key={item.field} value={item.field}>{item.field.replace('ATS_LOCAL_TEMP','Sensor ')} · near-unit air</option>)}</select></label>
    <p>{meda.temperature.find(item=>item.field===sensor).description}</p>
    <Series series={meda.temperature.find(item=>item.field===sensor)}/>
    <h4>Atmospheric pressure · derived product</h4>
    <p>{meda.pressure_product.start_utc} → {meda.pressure_product.stop_utc}</p>
    <Series series={meda.pressure}/>
    <details><summary>Location, sampling & provenance</summary><p>{meda.location.description}</p>{meda.location.axes.map(axis=><p key={axis.field}>{axis.field}: {axis.minimum.toFixed(2)} to {axis.maximum.toFixed(2)} m</p>)}<p>{meda.location.limit}</p><p>{meda.method}</p>{meda.caveats.map(note=><p className="context-limit" key={note}>{note}</p>)}{[meda.temperature_product,meda.pressure_product,meda.position_product].map(product=><p key={product.product_id} className="hash-text"><a href={product.label_url} target="_blank" rel="noreferrer">{product.filename} · version {product.version}</a><br/>SHA256 {product.data_sha256}<br/>{product.records.toLocaleString()} rows ? dominant interval {product.sampling_sclk_seconds.dominant_step} spacecraft-clock s</p>)}</details>
    <p className="context-limit">Rover-local historical samples cannot describe current weather across the pilot. Near-unit temperature may be influenced by the rover. Wind, humidity, local opacity and forecasts are unavailable in this import.</p>
  </>;
}

export function EnvironmentPanel({id}) {
  const [state,setState]=useState({status:'loading'});
  const [attempt,setAttempt]=useState(0);
  useEffect(()=>{
    const controller=new AbortController();
    setState({status:'loading'});
    (async()=>{try {
      const response=await fetch('/api/environment',{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(8000)])});
      const body=await apiJson(response);
      if (!response.ok) throw new Error(body.message||'Environmental data unavailable.');
      setState({status:'ready',data:body});
    } catch(error) {if (!controller.signal.aborted) setState({status:'error',message:error.message});}})();
    return ()=>controller.abort();
  },[attempt]);
  if (state.status==='loading') return <p role="status">Loading verified environmental archive…</p>;
  if (state.status==='error') return <div role="alert"><p>{state.message}</p><p>No measurements shown. Run the M4 acquisition/preprocessing commands and restart the backend.</p><button onClick={()=>setAttempt(value=>value+1)}>Retry environmental data</button></div>;
  const data=state.data;
  if (id==='temperature') return <Weather data={data}/>;
  const item=data[id];
  return <><span className="evidence-kind">{item.kind}</span><p>{item.date_label}</p><p>{item.summary}</p>{item.reference&&<p className="environment-reference">{item.reference}</p>}<p className="context-limit">{item.limit}</p><a href={item.url} target="_blank" rel="noreferrer">{item.source} ↗</a><details><summary>Source validation</summary><p>{item.validation}</p><p className="hash-text">SHA256 {item.sha256}</p></details></>;
}
