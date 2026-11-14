"""Resolve WMTS grid from saved capabilities; fetch real pilot tiles with --fetch.

The service advertises degree-valued origins despite a projected CRS identifier.
Use its global 2:1 matrix, record the inconsistency, never feed these numbers
to an Earth Web Mercator grid or blindly trust ScaleDenominator.
"""
import argparse
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np
from PIL import Image

from inspect_dem import ROOT, OUT, sha256

NS = {'w': 'http://www.opengis.net/wmts/1.0', 'o': 'http://www.opengis.net/ows/1.1'}
LAYER = 'JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0'


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--fetch', action='store_true')
    fetch = args.parse_args().fetch
    root = ET.parse(OUT / 'wmts-capabilities.xml').getroot()
    layer = root.find('w:Contents/w:Layer', NS)
    assert layer.findtext('o:Identifier', namespaces=NS) == LAYER
    style = layer.findtext('w:Style/o:Identifier', namespaces=NS)
    matrixset = root.find('w:Contents/w:TileMatrixSet', NS)
    set_id = matrixset.findtext('o:Identifier', namespaces=NS)
    matrices = matrixset.findall('w:TileMatrix', NS)
    grid = next(m for m in matrices if m.findtext('o:Identifier', namespaces=NS) == '11')
    def number(key):
        return float(grid.findtext('w:'+key, namespaces=NS))
    cols, rows = int(number('MatrixWidth')), int(number('MatrixHeight'))
    tw, th = int(number('TileWidth')), int(number('TileHeight'))
    origin = list(map(float, grid.findtext('w:TopLeftCorner', namespaces=NS).split()))
    assert origin == [-180, 90] and cols == rows*2 and tw == th == 256
    dx, dy = 360/cols, 180/rows
    lower = list(map(float, layer.findtext('o:BoundingBox/o:LowerCorner', namespaces=NS).split()))
    upper = list(map(float, layer.findtext('o:BoundingBox/o:UpperCorner', namespaces=NS).split()))
    dem = json.loads((OUT / 'dem-inspection.json').read_text())
    catalog = json.loads((OUT / 'trek-layers.json').read_text())['response']['docs']
    source = next(d for d in catalog if d['productLabel'] == LAYER)
    west, south, east, north = dem['pilot']['geographic_bounds_lonlat']
    assert lower[0] <= west < east <= upper[0] and lower[1] <= south < north <= upper[1]
    c0, c1 = math.floor((west+180)/dx), math.floor((east+180)/dx)
    r0, r1 = math.floor((90-north)/dy), math.floor((90-south)/dy)
    resource = layer.find('w:ResourceURL', NS).attrib['template']
    mosaic = Image.new('RGBA', ((c1-c0+1)*tw, (r1-r0+1)*th))
    records = []
    for row in range(r0, r1+1):
        for col in range(c0, c1+1):
            url = resource
            for key, value in dict(Style=style, TileMatrixSet=set_id, TileMatrix=11, TileRow=row, TileCol=col).items():
                url = url.replace('{'+key+'}', str(value))
            dest = ROOT / f'data/raw/ctx_11_{row}_{col}.png'
            header = OUT / f'ctx_11_{row}_{col}.headers.txt'
            if fetch and not dest.exists():
                part = dest.with_suffix('.png.part')
                if part.exists():
                    raise FileExistsError(f'Inspect/remove incomplete download first: {part}')
                subprocess.run(['curl.exe', '-fL', '--retry', '2', '--connect-timeout', '20', '--max-time', '60',
                                '-H', 'Origin: http://localhost:5173', '-D', str(header), '-o', str(part), url], check=True)
                with Image.open(part) as test:
                    test.load()
                    assert test.size == (tw, th)
                part.rename(dest)
            with Image.open(dest) as im:
                im.load()
                assert im.size == (tw, th) and im.format == 'PNG'
                rgba = im.convert('RGBA')
                assert np.asarray(rgba)[:, :, :3].std() > 0, 'Blank image tile'
                mosaic.paste(rgba, ((col-c0)*tw, (row-r0)*th))
            headers = header.read_text()
            cors = [line for line in headers.splitlines() if line.lower().startswith('access-control-allow-origin:')]
            records.append(dict(url=url, local_path=str(dest.relative_to(ROOT)).replace('\\', '/'),
                                sha256=sha256(dest), bytes=dest.stat().st_size, row=row, col=col,
                                cors_headers=cors, modified_utc=datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).isoformat()))
    # Check nearest imagery alpha at every native DEM pilot-cell center.
    from pyproj import CRS, Transformer
    crs = CRS(dem['crs_wkt'])
    to_ll = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
    pw, ps, pe, pn = dem['pilot']['projected_bounds_m']
    xx, yy = np.meshgrid(np.arange(pw+10, pe, 20), np.arange(pn-10, ps, -20))
    lon, lat = to_ll.transform(xx, yy)
    px = np.floor(((lon+180)/dx-c0)*tw).astype(int)
    py = np.floor(((90-lat)/dy-r0)*th).astype(int)
    alpha = np.asarray(mosaic)[:, :, 3][py, px]
    assert (alpha == 255).all(), 'Imagery missing at pilot DEM cell centers'
    mosaic.save(OUT / 'imagery-preview.png')
    scale = number('ScaleDenominator')
    report = dict(status='validated', generated_utc=datetime.now(timezone.utc).isoformat(),
                  publisher='NASA/JPL Mars Trek; source product USGS Astrogeology',
                  mission=source['mission'], instrument=source['instrument'],
                  catalog_created_date=source['data_created_date'], acquisition_date=None,
                  citation='Fergason et al. (2020), Mars 2020 Terrain Relative Navigation Flight Product Generation, doi:10.5066/P906QQT8; NASA Mars Trek layer '+LAYER,
                  source_projection_wkt=source['projection'],
                  license='No license field in retrieved WMTS/catalog response; retain NASA/USGS attribution and verify source use terms before submission',
                  layer=LAYER, style=style, matrix_set=set_id, supported_crs=matrixset.findtext('o:SupportedCRS', namespaces=NS),
                  catalog_projection='Mars sphere 3396190 m, equirectangular standard parallel 0',
                  axis_order='service tile grid x=positive-east longitude, y=planetocentric latitude; origin west,north',
                  source_bounds_lonlat=lower+upper, template=resource,
                  matrix=dict(id='11', width=cols, height=rows, tile_width=tw, tile_height=th,
                              origin_lonlat=origin, tile_span_degrees=[dx, dy],
                              degrees_per_pixel=[dx/tw, dy/th], advertised_scale_denominator=scale,
                              advertised_metres_per_pixel_at_0_28mm=scale*0.00028,
                              mars_equatorial_metres_per_pixel=2*math.pi*3396190/(cols*tw)),
                  tile_matrix_limits='None advertised; enforce matrix dimensions and catalog coverage',
                  pilot_dem_cells_with_opaque_imagery=int((alpha == 255).sum()), pilot_dem_cells=int(alpha.size),
                  pilot_common_bounds_lonlat=[west, south, east, north], tiles=records,
                  limitations=['Capabilities CRS/bounding-box labels and scale denominator are inconsistent with the degree-valued global grid; use explicit degree grid and custom Mars transform in M1',
                               'Opaque imagery samples establish data access, not positional accuracy; visual control-point alignment remains M1',
                               'HTTP CORS headers checked; no browser integration tested in M0',
                               'ResourceURL double slash preserved exactly as advertised and successfully tested'])
    (OUT / 'imagery-inspection.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
