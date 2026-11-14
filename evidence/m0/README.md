# M0 evidence — 2026-11-14

Gate passed: actual numeric DEM and actual imagery are accessible, with a common proposed pilot. No synthetic data was used. Browser integration, control-point alignment, slope and routing are M1/M2 work.

## Reproduce (PowerShell, repository root)

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-data.lock.txt
.\.venv\Scripts\python.exe scripts/fetch_m0.py
.\.venv\Scripts\python.exe scripts/inspect_dem.py
.\.venv\Scripts\python.exe scripts/inspect_imagery.py --fetch
```

For an existing environment, omit `uv venv`. Initial `python -m venv .venv` failed during ensurepip on this machine; `uv pip install --python .venv/Scripts/python.exe ...` successfully populated that environment without pip. Scripts need curl.exe. Network access must be permitted; TLS validation remains enabled. Existing raw files are preserved; inspect incomplete `.part` files before explicitly removing or moving them to retry. DEM SHA256 is pinned, so a changed upstream asset fails rather than silently replacing the data.

Offline recheck after acquisition:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_m0.py
.\.venv\Scripts\python.exe scripts/inspect_dem.py
.\.venv\Scripts\python.exe scripts/inspect_imagery.py
```

All three offline commands passed on the acquired data. `fetch_m0.py` reused existing files and verified the pinned DEM checksum. Source snapshots are under this directory, raw GeoTIFF/tiles under ignored `data/raw/`. Reports and the small imagery preview are suitable for source control; the raw raster and environment are excluded. No preprocessing/resampling has been applied to the DEM.

## Verified results

- `dem-inspection.json`: 90,345,300 bytes, 4456 columns × 5067 rows × 1 float32 band, 20 m projected spacing. SHA256 `ba7f706ea1b5d63a562f28a7dcf7a7f3c79bce7f048e6974b57e8a33c30d1ba2`.
- PDS4 product `urn:nasa:pds:mars2020_ctx_basemap_2021:data:m20_ctxdem_mosaic`, version 1.0. Linked label dimensions, missing constant and radius agree with GeoTIFF. Full source citations and catalog snapshot retained; USGS catalog says public domain, cite authors (Fred Calef; label cites Mangold et al. 2021).
- Equirectangular Mars sphere radius **3,396,190 m**, standard parallel **18.4663°**, central meridian 0°. This differs from catalog radius 3,396,160 m. GeoTIFF band units absent; elevation metres are documented in catalog. MOLA vertical localization described by source; no explicit vertical CRS in GeoTIFF.
- Bounds in projected metres: west 4329000, south 1042080, east 4418120, north 1143420. Transformed bounds: 76.99743706146–78.58256332409°E, 17.58051991054–19.29018700687°N, planetocentric.
- Nodata `-3.4028234663852886e38`; 22,564,575 / 22,578,552 cells valid (99.9381%). Valid elevations −3504.6453 to −475.8408 m. Mask and finite check applied before statistics.
- Pilot native-grid window: column 1119, row 2394, width 250, height 250. Projected extent [4351380, 1090540, 4356380, 1095540] m; geographic extent **[77.39549726969, 18.39806942197, 77.48442939843, 18.48242244626]** in lon/lat order. Every cell valid; elevation −2627.2498 to −2444.9070 m. Center sample (row 2519, col 1244): −2561.0198 m.
- Pilot is 5000 × 5000 projected metres, a proposed data/demo extent, not an EVA limit. Mars spherical geodesic south edge ≈5001.985 m, west edge ≈5000 m; center parallel scale 0.9998468425. Five pixel-center → Mars lon/lat → projected → pixel roundtrips passed to <1 micrometre numerical residual. This checks transforms, not geolocation accuracy.
- `imagery-inspection.json`: Jezero CTX controlled mosaic resolved through NASA API config → catalog UUID → getLayerServices → WMTS capabilities → ResourceURL. Four real nonblank 256×256 PNG tiles decoded at matrix 11, rows 813–814, columns 2928–2929. SHA256 values and exact URLs retained. All 62,500 DEM cell centers fall on opaque imagery samples and inside source bounds. `imagery-preview.png` is a visually inspected 512×512 mosaic of those tiles, larger than the pilot.
- Tile and capabilities GET requests with `Origin: http://localhost:5173` returned `Access-Control-Allow-Origin: *`. Actual browser/CORS rendering remains an M1 check.

## WMTS integration caveat

Capabilities advertise `EPSG::104905` but have degree-valued origin [−180,90], degree-valued bounds and a 2:1 global matrix. They also call Mars bounds WGS84. At matrix 11 the grid is 4096×2048 tiles; each spans 0.087890625° and has 0.00034332275390625° pixels. The advertised OGC scale yields 38.17565 m/pixel, whereas the Mars sphere/global angular grid yields 20.35035 m/pixel at the equator. Therefore do not let a generic projected WMTS client silently infer resolution/extent from these labels. Register an explicit Mars angular tile grid and transform into DEM CRS; visually verify common control points in M1. The ResourceURL contains a double slash, preserved and tested successfully. No TileMatrixSetLimits are advertised; apply dimensions plus source coverage bounds. The controlled imagery has standard parallel 0°, unlike DEM 18.4663°.

## Access failures and remaining blocker

- Initial sandbox curl calls failed with exit 7: proxy 127.0.0.1 unreachable. Approved network execution succeeded for USGS/NASA acquisition.
- Official challenge resources URL failed Windows TLS validation: curl exit 60 `SEC_E_UNTRUSTED_ROOT`. A retry with the installed certifi bundle failed with `certificate chain is incomplete`. Web tool attempts also failed (inaccessible/502). Certificate validation was not bypassed; challenge wording, eligibility and required resource/mission counts remain unverified. This blocks final submission verification, not the M0 raster-plus-imagery gate. Recheck official page with organizers or a working trusted browser/network before submission.
- D3 not needed: primary D1/D2 acquisition succeeded. Matched 5 m orthomosaic and its label were located via USGS catalog links but not downloaded; no alternate dataset was silently substituted.
- CTX imagery and DEM are both from MRO, not two separate missions. No weather, radiation, mineral or water claims are established by this spike. 20 m sampling does not resolve astronaut-scale holes or certify any terrain or route.

## Files

Implementation: `.gitignore`, `requirements-data.txt`, `requirements-data.lock.txt`, `scripts/fetch_m0.py`, `scripts/inspect_dem.py`, `scripts/inspect_imagery.py`. Reports: `acquisition-manifest.json`, `dem-inspection.json`, `imagery-inspection.json`, `imagery-preview.png`; final offline check stdout in `dem-check.stdout.txt` and `imagery-check.stdout.txt`. Supporting source snapshots: `ctx-catalog.html`, `ctx-dem-label.xml`, `trek-api.html`, `trekApi.js`, `trek-config.json`, `trek-layers.json`, `trek-ctx-service.json`, `wmts-capabilities.xml`, `wmts-capabilities.headers.txt`, four `ctx_11_*.headers.txt`. `STATUS.md` records the milestone and next task. Original planning decisions are preserved.

Final `python -m compileall -q scripts` and `git diff --check` returned exit 0; `git check-ignore` confirmed the raw DEM and local Python environment are excluded. The added source files are still untracked, so `git diff --check` only checks tracked changes; compilation and actual data smoke runs validate the new scripts.
