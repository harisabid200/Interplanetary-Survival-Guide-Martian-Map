"""M0: inspect the real CTX DEM and validate a native-grid pilot (no resampling)."""
import hashlib
import json
import platform
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyproj
import rasterio
from pyproj import CRS, Transformer, Proj
from rasterio.windows import Window, bounds as window_bounds

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/M20_JezeroCrater_CTXDEM_20m.tif'
OUT = ROOT / 'evidence/m0'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(SOURCE) as ds:
        crs = CRS(ds.crs)
        assert ds.count == 1 and ds.dtypes == ('float32',)
        assert ds.res == (20, 20) and ds.transform.b == ds.transform.d == 0
        assert crs.ellipsoid.semi_major_metre == 3396190
        assert crs.ellipsoid.semi_minor_metre == 3396190
        label = ET.parse(OUT / 'ctx-dem-label.xml').getroot()
        ns = {'c': 'http://pds.nasa.gov/pds4/cart/v1', 'p': 'http://pds.nasa.gov/pds4/pds/v1'}
        label_radius = float(label.findtext('.//c:a_axis_radius', namespaces=ns))
        assert label_radius == crs.ellipsoid.semi_major_metre
        axes = {a.findtext('p:axis_name', namespaces=ns): int(a.findtext('p:elements', namespaces=ns))
                for a in label.findall('.//p:Axis_Array', ns)}
        assert axes == {'Band': ds.count, 'Line': ds.height, 'Sample': ds.width}
        assert float(label.findtext('.//p:missing_constant', namespaces=ns)) == ds.nodata
        to_xy = Transformer.from_crs(crs.geodetic_crs, crs, always_xy=True)
        to_ll = Transformer.from_crs(crs, crs.geodetic_crs, always_xy=True)
        band = ds.read(1, masked=True)
        valid = ~np.ma.getmaskarray(band) & np.isfinite(band.data)
        values = band.data[valid]
        assert values.size and -15000 < float(values.min()) < float(values.max()) < 30000
        # Proposed western Jezero pilot near landing-site/delta area; not an EVA limit.
        center_lon, center_lat = 77.44, 18.44
        x, y = to_xy.transform(center_lon, center_lat)
        row, col = ds.index(x, y)
        win = Window(col - 125, row - 125, 250, 250)
        assert win.col_off >= 0 and win.row_off >= 0
        assert win.col_off + win.width <= ds.width and win.row_off + win.height <= ds.height
        pilot_valid = valid[row-125:row+125, col-125:col+125]
        assert pilot_valid.shape == (250, 250) and pilot_valid.all(), 'Pilot contains missing data'
        pilot = band.data[row-125:row+125, col-125:col+125]
        west, south, east, north = window_bounds(win, ds.transform)
        corners = [to_ll.transform(xx, yy) for xx, yy in
                   [(west, south), (east, south), (east, north), (west, north)]]
        samples = []
        for rr, cc in [(row, col), (row-124, col-124), (row+124, col+124),
                       (row-124, col+124), (row+124, col-124)]:
            xx, yy = ds.xy(rr, cc)
            lon, lat = to_ll.transform(xx, yy)
            tx, ty = to_xy.transform(lon, lat)
            assert ds.index(tx, ty) == (rr, cc)
            assert np.hypot(tx-xx, ty-yy) < 1e-6
            samples.append(dict(row=rr, col=cc, x_m=xx, y_m=yy, lon_east_deg=lon,
                                lat_planetocentric_deg=lat, elevation_m=float(band[rr, cc])))
        geod = crs.get_geod()
        _, _, width_m = geod.inv(*corners[0], *corners[1])
        _, _, height_m = geod.inv(*corners[0], *corners[3])
        factors = Proj(crs).get_factors(center_lon, center_lat)
        report = dict(
            generated_utc=datetime.now(timezone.utc).isoformat(), status='validated',
            source_url='https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif',
            local_path=str(SOURCE.relative_to(ROOT)).replace('\\', '/'),
            bytes=SOURCE.stat().st_size, sha256=sha256(SOURCE),
            local_download_completed_utc=datetime.fromtimestamp(SOURCE.stat().st_mtime, timezone.utc).isoformat(),
            pds4_label_checks='Dimensions, nodata and Mars radius agree with actual GeoTIFF',
            product_id='urn:nasa:pds:mars2020_ctx_basemap_2021:data:m20_ctxdem_mosaic',
            product_version='1.0', mission='Mars Reconnaissance Orbiter', instrument='CTX',
            publisher='USGS Astrogeology / NASA PDS', publication_year=2021,
            publication_date='2021-10-14 (USGS catalog)',
            acquisition_time=None, acquisition_time_note='PDS4 label marks times inapplicable',
            citation='Mangold et al. (2021), Science, doi:10.1126/science.abl4051 (PDS4 label citation); catalog originator Fred Calef / PDS',
            license='Public Domain (USGS catalog)',
            dimensions=dict(width=ds.width, height=ds.height, bands=ds.count),
            dtype=ds.dtypes[0], crs_wkt=ds.crs.to_wkt(), crs_projjson=crs.to_json_dict(),
            affine=list(ds.transform)[:6], pixel_size_projected_m=list(ds.res),
            projected_bounds_m=list(ds.bounds), geographic_bounds_lonlat=list(to_ll.transform_bounds(*ds.bounds)),
            nodata=ds.nodata, mask_flags=[str(f) for f in ds.mask_flag_enums[0]],
            valid_cells=int(valid.sum()), total_cells=int(valid.size),
            valid_fraction=float(valid.mean()), valid_min_m=float(values.min()), valid_max_m=float(values.max()),
            valid_percentiles_m=np.percentile(values, [0, 25, 50, 75, 100]).tolist(),
            band_units=ds.units[0], elevation_units='metres per USGS catalog; GeoTIFF band unit absent',
            vertical_reference='Catalog: localized vertically to MOLA; no explicit vertical CRS in GeoTIFF',
            raster_tags=ds.tags(), samples=samples,
            pilot=dict(status='DEM validated; imagery overlap checked separately',
                       proposed_center_lonlat=[center_lon, center_lat], window_col_row_width_height=list(win.flatten()),
                       projected_bounds_m=[west, south, east, north], corners_lonlat=corners,
                       geographic_bounds_lonlat=[min(c[0] for c in corners), min(c[1] for c in corners),
                                                max(c[0] for c in corners), max(c[1] for c in corners)],
                       valid_cells=int(pilot_valid.sum()), total_cells=int(pilot_valid.size),
                       min_elevation_m=float(pilot.min()), max_elevation_m=float(pilot.max()),
                       projected_width_height_m=[east-west, north-south],
                       mars_geodesic_south_width_west_height_m=[width_m, height_m],
                       center_parallel_scale=factors.parallel_scale, center_meridional_scale=factors.meridional_scale),
            limitations=['20 m sampling cannot resolve astronaut-scale holes or establish safe travel',
                         'Catalog radius 3396160 m conflicts with raster and PDS4 label 3396190 m; use raster CRS',
                         'No terrain interpolation, slope generation or route analysis performed in M0'],
            processing=['Read full band and combine GDAL nodata mask with finite-value check',
                        'Choose native-grid 250x250 pilot, verify every cell and five coordinate roundtrips'],
            versions=dict(python=platform.python_version(), rasterio=rasterio.__version__,
                          gdal=rasterio.__gdal_version__, numpy=np.__version__, pyproj=pyproj.__version__,
                          proj=pyproj.proj_version_str))
    (OUT / 'dem-inspection.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['bytes', 'sha256', 'valid_fraction', 'valid_min_m', 'valid_max_m', 'pilot', 'samples']}, indent=2))


if __name__ == '__main__':
    main()
