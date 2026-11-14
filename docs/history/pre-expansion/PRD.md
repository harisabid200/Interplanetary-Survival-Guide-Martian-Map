# PRD — MARSWALK (working title)

## Problem and intent
Future surface explorers need to combine fragmented Mars science observations into understandable travel decisions. Build a layered map and decision-support prototype for a hypothetical astronaut visiting Jezero Crater. This is a planning demonstration, not operational EVA or landing software.

Challenge: Interplanetary Survival Guide: Martian Map, NASA Space Apps 2026. Official page: https://www.spaceappschallenge.org/2026/challenges/interplanetary-survival-guide-martian-map/?tab=resources . Confirm current wording, eligibility and required resources with organizers; this handoff does not independently establish those rules.

## Target user and workflow
Hypothetical astronaut/mission planner opens a Jezero map, selects a simulated base and science destination, inspects terrain/observations, compares shortest-distance and slope-penalized routes (including return if enabled), inspects tradeoffs and chooses a plan. A science target is either a sourced feature or a user-selected point; no invented mineral discoveries.

## Priorities (proposed)
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

Defer certified landing/habitat selection, live storm/radiation forecasts, communications coverage predictions, resource extraction, fine-scale obstacle avoidance, full Mars coverage and 3D unless core demo works. Brainstorm remains preserved in AGENTS.md.

## Interface
Single map-first screen: mission setup sidebar (base, target, objective and optional budget); interactive map with toggleable imagery, terrain, route and science layers; comparison panel (distance, ascent, maximum sampled slope, estimated duration and sources). Clearly distinguish measured inputs from derived results and assumptions. Show errors, loading, no coverage and no path; no decorative fake telemetry.

## Pilot and definition of success
Western landing-site/delta area preferred, approximate crater center 18.4 N, 77.6 E. Select a 3–5 km pilot only after measuring overlapping data coverage; make bounds configurable. A judge can select two locations, compute routes from actual numeric data, understand why a route differs, and inspect the evidence in under two minutes. If numeric data unavailable, demonstrate layered observations and waypoint distances only; explicitly disable terrain routing. No unsupported claim of astronaut safety.
