# MARSWALK · Jezero mission control

NASA Space Apps 2026 planning prototype with core Environmental, Scientific and Mission Intelligence. M0–M5 include verified geology, partial-coverage CRISM D2300 spectral index, cited ancient-lakeshore context and SIM 3464 mapped small-crater point stops. These points are optional user selections, not rankings or safety-qualified sites; source positional uncertainty is disclosed. CTX imagery/DEM/slope, deterministic routing, mission-control UI/API, historical MEDA series, dated MARCI context, Gale-only RAD reference and THEMIS thermal-inertia map are available. CRISM is an observed spectral parameter, not mineral identification or resource mapping. No live weather, numeric RAD dose, measured Jezero ionizing radiation, water resources or travel-safety claims.

## Run locally (PowerShell)

The current workspace has the acquired data, installed packages and built frontend. Start the combined UI/API from repository root:

```powershell
.\.venv\Scripts\python.exe -m backend.server
```

Open http://127.0.0.1:8000. The initial map view shows about 7.5 by 7.5 km of real NASA/JPL Mars Trek / USGS CTX imagery. The default Terrain coverage is the original 5 by 5 km DEM and route region. Use the Terrain coverage selector in the left sidebar to choose Expanded 7.5 by 7.5 km; the dashed boundary then encloses a second verified native 20 m DEM, slope and route grid. Expanded mode also loads source-derived SIM 3464 geology (19 intersecting polygons), CRISM D2300 (38.4% valid grid cells; remaining cells stay transparent), and THEMIS thermal inertia (native 100 m pixels covering the expanded terrain). Their units, footprint and limits remain shown in the UI. Imagery beyond the dashed boundary is imagery only. Fit terrain / Wider view changes the viewport, not data coverage. The basemap is a 2048 by 2048 mosaic from 64 zoom-13 tiles (about 5.09 m tile spacing at the equator; nominal source imagery about 6 m); this visual detail and expanded crop do not improve native DEM resolution. Slope shading starts off. Pick start/destination on the map or enter Mars coordinates, choose distance/terrain priority, then Compare routes. Load verification pair reproduces test selections, not designated science sites. CRISM D2300 is a dimensionless observed parameter with valid pixels over about 45% of the 5 km pilot, not mineral identification, concentration, resource, water or safety. Geological features shows USGS SIM 3464 units at 1:75,000 with disclosed 100-200 m random registration offsets. Temperature and weather opens historical MEDA sol 15 observations; MARCI dust context and the Gale-only radiation reference remain separate panels. No unsupported environmental overlay is painted. Restart an already-running backend after updating code or preprocessing.

Fresh setup from repository root requires Python 3.13, uv, Node 22.12+ (tested 22.21.0), npm, curl.exe and internet access:

```powershell
uv venv --python 3.13 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-data.lock.txt
uv pip install --python .venv/Scripts/python.exe -r requirements-api.lock.txt
.\.venv\Scripts\python.exe scripts/fetch_m0.py
.\.venv\Scripts\python.exe scripts/inspect_dem.py
.\.venv\Scripts\python.exe scripts/inspect_imagery.py --fetch
.\.venv\Scripts\python.exe scripts/preprocess.py
.\.venv\Scripts\python.exe scripts/preprocess_expanded.py
.\.venv\Scripts\python.exe scripts/build_detail_basemap.py --fetch
.\.venv\Scripts\python.exe scripts/fetch_environment.py --sol 15
.\.venv\Scripts\python.exe scripts/preprocess_environment.py
.\.venv\Scripts\python.exe scripts/environment_map.py --fetch
.\.venv\Scripts\python.exe scripts/fetch_sim3464.py
.\.venv\Scripts\python.exe scripts/build_geology.py
.\.venv\Scripts\python.exe scripts/fetch_crism_candidate.py
.\.venv\Scripts\python.exe scripts/build_crism_overlay.py
.\.venv\Scripts\python.exe scripts/build_geology.py --region data/processed/jezero-expanded-7p5km/manifest.json --output frontend/public/data/expanded/geology --processed data/processed/jezero-expanded-7p5km/geology --evidence evidence/map-expansion/geology
.\.venv\Scripts\python.exe scripts/build_crism_overlay.py --region data/processed/jezero-expanded-7p5km/manifest.json --output data/processed/jezero-expanded-7p5km/crism --public frontend/public/data/expanded/crism
.\.venv\Scripts\python.exe scripts/environment_map.py --region data/processed/jezero-expanded-7p5km/manifest.json --output data/processed/jezero-expanded-7p5km/environment-map --public frontend/public/data/expanded/environment-map --evidence evidence/map-expansion/environment-map
.\.venv\Scripts\python.exe scripts/build_science_destinations.py
.\.venv\Scripts\python.exe scripts/build_science_destinations.py --region data/processed/jezero-m1/manifest.json --output frontend/public/data/science-destinations
.\.venv\Scripts\python.exe scripts/verify_science_destinations.py
npm.cmd ci --prefix frontend
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m backend.server
```

Raw source assets are ignored and never overwritten by these scripts. Inspect existing `.part` files after an interrupted download before retrying. A changed source checksum stops processing. Generated products live in ignored `data/processed/jezero-m1/` and `data/processed/jezero-expanded-7p5km/`, copied into matching paths under ignored `frontend/public/data/` for the static app. Do not hand-edit generated files. M0 sources and exact URLs are in [the acquisition report](evidence/m0/README.md).

Development with live reload: run `.\.venv\Scripts\python.exe -m backend.server` in one terminal and `npm.cmd run dev --prefix frontend` in another; open http://127.0.0.1:5173. Vite proxies `/api` to the loopback backend. Rebuild after frontend edits for the combined server. If the API is unavailable, the standalone Vite terrain inspector remains usable and planning shows a reconnect/error state. For terrain/CLI-only setup, the original `requirements-data.lock.txt` remains unchanged; the API has its own pinned lock file.

If port 5173 shows `Unexpected token '<'` or reports a page instead of API data, stop that frontend terminal with Ctrl+C and rerun `npm.cmd run dev --prefix frontend`. Keep the Python server on port 8000 running. Restart is necessary for an older process that did not load the API proxy. Then hard-refresh port 5173 and choose **Reconnect routing** if shown. The Compare button enables only after the API connection and dataset identity check pass. `/api/region` on port 5173 must return JSON, not the frontend HTML page. The dev command now explicitly loads `frontend/vite.config.js` and its fixed project root/proxy.

## Validation

Run from repository root after preprocessing:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
$env:MARSWALK_EVIDENCE_STAGE='environment-map'
$env:MARSWALK_API_PORT='8001'
npm.cmd run test:browser --prefix frontend
.\.venv\Scripts\python.exe scripts/verify_m4.py
.\.venv\Scripts\python.exe scripts/verify_science_destinations.py
Remove-Item Env:MARSWALK_API_PORT
Remove-Item Env:MARSWALK_EVIDENCE_STAGE
```

The suite contains 60 Python tests, 9 JS tests and 25 Chrome cases including the M1 map, mission routing, environmental panels, SIM 3464, CRISM, science-stop selection and detailed-basemap scenarios. Current expansion checks: all 60 Python tests, all 9 JS tests, all 25 Chrome tests, source/region/hash audit, expanded API route/hash smoke and production build passed. Commands above use isolated test ports; an existing application on 8000 is preserved. These test ports must be free. Chrome must already be installed. Current screenshots/evidence are in `evidence/map-upgrade/`, `evidence/map-expansion/` and `evidence/m5/`; prior M0–M4 evidence remains preserved. `verify_m4.py` independently audits real routes, confirms unchanged M2 engine/M1 identity and previous evidence, and rebuilds the environmental artifact deterministically. Clear the test environment variables afterward so normal development continues to proxy to 8000. Original milestone verification scripts remain available; they regenerate their own milestone evidence when deliberately rerun. Synthetic fixtures remain confined to tests.

## Run real terrain routes (M2)

From the repository root, after preprocessing:

```powershell
.\.venv\Scripts\python.exe -m backend.cli --start 77.44014119831834 18.44007722806572 --end 77.39603086246426 18.48191632811385 --terrain-weight 100
```

This retained M2 CLI compares objectives between two verification cells, not designated mission sites. It prints actual Mars geometry, horizontal distance, ascent/descent, sampled segment/local cell slopes, full elevation profile, coverage, assumptions and provenance. Add `--max-cell-slope-deg 20` for an assumed local-cell exclusion, or `--output data/processed/my-route.json` to create a new result; existing files are never overwritten. Invalid/nodata/outside endpoints are errors; disconnected valid endpoints return no-path without geometry. The M3 UI/API uses this same engine; see [API contract](backend/API.md).

The real audited example gives 3507.3 m / 13.30° max segment slope for distance and 3964.3 m / 8.69° for terrain (weight 100). Both use actual Mars geodesic edge lengths and the same valid mask, with no diagonal corner cutting. A* costs match Dijkstra. See [model/interface](backend/ROUTING.md), [M2 evidence](evidence/m2/README.md) and [actual route preview](evidence/m2/routes-preview.png).

## Scientific processing

The actual DEM is equirectangular on a Mars sphere of radius **3,396,190 m**, standard parallel **18.4663°**, central meridian 0°. Frontend transforms explicitly use those spherical equations and register a custom OpenLayers projection. No Earth Web Mercator or Earth distance helpers are used.

The 250×250 native crop is 5×5 km in projected metres near 77.44°E, 18.44°N. It is a proposed demo extent, not an EVA limit. Crop row/column indices start at zero in the northwest; selected coordinates snap to cell centers. West/north edges are included, east/south edges excluded. Points outside coverage and nodata are rejected rather than clamped or filled.

Slope uses central differences with a one-cell source halo. East/west and north/south elevation differences are divided by the actual Mars spherical geodesic distances between the neighboring cell centers. Slope is `atan(hypot(dzdx,dzdy))`, in degrees. Center and all four neighbors must be valid. Missing terrain is never interpolated. Color bins are presentation choices, not operational thresholds.

Imagery comes from the M0 capabilities-derived CTX tiles, stitched without resampling. Their angular extent transforms exactly into this DEM's equirectangular grid because both use the same sphere and linear longitude/latitude axes. The frontend displays the resulting cached image with that explicit georeferencing, avoiding the inconsistent WMTS CRS/scale labels. Cached matrix 11 is ~20.35 m/pixel at the equator; this differs from the nominal ~6 m source imagery sampling. Terrain and imagery are shown with nearest-neighbor rendering; numerical samples use native cells.

See [M1 evidence](evidence/m1/README.md) for actual results and limits, [STATUS.md](STATUS.md) for milestones, and the generated manifest for source IDs, checksums, method and output hashes. Georeferencing checks are numerical consistency checks, not survey positional accuracy. Twenty-metre sampling cannot resolve astronaut-scale holes or certify travel.

Expanded scope, source details and earlier implementation results remain in [M3 evidence](evidence/m3/README.md) and [DATA_SOURCES.md](DATA_SOURCES.md). [M4 evidence](evidence/m4/README.md) documents actual MEDA import, 7.4-hour observation gaps, absent per-row quality flags, excluded pressure-uncertainty label anomaly, native landing-site-relative positions, dated MARCI context and unavailable numeric RAD dose. [M5 evidence](evidence/m5/README.md) documents actual SIM 3464 destination points and CRISM D2300 coverage. M6 provides explicit-assumption round-trip arithmetic and deterministic terrain-screened mapped-stop candidates; see [API contract](backend/API.md) and `evidence/m6/`. These estimates do not certify operational feasibility or safety. M7 validation/submission remains. Gale RAD is never measured Jezero radiation; ancient-water evidence never implies drinking water or extractable ice.

## Environmental colour overlay
Enable **Environmental map ? Surface thermal response** to colour the actual map using verified THEMIS-derived thermal inertia. Adjust Overlay opacity, then click the map or Sample map center to inspect the native source value. Lower thermal inertia responds faster to heating/cooling; higher resists temperature changes. These are 100 m source pixels, not 20 m environmental detail. The legend and source panel explicitly distinguish this property from temperature, storms and radiation, whose geographic distributions remain unavailable. Historical MEDA/MARCI/RAD context panels still work separately. [Source and checks](evidence/environment-map/README.md), [screenshot](evidence/environment-map/thermal-desktop.png). Production frontend is built; refresh 8000 or 5173 (backend/API requirements unchanged).
