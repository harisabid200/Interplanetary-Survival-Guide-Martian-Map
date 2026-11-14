# PLANS — execution milestones

Timeboxes are proposed elapsed hours, not official hackathon deadlines. Confirm remaining time and team capacity. Prefer a complete vertical slice before adding features.

## M0 — data feasibility (0–60 min)
Inspect repo, official challenge resources and available tools. Fetch D1, inspect raster, sample valid numeric values; obtain D2 capabilities and render one test tile. Confirm common coverage and pilot. If downloads fail, record exact errors, try D3 or cached permitted assets without fabricating values. Gate: actual valid raster plus imagery access or explicit reduced-scope decision.

## M1 — map and data pipeline (hours 1–2)
Map frontend (React/Vite, OpenLayers proposed) with registered Mars projection. Python Rasterio/NumPy pipeline saves cropped DEM, slope grid, valid mask and manifest. Display real imagery plus a derived slope overlay. Verify control points against both layers and bounds. Gate: point-to-cell roundtrip and numeric sample visible at selected point.

## M2 — routing (hours 2–4)
Implement 8-neighbor grid A* (or Dijkstra), no diagonal corner cutting through invalid cells, mask nodata and avoid out-of-bounds. Use projected horizontal distance metres with scale handled or Mars geodesic distance. Distance objective cost d; terrain objective example d*(1 + lambda*(abs(delta_z)/d)^2), lambda >=0 configurable, explicitly heuristic rather than physiological model. Optional slope exclusion user-defined and clearly assumed; same valid mask for comparisons. A* straight-line lower bound only if consistent with the chosen distance metric. Return geometry, distance, positive ascent, max sampled segment slope, elevation profile, coverage and parameter values. No path is valid output; never draw a fake route. Test flat, steep detour, blocked grid, start=end, nodata and unreachable endpoints using labeled fixtures; test real crop separately.

## M3 — connect UI and backend (hours 4–5)
Proposed API: GET /region -> footprint, CRS, layers, provenance; POST /routes -> start/end (lon,lat positive east), objectives, lambda, optional threshold; response route coordinates explicitly lon/lat, metrics/units, model assumptions and errors. Keep contract in one shared document/schema and validate input. Serve locally with FastAPI or equivalent. Draw paths, compare and inspect details; handle offline/error states. Test a real route end-to-end.

## M4 — science and budget (hours 5–7, only after M3)
Add verified science targets if available. User-selectable mission budget: outbound and separately calculated return distance / assumed speed + science time + reserve; remaining minutes = total - sum. Validate positive speed and nonnegative durations. No time claim is operational. Optional terrain-only staging candidate ranking with visible criteria; do not label as safest. Missing geology means no scientific score. LLM explanation only grounded in computed inputs, with no keys in frontend.

## M5 — polish, validation, submission (remaining time)
Pin sources, capture screenshots/video and test fresh setup. Prepare a 90–120 second demo: choose base and target, compare route objectives, inspect slope and source, explain decision and limitations. Include multiple mission datasets if verified and required; CTX and HiRISE are different instruments on the same MRO mission, so do not count them as different missions. Check challenge-specific eligibility; add sourced MOLA or rover context as relevant if requirement calls for multiple missions. Avoid token source additions with no meaningful use. Reserve final hours for submission and backup demo.

## Suggested ownership (if parallel)
- Data: scripts/, data manifest, projection and crop.
- Frontend: frontend/ map, controls, layers, route UI.
- Routing: backend/ route engine and tests.
- Integrator: shared contract, deployment, QA, documentation and demo. Adjust to actual team size; one person may perform all tasks sequentially.

Proposed directory layout: AGENTS.md, PRD.md, DATA_SOURCES.md, PLANS.md, STATUS.md, frontend/, backend/, scripts/, tests/, data/raw/ (ignored), data/processed/ (large files ignored). Respect existing repo layout first.
