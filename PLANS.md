# PLANS — execution milestones

Timeboxes are proposed elapsed hours, not official hackathon deadlines. Confirm remaining time and team capacity. Prefer a complete vertical slice before adding features.

Scope expansion after M2: preserve completed M0–M2 and their evidence. Revised remaining milestones below are authoritative. Original M3–M5 science/budget/polish plan and all pre-expansion documents are retained verbatim in docs/history/pre-expansion/; old numbering is not evidence that expanded modules were implemented.

## M0 — data feasibility (0–60 min)
Inspect repo, official challenge resources and available tools. Fetch D1, inspect raster, sample valid numeric values; obtain D2 capabilities and render one test tile. Confirm common coverage and pilot. If downloads fail, record exact errors, try D3 or cached permitted assets without fabricating values. Gate: actual valid raster plus imagery access or explicit reduced-scope decision.

## M1 — map and data pipeline (hours 1–2)
Map frontend (React/Vite, OpenLayers proposed) with registered Mars projection. Python Rasterio/NumPy pipeline saves cropped DEM, slope grid, valid mask and manifest. Display real imagery plus a derived slope overlay. Verify control points against both layers and bounds. Gate: point-to-cell roundtrip and numeric sample visible at selected point.

## M2 — routing (hours 2–4)
Implement 8-neighbor grid A* (or Dijkstra), no diagonal corner cutting through invalid cells, mask nodata and avoid out-of-bounds. Use projected horizontal distance metres with scale handled or Mars geodesic distance. Distance objective cost d; terrain objective example d*(1 + lambda*(abs(delta_z)/d)^2), lambda >=0 configurable, explicitly heuristic rather than physiological model. Optional slope exclusion user-defined and clearly assumed; same valid mask for comparisons. A* straight-line lower bound only if consistent with the chosen distance metric. Return geometry, distance, positive ascent, max sampled segment slope, elevation profile, coverage and parameter values. No path is valid output; never draw a fake route. Test flat, steep detour, blocked grid, start=end, nodata and unreachable endpoints using labeled fixtures; test real crop separately.

## M3 — interactive mission control and routing integration
Extend the working React/OpenLayers dark map interface. Independently control verified imagery, elevation/slope and route layers; group Environmental and Scientific capability panels with availability states. Only validated geographic assets may become overlays. Add start/destination selection by map and accessible coordinates, distance/terrain exploration objectives, assumed weight/optional cell-gradient exclusion and actual comparison/profile panels. Reuse M2 unchanged behind a validated local API: GET /api/region returns coverage/CRS/provenance and availability; POST /api/routes returns M2 structured geometry/metrics/assumptions. Load verified grid once, reject stale frontend/backend dataset mismatches, bounds/nodata/invalid input, and clear stale results after input changes. Gate: real map selection → API → M2 → rendered routes and profiles, no-path/backend-error/same-cell behavior and all M0–M2 regressions tested. Preserve standalone terrain inspection when API unavailable.

## M4 — environmental intelligence (core)
Acquire/inspect actual labelled MEDA historical measurements (temperature/pressure/wind/dust as supported), quality and rover coordinates; record exact temporal sampling and units. Show dated rover-local series/context, never a fabricated regional current-weather raster. Investigate a dated MARCI report or calibrated/geolocated swath for broad dust/storm context; use context-only until footprint and variable meaning validate. RAD is historical Gale reference only, no measured Jezero radiation distribution. Distinguish solar optical radiation from ionizing dosimetry and reference estimates from measurements. Gate: reproducible scientific import/summary, visible location/time/source/quality/limits, independent module controls, numerical checks and honest missing-data states. Unavailable spatial coverage remains an explicit unmet requirement rather than invented telemetry.

M4 execution result (2026-11-14): gate passed for the supported historical-context slice. Reproducible MEDA sol 15 ATS/derived-pressure/ancillary import, actual K/Pa series with gap/quality/frame disclosure, dated MARCI report and verified Gale RAD metadata reference are implemented. See STATUS.md and evidence/m4/. Environmental rasters/current forecasts, wind/humidity/opacity and numeric RAD dose remain unavailable; they are not silently counted as implemented. M0–M3 functionality/evidence retained. Next execution task is M5.

## M5 — scientific intelligence (core)
Acquire USGS SIM 3464 database; inspect native Mars CRS/attributes, clip supported geological features and preserve documented random 100–200 m registration uncertainty. Validate an exact pilot-intersecting CRISM observation/label and scientifically interpreted spectral evidence before adding mineral geography. Use published ancient-water explanations with citations; no accessible water/ice or resource amounts inferred. Source destination pins from verified coordinates and feature meaning; user-selected points remain available. Gate: scientifically meaningful context/overlays with scale, uncertainty, coverage and source; no invented deposits, fabricated discoveries or scientific ranking from unverified layers.

## M6 — mission recommendations and budgets
Budget uses user-assumed positive walking speed, available time, science duration and reserve, with separately computed outbound/return route distances. Explicitly label time as a calculation, not an operational guarantee. Candidate staging/exploration locations use deterministic documented terrain criteria; add science/environment criteria only where verified spatial data support them. Report missing inputs, footprint, uncertainty and weights; never claim safest landing/habitat. Test positive/nonnegative inputs, infeasible budgets, missing coverage and ranking determinism. LLM narration optional, only from structured results, with deterministic fallback and no frontend secrets.

## M7 — validation, polish and submission
Fresh setup, offline scientific cache, API/browser regression and accessibility/mobile checks; provenance/license/source review, screenshots/video and backup demo. Demonstrate environmental/scientific/mission modules while honestly identifying planned/unavailable capabilities. Recheck official challenge wording, resources and eligibility with trusted access/organizers before submission. CTX/MARCI/CRISM/HiRISE are instruments on MRO, not independent missions; MEDA is Mars 2020, RAD is MSL/Gale context. Only count scientifically meaningful sources under actual rules. Preserve all milestone evidence and document unresolved requirements.

## Suggested ownership (if parallel)
- Data: scripts/, data manifest, projection and crop.
- Frontend: frontend/ map, controls, layers, route UI.
- Routing: backend/ route engine and tests.
- Integrator: shared contract, deployment, QA, documentation and demo. Adjust to actual team size; one person may perform all tasks sequentially.

Proposed directory layout: AGENTS.md, PRD.md, DATA_SOURCES.md, PLANS.md, STATUS.md, frontend/, backend/, scripts/, tests/, data/raw/ (ignored), data/processed/ (large files ignored). Respect existing repo layout first.

## M4 map extension ? user clarification after historical-context slice
Environmental colour overlays are an explicit product requirement. A verified, georeferenced THEMIS thermal-inertia overlay has been implemented with native pixels, legend, units, provenance and point sampling; context-only MEDA/MARCI/RAD functionality is retained. This supplies a real thermal-property map, not temperature/storm/radiation distributions. Those geographic variables remain unmet until actual suitable spatial sources or validated models support them. Source acquisition, native pixel/CRS checks, actual map rendering, missing/corrupt states and routing regressions are recorded under evidence/environment-map/. Preserve M0?M4 evidence. M5 scientific intelligence remains the next numbered milestone.
