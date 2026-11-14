# PRD — MARSWALK (working title)

## Problem and intent
Future surface explorers need to combine fragmented Mars science observations into understandable travel decisions. Build a layered map and decision-support prototype for a hypothetical astronaut visiting Jezero Crater. This is a planning demonstration, not operational EVA or landing software.

## Approved expanded scope after M2
This scope supersedes the earlier proposed priority/defer decisions below; it preserves all M0–M2 implementation. Original documents are archived in docs/history/pre-expansion/. MARSWALK integrates three core modules:

| Module | Core requirement | Verified now vs planned |
| --- | --- | --- |
| Environmental Intelligence | Terrain, temperature/weather, atmospheric dust/storms, radiation context | CTX terrain and a THEMIS thermal-inertia colour overlay are validated runtime layers. M4 provides historical MEDA temperature/pressure and dated MARCI context; Gale RAD metadata is reference-only, with numeric dose unavailable. Temperature/storm/radiation geographic surfaces remain unmet requirements. |
| Scientific Intelligence | Minerals, ancient-water evidence, geology and science destinations | USGS SIM 3464, CRISM and published Jezero evidence investigated. No mineral/aqueous polygons or scientific scores until specific assets and footprints validate. M5 implements sourced context and supported overlays/destinations. |
| Mission Intelligence | Start/target selection, route objectives/comparison, budgets, candidate locations | M2 routing and M3 map/API comparison are working. M6 adds explicit budgets and candidate ranking from verified criteria. |

Environmental/scientific data are required product work, not optional decorative panels. If spatial data cannot support an overlay, provide honest dated context or an explicit unavailable state and record the unmet capability. No made-up weather telemetry, radiation surface, deposit pin or water inventory.

## Current interface acceptance (M3)
Professional dark mission-control map, preserving real imagery, Mars CRS and numeric inspector. Left sidebar groups independently controlled environmental/scientific layers with evidence status. Mission controls select start/destination on map or through accessible coordinate inputs and choose distance/terrain objective. Show both M2 route geometries, comparison metrics and actual elevation profiles; support coincident paths, same-cell, no-path, outside/nodata, backend failure and changed-input invalidation. Context panels expose units, source, date/location, method and limits. Unverified capabilities have availability/source panels and no geographic overlay. No placeholder science/radiation values.

## Environmental acceptance implemented in M4
Independently toggled environmental panels now import actual MEDA sol 15 (5–6 March 2021 UTC) five-detector near-unit air temperatures and derived atmospheric pressure. Display source units (K/Pa), detector selection, native-sample ranges/counts, five-minute LMST sample means, empty observation gaps, actual UTC label bounds, native clock cadence, product versions/checksums and landing-site-relative rover-position ranges. Preserve detector distinctions and rover thermal influence. Neither ATS nor pressure label supplies per-row quality flags: explicitly disclose finite-only screening. Exclude the pressure-uncertainty field with its inconsistent label unit instead of guessing a correction.

MARCI is the attributed MSSS-606 report for 17–23 January 2022, a different historical period from MEDA. Radiation is verified Curiosity/Gale sol-1 product metadata and source/limitations only; numeric science transfer failed and no dose is displayed. No present-day weather, local dust-opacity/wind/humidity measurements, forecast, environmental hazard surface or Jezero radiation measurement is implemented. These missing capabilities remain explicit. Environmental cache failure must show a retry/unavailable state while terrain/routing remain usable. See evidence/m4/ for checks and screenshots. Scientific intelligence remains M5; budgets/recommendations remain M6.

## Evidence semantics and scientific limits
Every future observation records instrument, product/version, time range, location/footprint, resolution, quality flags, units and provenance. Reference estimates explicitly identify assumptions and transfer uncertainty; derived metrics cite inputs/method. Radiation at Gale is not measured radiation at Jezero; MEDA optical radiation is not ionizing dose. Ancient lake/delta/mineral evidence is not drinking water, accessible ice or extraction feasibility. Geological mapping and spectroscopic detections are interpretations with scale/coverage/uncertainty, not local resource guarantees. Route safety, operational landing/habitat certification and live regional forecasts remain outside this prototype's claims.

Challenge: Interplanetary Survival Guide: Martian Map, NASA Space Apps 2026. Official page: https://www.spaceappschallenge.org/2026/challenges/interplanetary-survival-guide-martian-map/?tab=resources . Confirm current wording, eligibility and required resources with organizers; this handoff does not independently establish those rules.

## Target user and workflow
Hypothetical astronaut/mission planner opens a Jezero map, selects a simulated base and science destination, inspects terrain/observations, compares shortest-distance and slope-penalized routes (including return if enabled), inspects tradeoffs and chooses a plan. A science target is either a sourced feature or a user-selected point; no invented mineral discoveries.

## Original proposed priorities (historical; superseded by expanded core scope)
| Priority | Feature | Acceptance |
|---|---|---|
| P0 | Interactive Jezero map | Actual sourced imagery; pan/zoom, source attribution and bounds |
| P0 | Start and destination | Select points within valid DEM footprint; reject outside/nodata |
| P0 | Terrain analysis | Numeric DEM-derived elevation/slope, units, legend and coverage |
| P0 | Route comparison | Two deterministic objectives, valid route geometry, distance, slope and elevation profile; honest no-path state; routes may coincide |
| P0 | Provenance | Dataset IDs/links, resolution, limitations and processing method visible |
| P1 | Science target selection | At least one verified geological feature if spatial source is available; otherwise user-selected points |
| P1 | Mission budget | User inputs walking speed, available minutes, science stop and reserve; estimate round trip and remaining margin |
| P1 | Site suitability | Rank candidate exploration/staging cells by explicit terrain criteria; science criteria only if verified geological layer exists |
| P2 | Context panels | Sourced historical temperature, dust, radiation or communication context, with times and location |
| P2 | Optional AI | Explain structured results without inventing facts; deterministic template fallback |

Historical defer list: certified landing/habitat selection, live storm/radiation forecasts, communications predictions, extraction, fine-scale obstacle avoidance, full Mars and 3D. The expanded scope promotes environmental/scientific intelligence and candidate recommendations to core work; it does not authorize unsupported operational/resource claims.

## Interface
Single map-first screen: mission setup sidebar (base, target, objective and optional budget); interactive map with toggleable imagery, terrain, route and science layers; comparison panel (distance, ascent, maximum sampled slope, estimated duration and sources). Clearly distinguish measured inputs from derived results and assumptions. Show errors, loading, no coverage and no path; no decorative fake telemetry.

## Pilot and definition of success
Western landing-site/delta area preferred, approximate crater center 18.4 N, 77.6 E. Select a 3–5 km pilot only after measuring overlapping data coverage; make bounds configurable. A judge can select two locations, compute routes from actual numeric data, understand why a route differs, and inspect the evidence in under two minutes. If numeric data unavailable, demonstrate layered observations and waypoint distances only; explicitly disable terrain routing. No unsupported claim of astronaut safety.

## Environmental map requirement clarified after M4
The user wants environmental features rendered as colour overlays on the actual map, with legends and point inspection, as terrain is. Historical side panels alone do not satisfy this geographic requirement. The implemented first supported overlay is a published THEMIS-derived thermal-inertia mosaic (Edwards & Buz, 2021), preserving native 100 m source pixels. It describes resistance to heating/cooling and is explicitly labelled **not temperature**. Temperature, atmospheric storm/dust and ionizing-radiation map layers remain unavailable until spatial data/models and their footprints/uncertainties validate. Single-site MEDA readings and Gale RAD references must not be expanded into illustrative local heatmaps. Context panels remain independently available.
