# M3 expanded scope and mission control evidence · 2026-11-14

Scope expanded, not restarted. All five project documents now promote Environmental, Scientific and Mission Intelligence to core modules, with revised M3–M7 milestones. Exact previous documents are archived in `docs/history/pre-expansion/`; completed M0–M2 scientific data, pipeline, engine, tests and evidence remain preserved.

## Working implementation

The existing React/Vite/OpenLayers map is now connected to the unchanged M2 Python engine through FastAPI. It supports actual map picks and accessible numeric start/destination entry, distance/terrain exploration priority, configurable heuristic weight and optional local cell-slope exclusion. Both actual native paths render on the custom Mars map, with individual visibility/focus controls, source elevation profiles, ascent, distances, sampled segment/local gradients, costs, snap offsets and provenance.

Verified imagery, derived slope, numeric inspector, coverage bounds, verification points, keyboard inspection and mobile behavior remain working. Added native-cell elevation tint is a visualization of the existing checked DEM, not a new elevation dataset. Left-side environmental/scientific context toggles expose exact candidate source and availability/limitations; **no unvalidated environmental or scientific geography is drawn**. Budget/recommendation work is clearly M6 planned.

Frontend/backend dataset identity is checked using the actual manifest SHA256; frontend numeric arrays/masks are checked against output hashes. Invalid inputs, stale datasets, no-path, same-cell, unavailable API, corrupted terrain, cancelled/late responses and changed mission inputs have explicit states. Terrain inspection remains usable independently when routing API is unavailable. Endpoints snap and routes render without smoothing or Earth coordinate shortcuts.

## Actual checks and results

| Check | Actual result |
| --- | --- |
| M0–M2 Python regressions + API | **44 passed** (31 existing + 13 API) |
| Existing JS coordinate/mask regressions | **4 passed**, including all 62,500 native cell roundtrips |
| Chrome tests with real loopback API + production preview | **13 passed** (4 retained M1 + 9 mission cases) |
| Production build | Passed, Vite 8.3.8; 544.71 kB JS / 164.18 kB gzip |
| Independent API scientific audit | Passed against separately read numeric grids/geodesic calls |
| Actual TCP browser result vs independent API adapter | Entire structured result identical |
| M2 engine preservation | Engine SHA256 exactly matches M2 evidence |
| M1 input preservation | Scientific manifest hash unchanged from M2 |

The actual end-to-end verification pair still produces distance **3507.3038 m**, ascent **156.8789 m**, max segment **13.2959°**; terrain **3964.3021 m**, ascent **118.0435 m**, max segment **8.6914°**, with weight 100 and no cell exclusion. These are selected verification locations, not approved mission/scientific sites. The Chrome result and independent audit include every native route sample, not precomputed/demo responses.

API checks cover actual route metrics/profiles, region/source availability, same-cell Point, actual disconnected cells under an assumed 0.1° cell-gradient limit, wrong dataset, bounds/exclusions, strict finite schema, untrusted host/origin, content type, 4096-byte body bound, single-computation/busy response, missing-data service state and retained static terrain. Browser checks include actual canvas picks → API → M2 → displayed geometry/metrics/profile, layer controls, source-context semantics, mobile width, failures/reconnect, changed-input clearing, intentional late-response cancellation and tampered binary data. Outage/mismatch/tamper simulations are explicitly test-only; real successful calculations use actual inputs and API.

Commands (repository root):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
npm.cmd run test:browser --prefix frontend
.\.venv\Scripts\python.exe scripts/verify_m3.py
.\.venv\Scripts\python.exe -m compileall -q backend scripts tests
git diff --check
```

Chrome tests own and stop API port 8000 and preview port 4173. Initial sandbox process creation returned EPERM; approved execution succeeded. Known NumPy masked-array and Starlette/httpx TestClient deprecations remain nonfatal; no scientific warnings/data are broadly suppressed. Vite's >500 kB bundle warning is nonfatal. No new frontend dependencies; pinned API environment recorded separately from unchanged data-only lock.

## Source investigation, access and scientific boundaries

Exact URLs, formats, sampling/scale, geographic coverage and limitations are in [DATA_SOURCES.md](../../DATA_SOURCES.md). Investigated primary PDS/SIS sources for **MEDA, MARCI, RAD, CRISM**, plus **USGS SIM 3464**. These are candidate sources, not imported runtime measurements. MEDA archive documentation is readable through web tools, but direct local curl attempts failed with Schannel revocation-offline exit 35; no TLS validation bypass or numeric sample import. MARCI and RAD format specifications were inspected; CRISM product families/current PDS4 labels and legacy data preservation were checked.

USGS official catalog and linked README/FGDC XML were actually fetched with trusted curl after initial web/sandbox failures:

```powershell
curl.exe -fsSL -o evidence/m3/sim3464-catalog.html https://pubs.usgs.gov/publication/sim3464
curl.exe -fsSL -o evidence/m3/sim3464_readme.txt https://pubs.usgs.gov/sim/3464/sim3464_readme.txt
curl.exe -fsSL -o evidence/m3/sim3464_metadata.xml https://pubs.usgs.gov/sim/3464/sim3464_metadata.xml
```

Catalog links verify exact database ZIP; it was **not** downloaded. Metadata/README establish file-geodatabase features, 1:75,000 publication scale, bounds 76.8–77.8°E / 17.7–18.7°N and Mars transverse Mercator central meridian 77.5°E. Source explicitly warns of random **100–200 m registration offsets** from the controlled surface-operations CTX mosaic. Preserve this uncertainty in M5; no automatic shift or exact contact overlay.

MEDA is historical rover-local Jezero environmental context, not a regional current forecast; its optical RDS radiation is not ionizing dose. RAD is historical **Gale Crater** reference, never measured Jezero radiation. MARCI broad imagery is not local storm prediction. CRISM spectral evidence is not mineral concentration or a confirmed extractable deposit. Ancient lake/delta evidence is not accessible drinking water, extractable ice or a present water inventory. The UI explicitly separates these unavailable/planned capabilities from verified terrain and calculated routes.

## Artifacts

- `mission-control-desktop.png`, `mission-control-mobile.png`: reviewed actual UI with computed routes/profiles; environmental/scientific controls and honest availability panels.
- `http-route-response.json`: actual TCP browser API result, independently verified against M2/scientific grids.
- `verification.json`: code/data preservation hashes, historical evidence file hashes, original context snapshots, fetched USGS metadata provenance and independent numeric audit.
- `regression-desktop-imagery.png`, `regression-desktop-slope.png`, `regression-mobile.png`: retained M1 behavior in the current interface. Existing M1 screenshot files were not overwritten; screenshot destinations alone were updated in the regression test.
- `sim3464-catalog.html`, `sim3464_readme.txt`, `sim3464_metadata.xml`: actually retrieved official source metadata (no scientific feature data or invented overlay).

## Changed files

Updated `AGENTS.md`, `PRD.md`, `DATA_SOURCES.md`, `PLANS.md`, `STATUS.md`, root `readme.md`, `backend/ROUTING.md`, `frontend/src/main.jsx`, `frontend/playwright.config.js`, `frontend/tests/browser/map.spec.js`. Added exact five-document snapshots under `docs/history/pre-expansion/`; `backend/api.py`, `backend/server.py`, `backend/API.md`; `requirements-api.txt`, `requirements-api.lock.txt`; `frontend/vite.config.js`, `frontend/src/MissionControl.jsx`, `frontend/src/mission.css`, `frontend/tests/browser/mission.spec.js`; `tests/test_api.py`, `scripts/verify_m3.py`; this evidence directory. M2 routing.py/CLI, M1 scientific pipeline, raw/processed source data, data lock and frontend package lock unchanged. No commits, cloud hosting or publication.

## Run / next milestone

Current built workspace: `.\.venv\Scripts\python.exe -m backend.server`, then open http://127.0.0.1:8000. Fresh setup and developer proxy workflow are in root README. The test servers have stopped; launch the command for interactive use.

Next is **M4 environmental intelligence**: acquire a labelled quality-checked MEDA product and time/rover context; import reproducible dated observations, then suitable MARCI historical context and separately labelled Gale RAD reference. M5 scientific imports follow with USGS registration uncertainty and selected CRISM footprint validation. M6 budgets/recommendations remain unimplemented. Official challenge eligibility/resource requirements and source-use terms still require trusted verification before M7 submission.
