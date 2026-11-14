# M3–M4 local API contract

Run `python -m backend.server` with the project API environment from repository root. Host is loopback `127.0.0.1`, port 8000, one process. Existing verified M1 grid loads once in FastAPI lifespan; every route delegates to the unchanged [M2 engine](ROUTING.md). No API key, service dependency, file writes or scientific source fetch is on the request path.

Production: `npm.cmd run build --prefix frontend`, then the API also serves `frontend/dist` at `/`. Development: Vite on 5173 proxies `/api` to 8000. No permissive cross-origin API is enabled. Trusted Host/origin checks match these fixed local ports. This is a local demo, not a public authenticated production service.

## GET /api/health
200 `{"status":"ready"}` when verified routing grid/manifest loaded; 503 `{"status":"data_unavailable"}` otherwise. A missing/unreadable dataset is logged locally; no fabricated fallback grid. Cached frontend terrain can remain available independently.

## GET /api/region
Returns `region` (existing scientific M1 manifest), `region_manifest_sha256`, `routing_available`, M2 model identifier and an `availability` registry. CTX imagery/terrain are validated. M4 availability distinguishes `historical_MEDA_local`, `historical_MARCI_report_only`, `Gale_reference_only_metadata` from unavailable environmental artifacts; M5 sources remain planned. This endpoint itself returns no environmental measurements.

The frontend hashes its actual local manifest and each elevation/slope/mask buffer with SHA256. It must match the backend manifest hash before planning. Numeric byte-length/hash failure stops terrain loading. Dataset identity errors must not be silently repaired by mixing products.

## GET /api/environment (M4)
Read-only local historical context, loaded once at startup from ignored `data/processed/environment/environment.json` and its manifest. Size is bounded to 2 MiB; byte count and SHA256 must match. No source fetch, preprocessing or file writes occur on the request path. Restart the backend after regenerating artifacts.

HTTP 200 returns `schema_version:1`, `kind:historical_environment_context`, `artifact_sha256`, `spatial_overlays:[]`, `meda`, `dust`, `radiation`. MEDA contains separate sol-15 ATS series and derived pressure, product/label provenance, actual UTC bounds, field units, record counts/native SCLK cadence, empty/nonfinite screening rules, sample ranges/counts and 288 five-minute LMST bins (null means for empty bins). Position ranges are same-sol landing-site-relative M2020_TOPO metres, not geodetic coordinates. No spatial weather surface, joined geodetic rover position or UTC-per-row conversion is claimed. Pressure uncertainty is excluded because of an inconsistent archive label unit.

`dust` is a dated, attributed MARCI report, not a numerical forecast. `radiation` is verified Gale RAD metadata reference with numeric dose unavailable; never measured Jezero radiation. No radiation exposure or safety budget is calculated. The periods differ and are explicitly displayed. Source fields/methods/caveats are retained for the UI.

Missing, unreadable or checksum-invalid artifacts return **503**, code `environment_unavailable`, with a reproducible preprocessing/restart instruction and no fabricated fallback measurements. Environmental failure does not disable valid terrain/routing; `/api/health` continues to describe routing readiness. Existing Host and response-security guards apply. Synthetic flag/missing-data fixtures are tests only.

## POST /api/routes
`Content-Type: application/json`. Coordinates ordered **positive-east longitude, planetocentric latitude**, degrees. Example using the hash from `/api/region`:

```json
{
  "start_lonlat": [77.44014119831834, 18.44007722806572],
  "end_lonlat": [77.39603086246426, 18.48191632811385],
  "terrain_weight": 100,
  "max_cell_slope_deg": null,
  "primary_objective": "terrain",
  "region_manifest_sha256": "<64-character lowercase SHA256 from the region response>"
}
```

Both objectives are always computed with the same grid/parameters; `primary_objective` chooses the initial display focus, not a different scientific model. Response is the M2 result plus `primary_objective` and `region_manifest_sha256`. Preserve all M2 units, profile fields, assumptions and provenance. Native same-cell geometry is a Point. No-path returns HTTP 200, `status=no_path`, null geometries/metrics and empty paths. Never draw a substitute straight line.

Strict finite numeric inputs; strings/booleans/nonfinite values, wrong coordinate cardinality and extra fields are rejected. Longitude/latitude domains/coverage and nodata are enforced by M2; the API bounds terrain weight to [0,1,000,000] as an engineering input limit, not physiological meaning. Optional local cell-gradient exclusion is [0,90]°, distinct from directional segment slope. JSON body is bounded to 4096 actual streamed bytes before parsing. One route computation at a time prevents uncontrolled parallel CPU work.

| HTTP | Code / meaning |
| --- | --- |
| 422 | Invalid schema/parameter/coordinate, outside/nodata/excluded endpoint, nonfinite cost; structured `code`, `message`, optional field names |
| 409 | `dataset_mismatch`: reload/regenerate matching map and route inputs |
| 429 | `busy`: another calculation is active; `Retry-After: 1` |
| 503 | Verified routing dataset unavailable |
| 413 | JSON body exceeds 4096 bytes |
| 415 | Request must be JSON |
| 403 | Untrusted browser origin |
| 400 | Untrusted host |

No input values or server stack traces are included in schema error responses. Server responses include nosniff/frame/referrer guards. No credentials, cookies, authentication, database or external write operations are involved. Frontend requests have finite timeouts, abort on changed inputs, and ignore outdated responses. Errors/no-path clear old geometry; API loss preserves standalone map inspection. The browser checks include actual local TCP/API routing, plus explicitly simulated outage/mismatch responses for failure-state coverage.

The backend's geometry is Mars-specific JSON, not Earth WGS84 GeoJSON. OpenLayers converts each returned coordinate using the existing custom Mars sphere/equirectangular transform. Browser route display never recalculates or smooths the M2 paths.
