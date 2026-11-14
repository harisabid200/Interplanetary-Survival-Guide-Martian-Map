"""Build M4 historical context from checksum-validated PDS products; no mock data."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.environment import digest, read_product, summarize, number, lmst_seconds

RAW=ROOT/'data/raw/environment'
OUT=ROOT/'data/processed/environment'
EVIDENCE=ROOT/'evidence/m4'
BASE='https://pds-atmospheres.nmsu.edu/PDS/data/PDS4/Mars2020/mars2020_meda/'


def product(pattern, collection):
    matches=list((RAW/'sol-0015').glob(pattern))
    if len(matches)!=1:
        raise ValueError(f'Require exactly one pinned sol 15 product: {pattern}')
    meta,rows=read_product(matches[0])
    if meta['sol']!=15:
        raise ValueError('M4 demonstration requires sol 15')
    meta['label_url']=BASE+collection+'/sol_0000_0089/sol_0015/'+matches[0].name
    return meta,rows


def build():
    t,tr=product('*CAL_ATS*.xml','data_calibrated_env')
    p,pr=product('*DER_PS*.xml','data_derived_env')
    a,ar=product('*ANCILLARY*.xml','data_derived_env')
    temperature=[summarize(t,tr,f'ATS_LOCAL_TEMP{i}','kelvin') for i in range(1,6)]
    pressure=summarize(p,pr,'PRESSURE','pascal')
    axes=[]
    for name in ['ROVER_POSITION_X','ROVER_POSITION_Y','ROVER_POSITION_Z']:
        field=next(f for f in a['fields'] if f['name']==name)
        if field['unit']!='meter':
            raise ValueError('Unexpected ancillary position unit')
        values=[number(r[name],field) for r in ar]
        if any(v is None for v in values):
            raise ValueError('Missing ancillary position; do not invent location')
        axes.append(dict(field=name,minimum=min(values),maximum=max(values)))
    # Verify temporal support; report same-sol geometry, never pretend a per-row geodetic join.
    anc_range=[float(ar[0]['SCLK']),float(ar[-1]['SCLK'])]
    for series in [*temperature,pressure]:
        if series['sclk_range'][0]<anc_range[0] or series['sclk_range'][1]>anc_range[1]:
            raise ValueError('Ancillary time coverage does not contain observations')
    for r in ar:
        lmst_seconds(r['LMST'],a['sol'])
    marci=RAW/'marci-2022-01-26.html'
    if digest(marci)!='4cc23ecd7b911bf04ef20a68c97b6cedfc1dc18a10ff1ce98d3b9fa2687cbfd9':
        raise ValueError('MARCI report changed; review curated interpretation before import')
    caption=marci.read_text(encoding='utf-8')
    for expected in ['MSSS-606','17 January 2022','23 January 2022','no afternoon dust storm activity']:
        if expected not in caption:
            raise ValueError('MARCI source no longer matches curated dated summary')
    rad=RAW/'rad-sol-0001.lbl'
    if digest(rad)!='6eb5e69243b26f845ebeda9575048ac92a72a6f2ae084431170452b4a328c25c':
        raise ValueError('RAD reference label changed; review metadata interpretation')
    label=rad.read_text(encoding='ascii')
    for expected in ['MSL-M-RAD-3-RDR-V1.0','RAD_RDR_2012_220_02_25_0001_V00','2012-220T02:25:43','microGray / Hour']:
        if expected not in label:
            raise ValueError('RAD metadata no longer matches reference')
    return dict(schema_version=1,kind='historical_environment_context',spatial_overlays=[],
        meda=dict(sol=15,temperature_product=t,pressure_product=p,position_product=a,
            temperature=temperature,pressure=pressure,
            method='Native sensor series remain separate. Plotted bins are unweighted means of accepted native samples in 300 LMST-clock-second intervals. No interpolation; empty bins are null. Sample means/ranges are not full-sol or time-weighted climate estimates. UTC bounds are from labels; LMST is from actual rows, not an invented UTC conversion.',
            location=dict(description='Perseverance, Jezero Crater. Same-sol SPICE-derived ancillary coordinates relative to the landing site in M2020_TOPO: +X north, +Z outward normal; +Y completes the right-handed frame (west). Ranges describe the rover positions observed in this sol, not an areal weather footprint.',
                axes=axes,sclk_range=anc_range,
                limit='Landing-site-relative metres, not longitude/latitude or DEM projected metres. No geodetic registration or per-sample position join is claimed; no map pin or weather surface is drawn.'),
            caveats=['ATS and pressure labels contain no per-row quality flags; finite-only screening is not scientific quality certification.',
                     'Pressure uncertainty label lists kelvin, which is inconsistent with pressure units; this field is excluded rather than silently corrected.',
                     'Wind, humidity and local dust opacity were not imported. No DER_WIND product appears in this sol listing.']),
        dust=dict(kind='HISTORICAL REGIONAL REPORT · NOT A FORECAST',date_label='Observed 17–23 January 2022 · released 26 January 2022',
            summary='MSSS reported lingering high-altitude dust after a regional storm subsided, with further local storms near polar caps and Syria–Sinai. No afternoon dust-storm activity was reported at the three active NASA surface sites during that week.',
            limit='Global/regional historical narrative, not a geolocated Jezero opacity measurement, storm polygon or present forecast. This week is not contemporaneous with the MEDA sol shown.',
            source='Malin & Cantor (2022) · MSSS-606 · NASA/JPL-Caltech/MSSS',url='https://www.msss.com/msss_images/2022/01/26/',sha256=digest(marci),
            validation='Cached dated HTML report verified against title/week/release identifier. Source describes intrinsic 1–2 km nadir imagery, lower-resolution public movie, off-nadir blur and data gaps. No image pixels or numerical dust raster imported.'),
        radiation=dict(kind='GALE REFERENCE ONLY · NOT JEZERO',date_label='MSL RAD surface sol 1 · label start 2012-220T02:25:43 (7 August 2012 UTC)',
            summary='Verified PDS3 metadata identifies Curiosity RAD calibrated/decompressed ionizing-radiation observations at Gale Crater. Its detector B/E dose sections use microgray per hour.',
            reference='Numeric dose unavailable: the science-file transfer did not complete. No dose, astronaut effective dose or exposure budget is calculated. MEDA optical radiation is a different measurement.',
            limit='Gale radiation is not measured Jezero radiation. No Jezero dose map or exposure calculation is available.',
            url='https://pds-ppi.igpp.ucla.edu/data/MSL-M-RAD-3-RDR-V1.0/DATA/SOL_00000_00089/RAD_RDR_2012_220_02_25_0001_V00.LBL',
            source='PDS PPI · MSL-M-RAD-3-RDR-V1.0 · product V00',sha256=digest(rad),
            validation='Detached label, archive README and errata acquired. Label stop time is UNK. No numeric science import; partial transfers remain excluded. Detector absorbed dose is not human effective dose.'))


def main():
    result=build()
    OUT.mkdir(parents=True,exist_ok=True);EVIDENCE.mkdir(parents=True,exist_ok=True)
    payload=json.dumps(result,indent=2,allow_nan=False)+'\n'
    path=OUT/'environment.json';path.write_text(payload,encoding='utf-8')
    manifest=dict(schema_version=1,path='environment.json',sha256=digest(path),bytes=path.stat().st_size,
                  provenance=[dict(product_id=p['product_id'],version=p['version'],data_sha256=p['data_sha256'],label_sha256=p['label_sha256'],label_url=p['label_url']) for p in [result['meda'][k] for k in ['temperature_product','pressure_product','position_product']]],
                  spatial_overlays=[],observation_scope='MEDA historical rover-local; MARCI historical regional report; RAD Gale metadata reference only')
    (OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    summary=dict(manifest=manifest,meda={k:v for k,v in result['meda'].items() if k not in ('temperature','pressure')},
                 temperature=[{k:v for k,v in s.items() if k!='bins'} for s in result['meda']['temperature']],
                 pressure={k:v for k,v in result['meda']['pressure'].items() if k!='bins'},dust=result['dust'],radiation=result['radiation'])
    (EVIDENCE/'environment-verification.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(dict(temperature_rows=result['meda']['temperature_product']['records'],pressure_rows=result['meda']['pressure_product']['records'],sha256=manifest['sha256']),indent=2))


if __name__=='__main__':
    main()
