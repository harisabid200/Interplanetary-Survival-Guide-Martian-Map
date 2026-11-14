# STATUS — M2 executed, 2026-11-14

## Confirmed
- Team chose Jezero Crater and is starting implementation.
- Codex is set up.
- Brainstorm captured astronaut-focused navigation, environmental context, site recommendations and AI.

## Proposed, pending team acceptance
- Working title MARSWALK; western Jezero 3–5 km pilot; map-first terrain-aware routing and science decisions as MVP; CTX DEM first with HiRISE upgrade; React/OpenLayers + Python/FastAPI if repo has no established architecture.

## Evidence obtained
- Read AGENTS.md, PRD.md, DATA_SOURCES.md, PLANS.md and initial STATUS.md in full. Repository contained only those documents and an empty tracked readme.md (commit `8acc826`); no application stack or existing implementation was present. Original handoff files were untracked and have been preserved; no commits made.
- **M0 gate passed: real numeric DEM + real imagery with verified common pilot.** Downloaded USGS D1 CTX DEM: 90,345,300 bytes, SHA256 `ba7f706ea1b5d63a562f28a7dcf7a7f3c79bce7f048e6974b57e8a33c30d1ba2`. Rasterio opened 4456 × 5067 float32 cells at 20 m projected spacing. Valid elevations −3504.6453 to −475.8408 m; 22,564,575 / 22,578,552 cells valid (99.9381%). Nodata and nonfinite values excluded. Linked PDS4 label agrees with actual dimensions, nodata and sphere radius.
- Actual Mars CRS: equirectangular, radius **3396190 m**, standard parallel **18.4663°**, central meridian 0°. Catalog radius 3396160 m conflicts; use raster CRS. Units are metres per catalog; band-unit and explicit vertical-CRS metadata are absent. Catalog describes MOLA vertical localization.
- Proposed **5 × 5 km projected pilot** centered near **77.44°E, 18.44°N**: geographic bounds `[77.39549726969, 18.39806942197, 77.48442939843, 18.48242244626]` (west,south,east,north); projected bounds `[4351380,1090540,4356380,1095540]` m. Native window col 1119, row 2394, width/height 250. **62,500 / 62,500 valid cells**, elevations −2627.2498 to −2444.9070 m. This is a proposed demo footprint, not an EVA limit or safety assessment.
- Five pixel-center → Mars longitude/latitude → projected-coordinate → pixel roundtrips passed; center elevation −2561.0198 m. Mars geodesic south/west edges ≈5001.985 / 5000 m; center east/west projection scale 0.9998468425. Retain scale handling in M1.
- NASA Mars Trek CTX controlled imagery resolved through official API catalog and service UUID, not guessed XYZ. Parsed capabilities; downloaded four 256 × 256 PNG tiles at matrix 11, rows 813–814, columns 2928–2929; decoded and visually inspected actual imagery. All 62,500 DEM pilot cell centers have opaque imagery samples inside catalog coverage. Tile and capabilities requests returned `Access-Control-Allow-Origin: *`; no browser integration tested yet.
- Source snapshots, labels, citations, hashes, versions, coordinate details and preview: [M0 evidence](evidence/m0/README.md), [DEM manifest](evidence/m0/dem-inspection.json), [imagery manifest](evidence/m0/imagery-inspection.json), [acquisition manifest](evidence/m0/acquisition-manifest.json). Raw raster/tiles are in ignored `data/raw/`. No synthetic values, slope products or routes created.

## Milestone tracker
| Milestone | State |
|---|---|
| Brainstorm | Complete (initial board) |
| Region selection | Confirmed |
| Handoff documentation | Created |
| M0 Data feasibility | Complete: numeric DEM, imagery, pilot and reproducible checks; official rules access remains unresolved |
| M1 Map / preprocessing | Complete: real-data pipeline, custom Mars map, slope overlay, numeric point samples; actual Chrome and raster checks passed |
| M2 Routing | Complete: deterministic Mars-geodesic A*, both objectives, masks/constraints, CLI, actual real-data audit and 31 Python tests passed |
| M3 Integration | Not started |
| M4 Science and mission budget | Not verified |
| M5 Demo/submission | Not verified |

## Blockers / unknowns
- Official challenge page could not be retrieved: curl exit 60 `SEC_E_UNTRUSTED_ROOT`; trusted certifi bundle retry reported incomplete certificate chain. Web tool returned inaccessible/502. **Challenge wording, eligibility and required datasets/mission counts remain unverified before final submission.** No TLS verification bypass. D1 and D2 succeeded, so no reduced-scope fallback or D3 download was needed.
- WMTS metadata inconsistency: projected CRS label with degree-valued origin/bounds, plus scale denominators inconsistent with Mars angular tile grid. Use explicit global angular tile grid (origin −180,90; matrix 11 = 4096 × 2048; 256 px tiles), custom Mars transform and control-point checks in M1. DEM and imagery standard parallels differ (18.4663° / 0°). Exact details in evidence README; no Earth Web Mercator assumptions.
- Geographical overlap, explicit Mars image placement, qualitative visual terrain alignment and actual Chrome behavior are now checked in M1. These establish relative consistency, not survey positional accuracy. Imagery license field absent from retrieved service catalog; preserve NASA/USGS attribution and check source terms for submission. CTX DEM catalog explicitly says public domain, cite authors.
- 20 m sampling cannot establish astronaut-scale obstacle avoidance or safe routes. Environmental/mineral/resource claims are not supported by this spike. Both acquired products are from MRO, not different missions.
- Team count, remaining deadline and deployment target remain to be established. M1 now uses React 19.3.1 / Vite 8.3.8 / OpenLayers 10.11.0 and Python Rasterio/NumPy/pyproj; no backend/API or paid services needed for this slice.

## Next action
Recommended next task: **M3 integration**. Load the verified grid once in a local API, expose region/provenance and route comparison using [the M2 interface](backend/ROUTING.md), add start/target selection to the real map, draw both returned paths, show metrics/profile and handle validation/no-path/errors. Run an actual map → API → real route end-to-end smoke check. Official challenge terms/source use review remains outstanding before submission.

## M2 results and run instructions
- CLI: `.\.venv\Scripts\python.exe -m backend.cli --start 77.44014119831834 18.44007722806572 --end 77.39603086246426 18.48191632811385 --terrain-weight 100`. Full [run instructions](readme.md) and [engine contract](backend/ROUTING.md).
- Implemented immutable-grid 8-neighbor A* with actual Mars spherical geodesic edge distances, geodesic lower-bound heuristic, deterministic tie ordering and no diagonal corner cutting. Both objectives use the same finite elevation/slope validity mask, with optional user-assumed local cell-slope limit. Distance cost `d`; terrain cost `d*(1+weight*(abs(delta_z)/d)^2)`. Weight is a heuristic, not a physiological or safety parameter.
- Returns actual native route geometry/cells, horizontal distance, positive ascent/descent, maximum sampled segment and local cell slopes, full elevation profile, snap offsets, coverage, penalty/cost contributions and scientific/code provenance. Same-cell requests return Point geometry and zero travel metrics. Disconnected endpoints return empty/no geometry. Nodata, excluded or outside endpoints are invalid requests; no invented route is drawn. Coordinates explicitly Mars lon/lat; no Earth GeoJSON interpretation.
- **Actual Jezero result**, verification cell (125,125) → (1,1), terrain weight 100, no slope exclusion: distance **3507.3038 m**, ascent **156.8789 m**, max segment slope **13.2959°**; terrain **3964.3021 m**, ascent **118.0435 m**, max segment slope **8.6914°**. Native path cells 125 / 164. These are selected verification locations, not mission sites or certified travel.
- Independent audit checked every route step, bounds, masks, diagonal supports, geometry, source elevation/profile and all metrics. A* costs matched Dijkstra on both actual objectives; repeat output identical. Real same-cell and separately chosen actual pair with assumed 10° local cell-slope limit passed. Latest timings: input load/precompute 0.360 s; both A* objectives 0.277 s; both Dijkstra objectives 1.561 s (workspace observation, not guarantee).
- **31 Python tests passed**: 4 existing M1 slope tests, 22 explicitly synthetic routing cases including eight seeded A*/Dijkstra comparisons, and 5 real input/CLI checks (source-copy tamper, manifest mismatch, single-cell JSON, invalid parameter and existing-output protection). Actual CLI command succeeded and saved an ignored runtime result. No new dependencies, downloads or raw writes. Frontend remains the tested M1 map; route display/API are M3.
- Added `backend/__init__.py`, `backend/routing.py`, `backend/cli.py`, `backend/ROUTING.md`, `tests/test_routing.py`, `tests/test_routing_io.py`, `scripts/verify_routes.py`; generated [M2 evidence](evidence/m2/README.md), full JSON results, independent verification and [route preview](evidence/m2/routes-preview.png); updated root README and this file. No commits/publication.
- Tooling: temp-copy tests required approved execution after sandbox Windows temp access failures. A specific NumPy masked-array deprecation was isolated in CLI test capture; production data warnings are not broadly suppressed. No remaining M2 gate blocker. Cell-slope exclusions are not segment-slope caps; endpoint snap offsets are excluded from path distance, both explicitly recorded.

## M1 results and run instructions
- Run `.\.venv\Scripts\python.exe scripts/preprocess.py`, then `npm.cmd run dev --prefix frontend`; open the printed loopback URL. Full fresh setup and verification commands: [readme.md](readme.md).
- Native DEM crop, slope TIFF, separate elevation/slope masks, binary numeric grids, georeferenced real imagery, slope PNG and manifest saved in ignored `data/processed/jezero-m1/`; static runtime copies in ignored `frontend/public/data/`. Pipeline checks raw source hashes before processing; no raw writes, no mock values.
- 62,500 valid elevation and slope cells. Derived slope range **0.00940795–34.37982559°**; median **2.36321306°**. Method: central differences using one-cell raw source halo and actual Mars spherical geodesic distances across neighbors; center plus four neighbors must be valid. No missing-data interpolation or terrain resampling.
- Custom OpenLayers Mars projection uses actual sphere radius/standard parallel; point-to-cell calculations explicitly distinguish projected metres, zero-based crop indices and positive-east/planetocentric lon/lat. All 62,500 cell centers roundtrip; five JS projected coordinates agree with Python/PROJ within 1e−6 m.
- Real cached imagery is stitched from M0 tiles and placed via exact equirectangular extent transform; no reliance on inconsistent WMTS CRS/scale labels. Five imagery pixel placements match native cell centers within 9.32e−10 m. Visual scarp/crater/terrain-break correspondence inspected; no independent accuracy claim.
- App supports pan/zoom, layer toggles/opacity, coverage boundary, keyboard-assisted sampling, numeric cell inspection, source/method/limits disclosure and visible loading/error/outside/nodata handling. Responsive mobile inspector sits below map. No route or safety classification in M1.
- Independent verification reopened outputs: all native elevations equal raw source window exactly; CRS/affine/elevation nodata preserved; TIFF/binary/public hashes agree. Five independently recalculated real slopes differ by at most 2.69e−7°.
- Checks: **4 Python unit tests, 4 JS tests, 4 Chrome browser tests passed**; production build passed; npm installation audit **0 vulnerabilities**. Desktop browser made no external data requests or page errors. Browser tests cover actual pointer selection, reference values, layer controls, outside/error states and mobile layout. Temporary test server stopped. Synthetic fixtures remain tests only.
- Nonblocking tooling observations: Node/Chrome worker creation required approved execution after sandbox EPERM; exact north-edge signed zero fixed; initial browser harness timing/mobile assertions corrected. NumPy/Rasterio shape deprecation warnings and Vite's 520 kB chunk warning recorded. No unresolved M1 gate failures.
- Exact changed files, source details, test results, saved manifest and screenshots: [M1 evidence](evidence/m1/README.md). Raw data, environment, node_modules, generated runtime assets and build/test outputs are ignored; original team documents preserved. No publication or commits made.

## Executed commands and checks
- Initial direct curl attempts: exit 7, unreachable sandbox proxy 127.0.0.1. Approved network execution then downloaded D1, source-linked label, NASA API config/catalog/service/capabilities and four imagery tiles successfully.
- `python -m venv .venv`: ensurepip failed; `uv pip install --python .venv/Scripts/python.exe rasterio==1.4.4 pyproj==3.7.2 Pillow==12.2.0`: succeeded. Exact installed dependencies captured in `requirements-data.lock.txt`; runtime versions in DEM manifest (Python 3.13.0, GDAL 3.10.3, PROJ 9.5.1).
- `.\.venv\Scripts\python.exe scripts/fetch_m0.py`: **passed** with existing files preserved and DEM pinned checksum verified. Initial acquisition used curl.exe; full source URLs, file completion times and hashes now recorded. No raw assets overwritten.
- `.\.venv\Scripts\python.exe scripts/inspect_dem.py`: **passed** actual full-raster mask/statistics, label agreement, pilot validity, plausible numeric samples, Mars transforms and five cell roundtrips.
- `.\.venv\Scripts\python.exe scripts/inspect_imagery.py --fetch`: **passed** actual network requests, PNG decoding, dimensions/nonblank checks, bounds and alpha coverage. Subsequent offline run without `--fetch`: **passed**. `imagery-preview.png` visually inspected.
- Reproduction, exact file list, failures and remaining limits: [evidence/m0/README.md](evidence/m0/README.md). Added `.gitignore`, requirements files and three scripts; generated source snapshots/manifests/preview; updated this file. Original PRD, data-source handoff, plan, AGENTS and README preserved.

## Session log
2026-11-14 (PKT; exact UTC file completion/check times in manifests) | M0 | Acquired/validated actual USGS CTX DEM and NASA Trek CTX tiles; all pilot cells covered; reproducible acquisition/inspection scripts and provenance saved | Commands above passed apart from documented initial network/ensurepip/challenge TLS failures | evidence/m0/ | Official challenge verification outstanding; M1 alignment/browser checks pending | Recommend M1 map and preprocessing slice

2026-11-14 (PKT) | M1 | Implemented real-data crop/slope/mask pipeline, custom Mars map and cell inspector; updated root run instructions | 4 Python + 4 JS + 4 Chrome tests passed; actual raster verification and build passed; screenshots visually inspected | evidence/m1/ | Official challenge terms/source imagery license still pending; no M1 blocker | Recommend M2 routing

2026-11-14 (PKT) | M2 | Implemented deterministic Mars-geodesic route engine and CLI, comparison metrics/profiles/masks/provenance | 31 Python tests passed; real path/metric audit, A*/Dijkstra equality, determinism, same-cell and assumed slope-limit smoke checks passed; actual CLI succeeded | evidence/m2/ | Official challenge terms/source imagery license still pending; route UI/API not yet integrated | Recommend M3 integration

## Session log template
Date/time | milestone | changes | commands/tests and actual results | evidence paths | blockers | next action
