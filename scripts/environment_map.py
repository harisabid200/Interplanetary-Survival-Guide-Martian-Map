"""Fetch/verify a real Jezero thermal-property raster; preserve native pixels across selectable regions."""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import numpy as np
import rasterio
from rasterio.windows import from_bounds, Window
from pyproj import CRS, Transformer
from PIL import Image
from backend.environment import digest
from scripts.fetch_environment import download

RAW=ROOT/'data/raw/environment-map/Jezero_Thermal_Inertia_v1.tiff'
OUT=ROOT/'data/processed/environment-map'
PUBLIC=ROOT/'frontend/public/data/environment-map'
EVIDENCE=ROOT/'evidence/environment-map'
URL='https://zenodo.org/api/records/4931348/files/Jezero_Thermal_Inertia_v1.tiff/content'
SHA='84401e7717d43ae80cbd80213b91bd141ee48197eb8648293197447c43c2829c'
COLORS=[[63,101,169],[95,169,185],[178,197,165],[224,179,110],[195,105,78]]
BREAKS=[200,300,400,500]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch',action='store_true')
    parser.add_argument('--region',type=Path,default=ROOT/'data/processed/jezero-m1/manifest.json')
    parser.add_argument('--output',type=Path,default=OUT)
    parser.add_argument('--public',type=Path,default=PUBLIC)
    parser.add_argument('--evidence',type=Path,default=EVIDENCE)
    args=parser.parse_args()
    output=args.output.resolve(); public=args.public.resolve(); evidence=args.evidence.resolve()
    output.mkdir(parents=True,exist_ok=True);public.mkdir(parents=True,exist_ok=True);evidence.mkdir(parents=True,exist_ok=True)
    if args.fetch:
        record=download(URL,RAW)
        (evidence/'acquisition.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
    if digest(RAW)!=SHA or digest(RAW,'md5')!='53fec7c990a90629e98c871a7a0da474':
        raise ValueError('Published raster checksum mismatch; no fallback')
    region=json.loads(args.region.resolve().read_text())
    target=CRS.from_wkt(region['crs']['wkt'])
    with rasterio.open(RAW) as ds:
        source=CRS(ds.crs)
        if source.ellipsoid.semi_major_metre!=3396190 or source.ellipsoid.inverse_flattening!=0 or ds.nodata!=0 or ds.res!=(100,100):
            raise ValueError('Unexpected source Mars CRS/nodata/native sampling')
        proj=source.to_dict()
        if proj['proj']!='eqc' or proj.get('lat_ts',0)!=0 or proj.get('lon_0',0)!=0 or proj.get('x_0',0)!=0 or proj.get('y_0',0)!=0:
            raise ValueError('Only verified source equirectangular geometry supported')
        to_source=Transformer.from_crs(target,source,always_xy=True)
        to_target=Transformer.from_crs(source,target,always_xy=True)
        w,s,e,n=region['bounds_m']
        sw=to_source.transform(w,s);ne=to_source.transform(e,n)
        floating=from_bounds(*sw,*ne,ds.transform)
        c=math.floor(floating.col_off);r=math.floor(floating.row_off)
        win=Window(c,r,math.ceil(floating.col_off+floating.width)-c,math.ceil(floating.row_off+floating.height)-r)
        if c<0 or r<0 or c+win.width>ds.width or r+win.height>ds.height:
            raise ValueError('Pilot not covered by source raster')
        z=ds.read(1,window=win);valid=ds.read_masks(1,window=win)>0
        valid &= np.isfinite(z)&(z!=0)
        if not valid.any():
            raise ValueError('No valid thermal-property coverage')
        affine=ds.window_transform(win);bounds=list(ds.window_bounds(win))
        target_bounds=[*to_target.transform(bounds[0],bounds[1]),*to_target.transform(bounds[2],bounds[3])]
        # Same-radius equirectangular projections differ by linear x scale only.
        scale=math.cos(math.radians(region['crs']['standard_parallel_deg']))
        if not np.allclose(target_bounds,[bounds[0]*scale,bounds[1],bounds[2]*scale,bounds[3]],atol=1e-7,rtol=0):
            raise ValueError('Source-to-map geometry failed independent transform check')
        rgba=np.zeros((*z.shape,4),dtype='uint8')
        for i,color in enumerate(COLORS):
            select=valid&(np.digitize(z,BREAKS)==i)
            rgba[select]=[*color,255]
        np.where(valid,z,np.nan).astype('<f4').tofile(output/'thermal.f32')
        valid.astype('uint8').tofile(output/'valid.u8')
        Image.fromarray(rgba).save(output/'thermal.png')
        controls=[]
        for row,col in [(0,0),(z.shape[0]//2,z.shape[1]//2),(z.shape[0]-1,z.shape[1]-1)]:
            x,y=affine*(col+.5,row+.5)
            controls.append(dict(row=row,col=col,source_xy_m=[x,y],map_xy_m=list(to_target.transform(x,y)),value=float(z[row,col]) if valid[row,col] else None))
        manifest=dict(schema_version=1,quantity='thermal_inertia',unit='J m⁻² K⁻¹ s⁻½',
            title='Surface thermal response',source_title='THEMIS-derived Thermal Inertia of Jezero Crater, Mars',
            source_url='https://doi.org/10.5281/zenodo.4931348',authors='Edwards & Buz',license='CC BY 4.0',
            published='2021-06-11',observation_time='Multi-image nighttime mosaic; individual acquisition dates are not supplied in the GeoTIFF. Not current conditions.',
            kind='Published derived thermal property; not temperature or atmospheric weather',
            source_sha256=SHA,source_crs_wkt=source.to_wkt(),source_pixel_size_m=100,
            source_shape=list(ds.shape),width=z.shape[1],height=z.shape[0],affine=list(affine)[:6],
            crs=dict(radius_m=3396190,standard_parallel_deg=0,central_meridian_deg=0),
            bounds_source_m=bounds,bounds_map_m=target_bounds,clip_bounds_map_m=region['bounds_m'],
            terrain_manifest_sha256=digest(args.region.resolve()),
            valid_pixels=int(valid.sum()),total_pixels=int(valid.size),range=[float(z[valid].min()),float(z[valid].max())],
            legend=dict(breaks=BREAKS,colors=COLORS,labels=['<200','200–300','300–400','400–500','≥500']),
            method='Native source crop; no value interpolation, resampling or artificial 20 m detail. Image extent uses verified same-sphere equirectangular transform and is clipped visually to the pilot.',
            limits='Thermal inertia describes resistance to heating/cooling. It is not air/surface temperature, live weather, dust storm probability or radiation. Mosaic blending, thermal-model assumptions and albedo influence apply; source reports inter-image offsets up to approximately 20 thermal-inertia units, not a complete uncertainty bound.',
            controls=controls,
            outputs={name:dict(bytes=(output/name).stat().st_size,sha256=digest(output/name)) for name in ['thermal.f32','valid.u8','thermal.png']})
    payload=json.dumps(manifest,indent=2,allow_nan=False)+'\n'
    (output/'manifest.json').write_text(payload,encoding='utf-8')
    for path in output.iterdir():
        if path.is_file():shutil.copyfile(path,public/path.name)
    (evidence/'inspection.json').write_text(payload,encoding='utf-8')
    print(json.dumps({key:manifest[key] for key in ['width','height','valid_pixels','range','bounds_map_m']},indent=2))


if __name__=='__main__':main()
