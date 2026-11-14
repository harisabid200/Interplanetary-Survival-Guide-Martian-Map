"""Smoke-check real outputs against raw source, independently of the pipeline."""
import json
import math

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from pyproj import CRS, Transformer
from rasterio.windows import Window

from inspect_dem import ROOT, SOURCE, sha256


def main():
    out = ROOT/'data/processed/jezero-m1'
    public = ROOT/'frontend/public/data'
    manifest = json.loads((out/'manifest.json').read_text())
    m0 = json.loads((ROOT/'evidence/m0/dem-inspection.json').read_text())
    assert sha256(SOURCE) == manifest['sources']['dem']['sha256']
    col, row, width, height = m0['pilot']['window_col_row_width_height']
    with rasterio.open(SOURCE) as source, rasterio.open(out/'dem.tif') as dem, rasterio.open(out/'slope.tif') as slopes:
        assert dem.crs == source.crs == slopes.crs
        assert dem.transform == source.window_transform(Window(col,row,width,height)) == slopes.transform
        assert dem.nodata == source.nodata and slopes.nodata == -9999
        np.testing.assert_array_equal(dem.read(1), source.read(1, window=Window(col,row,width,height)))
        values = np.fromfile(out/'elevation.f32', dtype='<f4').reshape(height,width)
        np.testing.assert_array_equal(values, dem.read(1))
        slope = np.fromfile(out/'slope.f32', dtype='<f4').reshape(height,width)
        np.testing.assert_array_equal(slope, slopes.read(1))
        with rasterio.open(out/'valid-mask.tif') as mask:
            assert np.array_equal(mask.read(1).astype(bool), dem.read_masks(1)>0)
        with rasterio.open(out/'slope-mask.tif') as mask:
            assert np.array_equal(mask.read(1).astype(bool), slopes.read_masks(1)>0)
        crs = CRS(source.crs)
        to_ll = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        geod = crs.get_geod()
        residuals = []
        for point in manifest['control_points']:
            rr, cc = point['row']+row, point['col']+col
            tile = source.read(1, window=Window(cc-1, rr-1, 3, 3)).astype(float)
            west = to_ll.transform(*source.xy(rr, cc-1))
            east = to_ll.transform(*source.xy(rr, cc+1))
            north = to_ll.transform(*source.xy(rr-1, cc))
            south = to_ll.transform(*source.xy(rr+1, cc))
            _,_,ew=geod.inv(*west,*east)
            _,_,ns=geod.inv(*south,*north)
            expected=math.degrees(math.atan(math.hypot((tile[1,2]-tile[1,0])/ew,(tile[0,1]-tile[2,1])/ns)))
            residual=abs(expected-point['slope_deg'])
            assert residual < 2e-6
            residuals.append(residual)
    for filename, record in manifest['outputs'].items():
        assert sha256(out/filename) == record['sha256'] == sha256(public/filename)
    # Science QA image: exact native cell-center imagery samples alongside slope.
    image = np.asarray(Image.open(out/'imagery.png').convert('RGB'))
    w,s,e,n=manifest['bounds_m']; iw,isouth,ie,inorth=manifest['imagery_bounds_m']
    xx,yy=np.meshgrid(w+(np.arange(width)+.5)*20,n-(np.arange(height)+.5)*20)
    px=np.floor((xx-iw)/(ie-iw)*image.shape[1]).astype(int)
    py=np.floor((inorth-yy)/(inorth-isouth)*image.shape[0]).astype(int)
    sampled=Image.fromarray(image[py,px])
    slope_image=Image.open(out/'slope.png').convert('RGB')
    comparison=Image.new('RGB',(width*2,height+24),'#172124')
    comparison.paste(sampled,(0,24)); comparison.paste(slope_image,(width,24))
    draw=ImageDraw.Draw(comparison)
    draw.text((6,5),'REAL CTX IMAGERY / native cell centers',fill='white')
    draw.text((width+6,5),'DERIVED SLOPE / identical footprint',fill='white')
    for i,point in enumerate(manifest['control_points']):
        for offset in [0,width]:
            x,y=point['col']+offset,point['row']+24
            draw.ellipse((x-2,y-2,x+2,y+2),outline='white')
            draw.text((max(offset,min(x+4,offset+width-9)),max(25,min(y-13,height+10))),str(i+1),fill='white',stroke_width=1,stroke_fill='black')
    comparison.save(ROOT/'evidence/m1/alignment-comparison.png')
    report=dict(status='passed',raw_source_unchanged=True,crop_equal_to_source=True,
                crs_affine_nodata_preserved=True,tiff_binary_and_public_checksums_match=True,
                independent_real_slope_checks=len(residuals), max_slope_residual_degrees=max(residuals),
                control_placement_max_residual_m=max(p['placement_residual_m'] for p in manifest['control_points']),
                note='Georeferencing residuals are numeric consistency, not independent survey positional accuracy.')
    (ROOT/'evidence/m1/verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
