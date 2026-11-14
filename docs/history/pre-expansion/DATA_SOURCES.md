# DATA SOURCES — Jezero Crater

Catalog pages and the CTX direct URL below were located in web research on 2026-11-14. Actual file downloads, raster contents, endpoint CORS, and overlap have NOT been tested. Catalog verified is not runtime verified. Verify eligibility against the official challenge resources.

## D1 — first numerical DEM (catalog verified)
USGS Astrogeology / MRO Context Camera stereo, Mars 2020 Science Investigation CTX DEM Mosaic (2021). 20 m/pixel; elevation metres; catalog covers Jezero crater; 87 MB listed. Public domain, cite authors. Catalog names Fred Calef and PDS as originator; consult full label for proper attribution.
- Catalog: https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic
- Direct GeoTIFF: https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif
- Catalog extent approximately lon 76.99–78.58 E, lat 17.58–19.29 N (catalog min/max latitude fields appear reversed; verify actual raster). Equirectangular, planetocentric latitude, positive-east longitude; catalog sphere radius 3396160 m. Read actual CRS rather than hard-code.
- Matched 5 m orthomosaic referenced by catalog; locate exact downloadable asset through catalog links/labels, not a guessed URL.

## D2 — NASA Mars Trek imagery (catalog verified)
API: https://trek.nasa.gov/tiles/apidoc/trekAPI.html?body=mars
Viewer: https://trek.nasa.gov/mars/
- CTX Jezero Controlled: `JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0` (catalog bounds 77.1604655,18.2110274,77.6991776,18.7211945; projected equirectangular).
- HiRISE Jezero Controlled: `JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first_dd` (catalog bounds 77.2229331,18.3067994,77.583964,18.669315; geographic).
- Obtain WMTS endpoints from catalog Show/Capabilities; parse tile matrix, style, projection and limits. Do not invent XYZ URLs. Check actual tile rendering and CORS. These layers are imagery, not numeric DEM. If blocked, preprocess a verified local orthomosaic into static images or local tiles with georeferencing.

## D3 — high resolution terrain (catalog verified, optional upgrade)
USGS Mars 2020 HiRISE DTM mosaic, 2020: https://www.usgs.gov/data/mars-2020-terrain-relative-navigation-hirise-dtm-mosaic ; DOI https://doi.org/10.5066/P9REJ9JN . Nominal 1 m DTM and 25 cm imagery products; check actual asset and footprint. CC0. Broader landing site catalog: https://astrogeology.usgs.gov/search/map/mars-2020-jezero-crater-landing-site-products . New western extension: https://doi.org/10.5066/P13CPYYU (2025). Do not download all gigabytes unless justified; crop a pilot. Higher sampling resolution is not guaranteed obstacle detection.

## D4 — science context (candidate; assets not verified)
- USGS geological map of Jezero and Nili Planum (SIM 3464), locate via https://astrogeology.usgs.gov/ . Check vector availability and scale; geological unit does not imply confirmed water resource.
- CRISM mineral observations and coverage: https://pds.nasa.gov/ ; https://ode.rsl.wustl.edu/mars/ ; https://murray-lab.caltech.edu/Mars2020/index.html (coverage resources). Coverage polygons alone do not establish mineral presence.
- Perseverance observations through NASA PDS; use published coordinates/observations only. MEDA is local historical weather, not live regional forecast. Curiosity RAD is Gale Crater context, not Jezero point radiation. Dust/storm and communications require independent validated data/models; disable quantitative local estimates until available.
- MOLA global terrain: https://pds-geosciences.wustl.edu/missions/mgs/megdr.html ; broad context only, not local obstacle routing.

## Required preprocessing
1. Download, record source URL/time, file hash and product label; run `gdalinfo -json` or Rasterio inspection. Verify CRS, affine, units, pixel size, dimensions, mask/nodata, extent and plausible numeric samples.
2. Transform all footprints into common Mars coordinates and choose pilot intersection. Crop in projected metres; preserve CRS and nodata. Align analytical rasters; use nearest-neighbor for categorical layers. No Earth CRS shortcuts.
3. Derive slope using elevation gradient and true horizontal metres in local projected grid; check projection scale and use masks around missing neighbors. Keep native resolution or document resampling.
4. Generate lightweight outputs and manifest: product ID, instrument/mission, publisher, source URL, publication/acquisition dates if known, resolution, CRS, extent, units, nodata, license, checksum, processing steps and status (`catalog`, `downloaded`, `validated`, `derived`, `unavailable`). Show provenance in UI.

Example download (run in repo root, not yet tested):
```sh
mkdir -p data/raw
curl -fL --retry 2 -o data/raw/jezero_ctx_dem.tif https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif
gdalinfo -json data/raw/jezero_ctx_dem.tif
```
On Windows use curl.exe and create directory with PowerShell if necessary. Validate the returned file rather than assuming HTTP success means valid GeoTIFF.
