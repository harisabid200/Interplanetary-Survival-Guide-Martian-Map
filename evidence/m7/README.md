# M7 demo and submission readiness

## Current build
MARSWALK is a local Jezero exploration prototype with verified NASA/USGS imagery and terrain, M2 route comparison, source-backed SIM 3464 and CRISM layers, THEMIS thermal inertia, historical MEDA/MARCI context, Gale-only RAD metadata, and user-assumption mission budget arithmetic. See [M0–M6 status](../../STATUS.md), [data sources and limitations](../../DATA_SOURCES.md), and [M6 calculations](../m6/README.md).

## Suggested live demo (3 minutes)
1. Start API: `\.venv\Scripts\python.exe -m backend.server`.
2. Start UI: `npm.cmd run dev --prefix frontend`; open `http://127.0.0.1:5173`.
3. Show 7.5 km coverage, toggle the 20 m slope layer and actual THEMIS thermal-inertia layer. Explain that optical imagery is not elevation and thermal inertia is not temperature.
4. Toggle mapped geology, CRISM D2300 and SIM 3464 points; show coverage, numeric values/labels and caveats.
5. Load the verification pair and compare distance/terrain routes. Explain that these are derived grid paths, not safety-certified or obstacle-scale traverses.
6. Enter a walking-speed assumption, time, stop and reserve to show round-trip arithmetic. The output is not an EVA plan.
7. Show MEDA/MARCI/RAD context and distinguish historical/remote context from Jezero spatial weather or radiation measurements. No accessible water or extractable ice is claimed.

## Before submission
- [ ] Confirm registered team, selected challenge, project title and portal submission fields with the team.
- [ ] Check the official local deadline and eligibility immediately. Official pages: [Space Apps 2026](https://www.spaceappschallenge.org/2026/), [Islamabad local event](https://www.spaceappschallenge.org/2026/local-events/islamabad/), [participant terms](https://www.spaceappschallenge.org/legal/).
- [ ] Obtain explicit NASA/USGS attribution/reuse terms for the Mars Trek/CTX WMTS imagery; the catalog inspected by M0 had no license field. DEM catalog records public-domain status; cite source authors. Keep credits visible in the app.
- [ ] Capture an actual 2–3 minute demo recording and provide its hosted link in the portal. This checklist is not a video recording.
- [ ] Add team-authored problem/solution text and challenge alignment after verifying the selected challenge. Do not invent team names, roles, registration or challenge selection.
- [ ] Fresh-start both services and run Python, JavaScript, browser and build regressions. Verify cached assets and API reconnect behavior for a backup demo.
- [ ] Check all claims against source limitations; never call Gale RAD a Jezero measurement or ancient water accessible water/ice.

## Current completion boundary
Software and regression evidence are prepared. This is a demo guide and submission checklist, not a completed portal submission or recorded demo. Team registration/challenge selection and demo hosting remain team-provided details.
