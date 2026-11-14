"""M1 real-data pipeline. No downloads, terrain interpolation or Earth CRS.

Outputs are regenerable and ignored. Raw assets are read-only. Native DEM
values/transform are preserved; a 1-cell source halo supplies slope neighbors.
"""
import json
import math
import shutil
from datetime import datetime, timezone

import numpy as np
import rasterio
from PIL import Image
from pyproj import CRS, Transformer
from rasterio.windows import Window, bounds as window_bounds

from inspect_dem import ROOT, SOURCE, sha256

OUT = ROOT / 'data/processed/jezero-m1'
PUBLIC = ROOT / 'frontend/public/data'
EVIDENCE = ROOT / 'evidence/m1'
COLORS = [[62, 143, 148], [178, 179, 120], [232, 163, 79], [220, 104, 61], [157, 62, 75]]
BREAKS = [5, 10, 15, 20]


def central_slope(z, valid, east_span_m, north_span_m):
    """Return interior slope/validity; all five cross neighbors must be valid.

    Span arrays are actual horizontal distances from west to east and south
    to north neighbors, not one-pixel spacing. Invalid inputs never contribute.
    """
    valid = np.asarray(valid, dtype=bool) & np.isfinite(z)
    mask = (valid[1:-1, 1:-1] & valid[1:-1, :-2] & valid[1:-1, 2:]
            & valid[:-2, 1:-1] & valid[2:, 1:-1])
    if np.any(np.asarray(east_span_m) <= 0) or np.any(np.asarray(north_span_m) <= 0):
        raise ValueError('Horizontal distances must be positive')
    clean = np.where(valid, z, 0).astype(np.float64)
    dx = (clean[1:-1, 2:] - clean[1:-1, :-2]) / east_span_m
    dy = (clean[:-2, 1:-1] - clean[2:, 1:-1]) / north_span_m
    slope = np.rad2deg(np.arctan(np.hypot(dx, dy)))
    return np.where(mask, slope, np.nan).astype('float32'), mask


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def main():
    for directory in [OUT, PUBLIC, EVIDENCE]:
        directory.mkdir(parents=True, exist_ok=True)
    m0 = json.loads((ROOT/'evidence/m0/dem-inspection.json').read_text())
    imagery = json.loads((ROOT/'evidence/m0/imagery-inspection.json').read_text())
    if sha256(SOURCE) != m0['sha256']:
        raise ValueError('Raw DEM checksum mismatch; rerun M0 and investigate')
    col, row, width, height = map(int, m0['pilot']['window_col_row_width_height'])
    win = Window(col, row, width, height)
    with rasterio.open(SOURCE) as ds:
        crs = CRS(ds.crs)
        to_ll = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        to_xy = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        radius = crs.ellipsoid.semi_major_metre
        params = {p.name: p.value for p in crs.coordinate_operation.params}
        parallel = params['Latitude of 1st standard parallel']
        if radius != 3396190 or parallel != 18.4663:
            raise ValueError('Unexpected projection: update explicit frontend transform')
        halo = ds.read(1, window=Window(col-1, row-1, width+2, height+2), masked=True, boundless=True)
        valid_halo = ~np.ma.getmaskarray(halo) & np.isfinite(halo.data)
        valid = valid_halo[1:-1, 1:-1]
        dem = halo.data[1:-1, 1:-1].copy()
        affine = ds.window_transform(win)
        bounds = list(window_bounds(win, ds.transform))
        xx, yy = np.meshgrid(bounds[0]+(np.arange(width)+.5)*20,
                             bounds[3]-(np.arange(height)+.5)*20)
        lon, lat = to_ll.transform(xx, yy)
        lon_w, lat_w = to_ll.transform(xx-20, yy)
        lon_e, lat_e = to_ll.transform(xx+20, yy)
        lon_n, lat_n = to_ll.transform(xx, yy+20)
        lon_s, lat_s = to_ll.transform(xx, yy-20)
        geod = crs.get_geod()
        _, _, east_span = geod.inv(lon_w, lat_w, lon_e, lat_e)
        _, _, north_span = geod.inv(lon_s, lat_s, lon_n, lat_n)
        slope, slope_valid = central_slope(halo.data, valid_halo, east_span, north_span)
        profile = dict(driver='GTiff', width=width, height=height, count=1,
                       crs=ds.crs, transform=affine, compress='deflate')
        with rasterio.open(OUT/'dem.tif', 'w', **profile, dtype='float32', nodata=ds.nodata) as dst:
            dst.write(np.where(valid, dem, ds.nodata).astype('float32'), 1)
            dst.set_band_unit(1, 'm')
        with rasterio.open(OUT/'slope.tif', 'w', **profile, dtype='float32', nodata=-9999) as dst:
            dst.write(np.where(slope_valid, slope, -9999).astype('float32'), 1)
            dst.set_band_unit(1, 'degree')
        for filename, mask in [('valid-mask.tif', valid), ('slope-mask.tif', slope_valid)]:
            with rasterio.open(OUT/filename, 'w', **profile, dtype='uint8') as dst:
                dst.write(mask.astype('uint8'), 1)
    # Row-major little-endian binary arrays; browser reads Float32/Uint8 data.
    np.where(valid, dem, np.nan).astype('<f4').tofile(OUT/'elevation.f32')
    slope.astype('<f4').tofile(OUT/'slope.f32')
    valid.astype('uint8').tofile(OUT/'valid.u8')
    slope_valid.astype('uint8').tofile(OUT/'slope-valid.u8')
    rgba = np.zeros((height, width, 4), dtype='uint8')
    for index, color in enumerate(COLORS):
        rgba[np.searchsorted(BREAKS, slope, side='right') == index, :3] = color
    rgba[:, :, 3] = np.where(slope_valid, 235, 0)
    Image.fromarray(rgba).save(OUT/'slope.png')
    # Stitch cached real tiles. Both equirectangular transforms are separable
    # linear x/y functions of lon/lat; transforming extent is exact here.
    tiles = imagery['tiles']
    r0, r1 = min(t['row'] for t in tiles), max(t['row'] for t in tiles)
    c0, c1 = min(t['col'] for t in tiles), max(t['col'] for t in tiles)
    tile_size = imagery['matrix']['tile_width']
    mosaic = Image.new('RGBA', ((c1-c0+1)*tile_size, (r1-r0+1)*tile_size))
    for tile in tiles:
        path = ROOT/tile['local_path']
        if sha256(path) != tile['sha256']:
            raise ValueError(f'Imagery checksum mismatch: {path.name}')
        with Image.open(path) as im:
            mosaic.paste(im.convert('RGBA'), ((tile['col']-c0)*tile_size, (tile['row']-r0)*tile_size))
    mosaic.save(OUT/'imagery.png')
    dx, dy = imagery['matrix']['tile_span_degrees']
    image_ll = [-180+c0*dx, 90-(r1+1)*dy, -180+(c1+1)*dx, 90-r0*dy]
    image_bounds = list(to_xy.transform_bounds(*image_ll))
    controls = []
    for s in m0['samples']:
        rr, cc = s['row']-row, s['col']-col
        x, y = affine*(cc+.5, rr+.5)
        ll = to_ll.transform(x, y)
        # Independently use angular tile pixels, then image extent placement.
        px = (ll[0]-image_ll[0])/(image_ll[2]-image_ll[0])*mosaic.width
        py = (image_ll[3]-ll[1])/(image_ll[3]-image_ll[1])*mosaic.height
        ix = image_bounds[0]+px/mosaic.width*(image_bounds[2]-image_bounds[0])
        iy = image_bounds[3]-py/mosaic.height*(image_bounds[3]-image_bounds[1])
        residual = math.hypot(ix-x, iy-y)
        assert residual < 1e-6 and np.isclose(dem[rr, cc], s['elevation_m'])
        controls.append(dict(row=rr, col=cc, x_m=x, y_m=y, lonlat=list(ll),
                             imagery_pixel=[px, py], placement_residual_m=residual,
                             elevation_m=float(dem[rr, cc]), slope_deg=float(slope[rr, cc])))
    manifest = dict(schema_version=1, status='derived', generated_utc=datetime.now(timezone.utc).isoformat(),
                    width=width, height=height, affine=list(affine)[:6], bounds_m=bounds,
                    bounds_lonlat=m0['pilot']['geographic_bounds_lonlat'],
                    crs=dict(code='MARS:JEZERO', wkt=crs.to_wkt(), radius_m=radius, standard_parallel_deg=parallel,
                             central_meridian_deg=0, axis_order='easting,northing in metres; geographic positive-east longitude,planetocentric latitude in degrees'),
                    imagery_bounds_m=image_bounds, imagery_bounds_lonlat=image_ll,
                    imagery_size=[mosaic.width, mosaic.height],
                    statistics=dict(valid_elevation_cells=int(valid.sum()), valid_slope_cells=int(slope_valid.sum()),
                                    elevation_range_m=[float(dem[valid].min()), float(dem[valid].max())],
                                    slope_range_deg=[float(slope[slope_valid].min()), float(slope[slope_valid].max())],
                                    slope_percentiles_deg=np.percentile(slope[slope_valid], [50, 90, 99]).tolist()),
                    slope_method='Central differences on native grid with 1-cell source halo. dzdx=(zE-zW)/Mars-geodesic-distance(W,E), dzdy=(zN-zS)/Mars-geodesic-distance(S,N); slope=atan(hypot(dzdx,dzdy)) in degrees. Center plus four neighbors must be valid. No filling or terrain resampling.',
                    horizontal_neighbor_span_m=dict(east_range=[float(east_span.min()), float(east_span.max())],
                                                    north_range=[float(north_span.min()), float(north_span.max())]),
                    legend=dict(breaks_deg=BREAKS, colors=COLORS, labels=['<5°', '5–10°', '10–15°', '15–20°', '≥20°']),
                    encoding='Binary arrays row-major from northwest, float32 little endian (NaN missing), uint8 masks (1 valid, 0 invalid). TIFF slope missing=-9999.',
                    sources=dict(dem={k:m0[k] for k in ['source_url', 'sha256', 'product_id', 'product_version', 'publication_date', 'citation', 'license', 'vertical_reference', 'local_download_completed_utc']},
                                 imagery={k:imagery[k] for k in ['layer', 'citation', 'license', 'matrix', 'template', 'tiles']}),
                    control_points=controls, versions=m0['versions'],
                    limitations=['20 m DEM sampling cannot resolve astronaut-scale holes or certify travel.',
                                 'Slope is a derived terrain metric, not a safety classification.',
                                 'Pilot is a proposed demo extent, not a mission travel limit.',
                                 'Alignment checks verify georeferencing and relative terrain structure, not survey accuracy.',
                                 'Cached imagery only within the shown footprint; no live weather, radiation or resource availability.'])
    files = ['dem.tif', 'slope.tif', 'valid-mask.tif', 'slope-mask.tif', 'elevation.f32', 'slope.f32',
             'valid.u8', 'slope-valid.u8', 'slope.png', 'imagery.png']
    manifest['outputs'] = {name:dict(sha256=sha256(OUT/name), bytes=(OUT/name).stat().st_size) for name in files}
    write_json(OUT/'manifest.json', manifest)
    for name in files+['manifest.json']:
        shutil.copyfile(OUT/name, PUBLIC/name)
    write_json(EVIDENCE/'pipeline-report.json', manifest)
    print(json.dumps(dict(outputs=str(OUT), statistics=manifest['statistics'],
                          max_control_placement_residual_m=max(c['placement_residual_m'] for c in controls)), indent=2))


if __name__ == '__main__':
    main()
