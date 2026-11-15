# M6 evidence — mission budgets and terrain-screened mapped stops

## Implemented behavior
`POST /api/mission-budget` runs the existing M2 router independently for outbound and return travel and reports separate distance/terrain objective arithmetic. The interface requires positive assumed walking speed, available time, science-stop duration and reserve. Invalid or missing inputs are rejected; no totals are returned if either route is absent. See the captured [budget summary](mission-budget-summary.json), tied to the M1 terrain-manifest hash.

The summary's verification pair yields a 7,014.6 m distance-objective round trip and a 7,928.6 m terrain-objective round trip. At an explicitly assumed 4 km/h, plus 20 minutes for a stop and 15 minutes of reserve, the arithmetic totals are 140.2 and 153.9 minutes. These are illustrative calculations for test control points, not an operational mission prescription, EVA duration, feasibility result or safety guarantee.

The deterministic candidate screen only considers actual SIM 3464 mapped small-crater points. User-set straight-line Mars distance and maximum terrain slope filter candidates; the full 200 m positional-uncertainty disk must fall inside valid DEM coverage. Ordering uses Mars-geodesic distance, buffered maximum slope and source feature ID. This does not test route access, hazards or science priority.

## Observed pilot result
With verification-pair start, 90 degree maximum buffer slope and 5 km maximum straight-line range, the three source-mapped points in the 5 km M1 region produced **zero candidates**. None satisfy the full 200 m uncertainty-buffer terrain-coverage condition. This is displayed as an empty qualifying set; criteria are not relaxed to force a recommendation. The eight points in the expanded 7.5 km region remain selectable under the pre-existing M5 feature picker, but need not pass this stricter M6 screen.

## Validation
- `python -m unittest discover -s tests -v`: **63 passed** (workspace-temp access required).
- `node --test --experimental-test-isolation=none tests/coordinates.test.js tests/api.test.js tests/environment-map.test.js tests/candidate-ranking.test.js`: **13 passed**.
- Full Playwright suite: **27 passed**, including M4 thermal/context, M5 sources and M6 budget/candidate flows.
- `npm run build --prefix frontend`: passed; existing Vite >500 kB chunk advisory remains.
- `scripts/verify_science_destinations.py`: passed source/archive/output hashes and pilot/expanded region membership (3/8 points).
- `scripts/verify_m4.py`: passed reproducibility, evidence preservation and unchanged M2 identity.
- `git diff --check`: passed before final evidence/doc updates; rerun before commit.

Playwright ran on isolated API port 8001 and wrote the M6 screenshot and regression artifacts into this evidence directory and `evidence/m6-regression/`. No environmental measurements or new geospatial products were invented.
