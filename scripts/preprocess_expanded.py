"""Build a separate, real 7.5 km Jezero terrain grid from the verified CTX DEM.

The M1 5 km pilot is read-only and untouched. The expanded crop is centered on
the same source-grid cell and contains no resampling or nodata filling.
"""
import json
import shutil
from pathlib import Path

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.windows import Window, bounds as window_bounds

from inspect_dem import ROOT, SOURCE, sha256
from preprocess import central_slope, write_json, COLORS, BREAKS

OUT = ROOT / 'data/processed/jezero-expanded-7p5km'
PUBLIC = ROOT / 'frontend/public/data/expanded'
EVIDENCE = ROOT / 'evidence/map-expansion'
SIZE = 375


def main():
    base = json.loads((ROOT/'data/processed/jezero-m1/manifest.json').read_text())
    m0 = json.loads((ROOT/'evidence/m0/dem-inspection.json').read_text())
    if sha256(SOURCE) != m0['sha256']:
        raise ValueError('Raw CTX DEM hash differs from the verified M0 source')
    col0, row0, width0, height0 = map(int, m0['pilot']['window_col_row_width_height'])
    if width0 != 250 or height0 != 250:
        raise ValueError('Expected original M1 250 x 250 pilot')
    col, row = col0 - (SIZE-width0)//2, row0 - (SIZE-height0)//2
    window = Window(col, row, SIZE, SIZE)
    OUT.mkdir(parents=True, exist_ok=True); PUBLIC.mkdir(parents=True, exist_ok=True); EVIDENCE.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SOURCE) as src:
        if col < 1 or row < 1 or col+SIZE+1 > src.width or row+SIZE+1 > src.height:
            raise ValueError('Expanded terrain window or its slope halo falls outside source raster')
        crs = CRS(src.crs); affine = src.window_transform(window)
        halo = src.read(1, window=Window(col-1,row-1,SIZE+2,SIZE+2), masked=True)
        hmask = ~np.ma.getmaskarray(halo) & np.isfinite(halo.data)
        valid = hmask[1:-1,1:-1]
        dem = halo.data[1:-1,1:-1].copy()
        if not valid.all(): raise ValueError('Expanded window contains DEM nodata; refusing to fill it')
        bounds = list(window_bounds(window,src.transform))
        xx, yy = np.meshgrid(bounds[0]+(np.arange(SIZE)+.5)*20,bounds[3]-(np.arange(SIZE)+.5)*20)
        to_ll=Transformer.from_crs(crs,crs.geodetic_crs,always_xy=True)
        lonw,latw=to_ll.transform(xx-20,yy); lone,late=to_ll.transform(xx+20,yy)
        lonn,latn=to_ll.transform(xx,yy+20); lons,lats=to_ll.transform(xx,yy-20)
        geod=crs.get_geod(); _,_,dx=geod.inv(lonw,latw,lone,late); _,_,dy=geod.inv(lons,lats,lonn,latn)
        slope,slope_valid=central_slope(halo.data,hmask,dx,dy)
        profile=dict(driver='GTiff',width=SIZE,height=SIZE,count=1,crs=src.crs,transform=affine,compress='deflate')
        for name,array,nodata,unit in [('dem.tif',dem,src.nodata,'m'),('slope.tif',slope,-9999,'degree')]:
            dtype='float32'
            with rasterio.open(OUT/name,'w',**profile,dtype=dtype,nodata=nodata) as dst:
                dst.write(np.where(valid if name=='dem.tif' else slope_valid,array,nodata).astype(dtype),1); dst.set_band_unit(1,unit)
        for name,mask in [('valid-mask.tif',valid),('slope-mask.tif',slope_valid)]:
            with rasterio.open(OUT/name,'w',**profile,dtype='uint8') as dst: dst.write(mask.astype('uint8'),1)
    np.asarray(dem,dtype='<f4').tofile(OUT/'elevation.f32'); slope.astype('<f4').tofile(OUT/'slope.f32')
    valid.astype('uint8').tofile(OUT/'valid.u8'); slope_valid.astype('uint8').tofile(OUT/'slope-valid.u8')
    # Reuse exact cached source imagery; its verified footprint contains both regions.
    source_image=ROOT/'data/processed/jezero-m1/imagery.png'
    shutil.copyfile(source_image,OUT/'imagery.png')
    shutil.copyfile(source_image,PUBLIC/'imagery.png')
    image_meta=json.loads((ROOT/'data/processed/jezero-m1/manifest.json').read_text())
    controls=[]
    to_ll=Transformer.from_crs(crs,crs.geodetic_crs,always_xy=True)
    for rr,cc in [(SIZE//2,SIZE//2),(0,0),(0,SIZE-1),(SIZE-1,0),(SIZE-1,SIZE-1)]:
        x,y=affine*(cc+.5,rr+.5); ll=to_ll.transform(x,y)
        controls.append(dict(row=rr,col=cc,x_m=x,y_m=y,lonlat=list(ll),elevation_m=float(dem[rr,cc]),slope_deg=float(slope[rr,cc])))
    # Preserve exact source metadata and M1 provenance while recording the new native crop.
    manifest={**base,'status':'derived','region_id':'expanded-7p5km','width':SIZE,'height':SIZE,
      'affine':list(affine)[:6],'bounds_m':bounds,'bounds_lonlat':list(to_ll.transform(bounds[0],bounds[1]))+list(to_ll.transform(bounds[2],bounds[3])),
      'statistics':{**base['statistics'],'valid_elevation_cells':int(valid.sum()),'valid_slope_cells':int(slope_valid.sum()),
        'elevation_range_m':[float(dem.min()),float(dem.max())],'slope_range_deg':[float(slope[slope_valid].min()),float(slope[slope_valid].max())],
        'slope_percentiles_deg':np.percentile(slope[slope_valid],[50,90,99]).tolist()},
      'control_points':controls,'outputs':{},
      'expansion':{'centered_on':'original M1 5 km crop','source_window_col_row_width_height':[col,row,SIZE,SIZE],
        'source_pixel_spacing_m':[20,20],'native_grid_cells':SIZE*SIZE,'valid_cells':int(valid.sum()),
        'source_m1_manifest_sha256':sha256(ROOT/'data/processed/jezero-m1/manifest.json'),
        'imagery_note':'Original verified imagery footprint covers this crop; imagery is not numeric elevation.'}}
    files=['dem.tif','slope.tif','valid-mask.tif','slope-mask.tif','elevation.f32','slope.f32','valid.u8','slope-valid.u8','imagery.png']
    for filename in files:
        digest=sha256(OUT/filename); size=(OUT/filename).stat().st_size
        manifest['outputs'][filename]={'sha256':digest,'bytes':size}
        shutil.copyfile(OUT/filename,PUBLIC/filename)
    write_json(OUT/'manifest.json',manifest); write_json(PUBLIC/'manifest.json',manifest); write_json(EVIDENCE/'manifest.json',manifest)
    print(json.dumps({'region_id':manifest['region_id'],'window':[col,row,SIZE,SIZE],'valid_cells':int(valid.sum()),
      'slope_valid_cells':int(slope_valid.sum()),'elevation_range_m':manifest['statistics']['elevation_range_m'],
      'bounds_m':bounds,'manifest_sha256':sha256(OUT/'manifest.json')},indent=2))

if __name__=='__main__': main()
