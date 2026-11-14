# AGENTS.md — Marswalk engineering instructions

## Mission
Build a working NASA Space Apps 2026 prototype for astronaut-facing exploration of Jezero Crater, Mars. Working name: MARSWALK (not final branding). Optimize for a credible live hackathon demo, not production flight software.

## Decisions and authority
Confirmed by team: Jezero Crater; start implementation now; Codex is available. Brainstorm: Google Maps-like astronaut navigation, roughly 5 km exploration, terrain/holes, temperature, radiation, weather/dust storms, communication, minerals/water, landing/habitat/science location recommendations, AI-assisted site and path selection. The narrower MVP in PRD.md is a recommended scope, not a team-confirmed rejection of other ideas. Treat 5 km as a proposed pilot extent, not a confirmed EVA limit.

Read PRD.md, DATA_SOURCES.md, PLANS.md and STATUS.md before edits. Inspect existing repository and preserve team work. Use existing stack where viable; otherwise propose React + Vite + OpenLayers (custom Mars projection), Python Rasterio/NumPy and FastAPI; simplify if appropriate. Avoid paid services or LLM dependencies on the critical path.

## Engineering rules
- Start with milestone M0/M1 in PLANS.md. Verify the direct DEM download and actual raster metadata before committing to route analysis. Report failures and choose documented fallbacks. Never fabricate scientific data. Synthetic test fixtures must be obviously labeled and excluded from real demo outputs.
- Store raw data outside tracked source (gitignore); include reproducible fetch/preprocess commands, data manifest, citations, checksums and version information. Do not commit large binaries or secrets. Do not overwrite raw assets.
- Use Mars CRS and proper coordinate transforms; explicitly distinguish longitude/latitude, raster index and projected metres. Do not silently use Earth Web Mercator or Earth distance formulas. Verify tile matrix, extent and axis order.
- Image tiles are imagery, not numeric elevation. Propagate nodata and coverage boundaries; never interpolate missing terrain into a claim of safety.
- Route scoring must be deterministic and explainable. LLM is optional narration of structured verified observations, not a geospatial oracle. Never claim a route, landing site or habitat is safe/certified; no fabricated live weather, radiation or water availability.
- Keep UI functional, map-first, responsive and accessible. Label observation, derived metric, assumption and unavailable data separately.
- Build vertical slices; run tests and actual smoke checks. Report exact files changed, commands/results, blockers and next step. Update STATUS.md after each milestone; do not mark untested work as complete.
- Coordinate parallel agents by file ownership; avoid broad rewrites, concurrent edits to shared interfaces, destructive Git commands and unnecessary dependency additions.

## First instruction
Inspect repo, identify existing work, then implement the data feasibility spike. Fetch the CTX DEM listed in DATA_SOURCES.md, inspect metadata and numeric samples, determine a valid pilot footprint and report results. If network permission is needed, request it or provide a reproducible command. Proceed to map integration only with explicit status of source access. Check official challenge rules/resources before final submission.
