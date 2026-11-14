# M2 routing interface and model

The route engine is implemented locally in Python, using existing NumPy/Rasterio/pyproj dependencies. No service, LLM or network is needed for its calculations. The M3 [local API adapter](API.md) now connects this unchanged M2 interface to the map; the model and evidence below remain preserved.

## Use

From the repository root, after M1 preprocessing:

```powershell
.\.venv\Scripts\python.exe -m backend.cli --start 77.44014119831834 18.44007722806572 --end 77.39603086246426 18.48191632811385 --terrain-weight 100
```

Optionally add `--max-cell-slope-deg 20` or `--output data/processed/my-route.json`. Output creation is exclusive: existing files are never overwritten. Omit the output flag to print JSON. A valid no-path result exits 0; invalid requests, excluded/nodata/outside endpoints, data errors and output errors exit 2 with an error object on stderr. Standard argument syntax errors are handled by argparse.

Python interface for M3:

```python
from backend.routing import TerrainGrid, RoutingError

grid = TerrainGrid.load()  # load once; verifies M1 TIFF checksums/geometry
result = grid.compare(
    start_lonlat=[77.44014119831834, 18.44007722806572],
    end_lonlat=[77.39603086246426, 18.48191632811385],
    terrain_weight=100.0,
    max_cell_slope_deg=None,
)
```

`RoutingError.code` distinguishes `invalid_parameter`, `invalid_coordinate`, `outside_coverage`, `nodata_endpoint`, `excluded_endpoint`, `checksum_mismatch`, `invalid_grid`, `invalid_crs`, and `cost_overflow`. Missing/corrupt files can raise standard I/O/JSON errors to the API adapter. Public coordinates are finite scalar numbers ordered **longitude, latitude**. Longitude uses positive east in [0,360); latitude is planetocentric in [−90,90]. Boolean, string, nested, nonfinite and out-of-range coordinate inputs are rejected. Weight must be finite and nonnegative; optional local cell-slope limit is [0,90] degrees. A finite weight that overflows edge/path costs is rejected, not converted into no-path.

## Deterministic model

- Eight neighbors, fixed clockwise iteration beginning north. Heap ordering is `(estimated total cost, accumulated cost, row-major cell index)`. Strictly lower costs update predecessors; repeated requests on identical inputs return identical results. No random tie breaking or smoothing.
- Both objectives use the same eligible cells: finite source DEM, elevation mask, valid finite local slope with required neighbors, and optional `max_cell_slope_deg` exclusion. Requiring slope validity for both objectives is conservative: it excludes cells where local terrain is unavailable even for the distance objective.
- Diagonal moves require both adjacent cardinal support cells to be eligible. No grid wrap, out-of-bounds access, nodata interpolation or diagonal corner cutting.
- Horizontal edge distance `d` is pyproj.Geod geodesic distance between native cell centers on the actual **Mars sphere R=3,396,190 m**. Longitude/latitude is obtained from the actual DEM CRS, using explicit x/y axis order. No Earth distance model or Web Mercator.
- Distance cost: `d`. Terrain cost: `d * (1 + weight * (abs(delta_z)/d)**2)`. This is a heuristic grade penalty. It is neither a physiological model nor a promise to minimize ascent or maximum slope.
- A* heuristic is the geodesic distance to goal, without terrain penalty. Triangle inequality makes it consistent because every edge cost is at least its geodesic distance and weights are nonnegative. `algorithm='dijkstra'` uses zero heuristic for verification, with the same graph and costs.
- Endpoint selection uses the containing native DEM cell, then snaps to its center. Snap offsets are reported separately; path distances exclude those offsets. Raster coverage includes west/north edges and excludes east/south edges. Fractional indices within 1e−8 of an exact integer are normalized for transform roundoff (≤0.2 micrometres on the 20 m grid); no cell is clamped into coverage.

The optional threshold applies to **local DEM-gradient cell slope**, not the directional segment slope. A valid segment may exceed that threshold. Both are returned separately; the threshold is an explicit user assumption, not a certified obstacle or safety limit.

## Response (schema version 1)

| Field | Meaning |
| --- | --- |
| `status` | `ok` or `no_path`; invalid inputs raise `RoutingError` |
| `endpoints` | Requested lon/lat, snapped cell-center lon/lat and projected metres, zero-based crop row/column, Mars snap distance |
| `parameters` | Weight, optional cell-slope limit, common validity rule and diagonal rule |
| `routes` | Two entries: `distance`, `terrain` |
| `routes[].status` | `ok` or `no_path` |
| `routes[].geometry` | GeoJSON-shaped `LineString` in **Mars** lon/lat, or `Point` for same-cell endpoints; null for no-path |
| `routes[].cells` | Native path as zero-based `[row,column]` pairs; empty for no-path |
| `routes[].profile` | Per-cell cumulative horizontal `distance_m`, source `elevation_m`, local `cell_slope_deg`, signed `incoming_segment_slope_deg` (0 at first cell) |
| `routes[].metrics` | Distance, positive ascent, positive descent, max absolute sampled segment slope, max local cell slope, elevation range, terrain penalty cost and total objective cost; null for no-path |
| `routes[].coverage` | Eligible path/support-cell assertions, native path cell count and eligible-region cell count |
| `routes[].effective_terrain_weight` | 0 for distance, requested weight for terrain |
| `routes[].expanded_cells` | Search expansions for diagnostics; not a scientific score |
| `identical_paths` | Boolean on successful paths, null on no-path; coincident routes are allowed |
| `provenance` | M1 manifest hash, four input TIFF hashes, source product citation/hash, CRS, extent and versions |
| `model`, `routing_source_sha256` | Algorithm version and engine source fingerprint |
| `assumptions` | Explicit limits and definitions, retained with every response |

All distances are horizontal spherical distances along the grid path, not 3D surface arclength. Positive ascent/descent sum differences of sampled native elevation; segment slope is `atan2(delta_z,d)` in degrees. Terrain objective costs have penalized metre units and must never be displayed as physical travel distance, time or effort. No travel duration is inferred.

A single-cell route has Point geometry, one profile sample, zero distance/ascent/descent/cost, and the actual local cell slope. No-path contains no fabricated route geometry or metrics. The two objectives have identical connectivity, so neither invents a path where the other cannot connect.

Geometry is **not Earth RFC 7946 GeoJSON** despite its familiar JSON shape. Consumers must register the custom Mars coordinate system; never silently feed these coordinates into an Earth map. The evidence vector file is named `.mars.json` accordingly.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/verify_routes.py
```

The suite includes explicitly synthetic graph/mask/gradient fixtures; test fixtures are never imported by the real pipeline or CLI. The smoke script loads only real M1 scientific data, compares A* costs to Dijkstra, independently audits all path steps and metrics against separate binary grids/geodesic calls, repeats requests for determinism, checks same-cell and optional threshold cases, and saves [evidence](../evidence/m2/README.md). Twenty-metre sampling cannot establish astronaut-scale obstacle avoidance or certify routes.
