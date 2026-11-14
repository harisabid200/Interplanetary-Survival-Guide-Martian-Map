# M2 routing evidence · 2026-11-14

M2 is implemented and tested: deterministic 8-neighbor A* compares horizontal distance and a grade-penalized objective using the real Jezero DEM. Both objectives share validity/exclusion masks; diagonal corner cutting is prohibited. HTTP/map integration remains M3.

## Actual real-data comparison

Endpoints are M1 verification sample 1 → sample 2, **not** actual mission base/science sites. Requested Mars coordinates:

- Start: [77.44014119831834, 18.44007722806572] positive-east longitude, planetocentric latitude; native crop row 125, column 125.
- End: [77.39603086246426, 18.48191632811385]; native crop row 1, column 1.
- Terrain weight: 100 (heuristic assumption). No cell-slope exclusion in this comparison.

| Derived metric | Distance objective | Terrain objective |
| --- | ---: | ---: |
| Horizontal Mars distance | 3507.3038 m | 3964.3021 m |
| Positive ascent | 156.8789 m | 118.0435 m |
| Descent | 45.7578 m | 6.9224 m |
| Max sampled segment slope | 13.2959° | 8.6914° |
| Max sampled local cell slope | 14.1570° | 14.1347° |
| Native path cells | 125 | 164 |
| Own objective cost | 3507.3038 | 4759.4117 |
| Terrain penalty component | 0 | 795.1095 |

The terrain route travels about 457.0 m farther. Lower ascent/maximum segment slope is observed in this example; the penalty does not guarantee minimizing either metric. Objective scores use different costs and should not be directly ranked against one another. The terrain score is penalized metres, not physical distance or effort.

Latest recorded timing on this workspace: input load/edge precompute **0.360 s**, A* both objectives **0.277 s**, Dijkstra both **1.561 s**. These are smoke timings, not performance guarantees. [verification.json](verification.json) contains exact values and engine/input hashes.

## Actual checks

- **31 Python tests passed**: 4 existing M1 slope tests, 22 synthetic routing tests, 5 real-data input/CLI boundary checks.
- Synthetic fixtures cover flat diagonal distance, longer lower-grade detour, zero weight/coincident objectives, blocked wall/no-path, one/two invalid diagonal supports, same cell, nodata/nonfinite terrain, missing slope neighbors, shared assumed exclusions, invalid/excluded/outside endpoints, exact bounds, snap offsets, reverse ascent/descent/profile, invalid weights/limits/coordinates/CRS and cost overflow. Eight seeded synthetic grids compare A* to Dijkstra. Fixtures are labeled and excluded from demo outputs.
- Real integrity checks reject a modified copy of a TIFF and a mismatched manifest geometry. Tests modify isolated temporary copies, never source assets. CLI checks finite single-cell output, invalid-parameter error response and refusal to overwrite existing files.
- Actual `python -m backend.cli ... --output data/processed/m2-cli/route.json` succeeded on the real comparison above. The command output is ignored runtime data; its scientific route results match the saved evidence.
- `python scripts/verify_routes.py`: **passed**. Every returned cell and cardinal support is in bounds and eligible, steps are native neighbors with no loop, route endpoints match snapped cells, and all geometry coordinates match independent CRS transforms. Distance, cumulative profile, signed segment slope, elevation samples, ascent/descent and cost were independently recomputed from M1 binary grids and separate Mars Geod calls. All metrics agree within 1e−7 absolute / 1e−12 relative tolerance.
- Both real A* objective costs match Dijkstra; repeated comparisons are identical. Real same-cell Point/zero-distance output passed. A second actual pair at crop row 125, columns 50 → 200 passed with a user-assumed **10° local cell-slope limit**, including independent mask/metric audit.
- No new dependencies, downloads, raw-data writes, synthetic demo values or frontend changes. No network/LLM used for route computation.

Commands (repository root; Python means `.\.venv\Scripts\python.exe`):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/verify_routes.py
.\.venv\Scripts\python.exe -m backend.cli --start 77.44014119831834 18.44007722806572 --end 77.39603086246426 18.48191632811385 --terrain-weight 100
```

Initial temporary-copy tests hit Windows temp-folder sandbox permissions; approved execution passed. Under unittest's warning policy a known NumPy 2.5 masked-array deprecation polluted the captured CLI stderr; the CLI test helper filters only that specific third-party compatibility warning when asserting its JSON channel. No scientific/runtime data warning is broadly suppressed. Input validation was hardened for nested/scalar-array coordinates and overflow before the final 31-test pass.

## Artifacts and files

- [real-routes.json](real-routes.json): complete actual comparison, geometry, cells, profile, metrics, parameters and source/code fingerprints.
- [real-routes-cell-limit-10deg.json](real-routes-cell-limit-10deg.json): separately audited real constrained example.
- [real-routes.mars.json](real-routes.mars.json): geometry collection with explicit Mars coordinate reference. GeoJSON-shaped JSON, **not Earth RFC 7946 GeoJSON**.
- [routes-preview.png](routes-preview.png): visually inspected real paths over real CTX imagery, identical pilot extent, north up; labels show actual computed metrics.
- [verification.json](verification.json): independent audit, Dijkstra/determinism results, scientific input and engine hashes, observed timings.

Added implementation: `backend/__init__.py`, `backend/routing.py`, `backend/cli.py`, `backend/ROUTING.md`, `tests/test_routing.py`, `tests/test_routing_io.py`, `scripts/verify_routes.py`. Updated root `readme.md` and `STATUS.md`; added these evidence files. No source assets overwritten; no commits or publication.

## Limits and next task

Local cell gradient and directional segment gradient are different metrics. The optional exclusion limits local cells only; a segment slope can exceed the specified cell limit, as explicitly tested and recorded. Endpoints snap to native centers; snap offsets are exposed but excluded from path distance. Every route uses the conservative common elevation-plus-slope validity mask. No path smoothing, fine-scale obstacle model, travel-time model or safety certification is provided.

Official challenge rules/resources and source imagery-use terms remain unverified as recorded in M0/M1. These do not block the local M2 gate but must be checked before submission.

Next: M3 API adapter and map integration—select start/target on the real map, request these structured results, draw both native paths, compare metrics and profile, and show input/no-path/errors honestly.
