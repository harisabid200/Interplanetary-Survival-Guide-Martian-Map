# M4 environmental intelligence — implemented 2026-11-14

M4's supported historical-context gate passes. Existing CTX map, M2 engine, route comparison, tests and earlier milestone artifacts remain intact. Environmental geographic surfaces, current forecasts and unsupported measurements remain explicitly unavailable.

## Actual data and behavior

- MEDA/Perseverance sol 15: actual PDS4 calibrated ATS version 1.0, derived pressure version 2.0 and ancillary version 4.0, with complete CSV/XML files under ignored `data/raw/environment/`. ATS has 54,121 rows per detector (five separate detectors), pressure 26,818 rows, ancillary 54,242 rows. Label bytes/MD5/header/record count and native units/clocks checked before import. Calibrated pressure also acquired, but not displayed as a second atmospheric estimate.
- Native detector-1 range 190.58–252.15 K; derived pressure 721.69–741.33 Pa. Dominant SCLK spacing 0.5 / 1 seconds; largest observation gaps 26,654.5 / 26,689 seconds. UI uses actual UTC label bounds, LMST row clocks and 300-LMST-clock-second sample means with explicit null empty bins/counts; dots never interpolate gaps. These are neither current weather nor a full-sol/time-weighted climate average.
- Neither ATS nor derived pressure label supplies per-row quality flags. Finite-only screening is explicitly not quality certification. Rover thermal influence disclosed. Pressure-uncertainty column spelling differs between label and CSV; a product/version-specific alias is recorded. Its label unit is kelvin and is scientifically inconsistent with pressure: uncertainty values are excluded, not silently corrected.
- Same-sol ancillary positions cover the sensor SCLK spans. M2020_TOPO landing-site-relative metres: X north −4.96–30.07; Y west −8.33–−3.43; Z outward 0.57–0.68. No geodetic registration, per-observation position join, map pin or areal weather footprint claimed.
- MARCI: cached Malin & Cantor (2022), MSSS-606 report, 17–23 January 2022, release 26 January. Short attributed historical regional paraphrase; no pixel/raster/forecast import. Not contemporaneous with the MEDA sol. Cached report hash is pinned before interpreting.
- RAD: official Gale surface-sol-1 PDS3 product label, README, errata and directory acquired. Product V00 start 2012-220T02:25:43, stop UNK; B/E section units microGray/Hour verified. Science file transfers failed and remain excluded partials. UI displays metadata reference and **numeric dose unavailable**. No measured Jezero radiation, astronaut effective dose or exposure budget.
- Wind, humidity, local dust opacity and environmental spatial overlays unavailable. Selected derived sol listing has no DER_WIND product. Scientific spatial imports remain M5 and budgets M6.

## Reproduce (PowerShell, repository root)

```powershell
.\.venv\Scripts\python.exe scripts/fetch_environment.py --sol 15
.\.venv\Scripts\python.exe scripts/preprocess_environment.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd test --prefix frontend
npm.cmd run build --prefix frontend
$env:MARSWALK_EVIDENCE_STAGE='m4'
$env:MARSWALK_API_PORT='8001'
npm.cmd run test:browser --prefix frontend
.\.venv\Scripts\python.exe scripts/verify_m4.py
Remove-Item Env:MARSWALK_API_PORT
Remove-Item Env:MARSWALK_EVIDENCE_STAGE
```

Install the existing API lockfile for a fresh environment (includes certifi); no new dependencies. Main data setup remains in root README. Acquisition and preprocessing successfully reran with cached files, no network or raw overwrites. Runtime artifacts are ignored `data/processed/environment/environment.json` and `manifest.json`; read-only `/api/environment` verifies manifest size/hash before serving, loaded independently of routing. Missing/corrupt environmental artifacts return 503 and preserve valid routing. Restart the running backend after code/preprocessing changes, then refresh 8000 or Vite 5173.

## Checks and evidence

**56 Python + 7 JS + 16 Chrome tests passed; production build and independent M4 audit passed.** The 44 Python/7 JS/13 Chrome pre-M4 tests remain; new tests cover scientific import/counts/gaps/units/masks/quality semantics/checksums, API tamper/unavailable/host behavior, real browser observations and detector selection, provenance/limits, mobile width and outage/retry while actual routing works. Chrome used test-owned API 8001/preview 4173, leaving the existing user backend on 8000 untouched. All test-owned servers stopped after checks. Desktop/mobile screenshots visually inspected.

- [MEDA acquisition](meda-acquisition-sol-0015.json): exact URLs, bytes, SHA256 and file completion times. Canonical source URLs are recorded even when reusing cached files; actual mirror recovery is described below.
- [Context acquisition](context-acquisition.json): MARCI report and RAD metadata source hashes.
- [Scientific verification](environment-verification.json): actual product metadata/field descriptions, sample statistics/cadence, source versions/hashes, reference semantics and limitations.
- [Independent audit](verification.json): reproducible environment build, unchanged M2 source/M1 identity, preserved M0–M2 evidence hashes, previous milestone snapshots and equality of M3/M4 real browser route results. Route steps/masks/Mars distances/metrics independently recomputed.
- [Actual TCP route response](http-route-response.json), [historical data desktop](environment-desktop.png), [mobile](environment-mobile.png), retained map/mission regression screenshots in this directory.

## Network and tooling outcomes

Initial normal-shell network hit the restricted proxy; approved curl failed Windows Schannel revocation access. Python default SSL validation with the pinned certifi CA bundle reached the actual archive, without disabling certificate checks. Larger streaming requests stalled/timed out. Verified HTTP 206 range requests check exact Content-Range/length/ETag and cap file size; the official `atmos.nmsu.edu` mirror recovered the ancillary/derived pressure files. Previously received bytes were copied into a **new** temporary file; original failed attempts remain untouched. Completed scientific files were accepted only after official PDS MD5/byte/header/count verification. Full source SHA256 values are recorded in the acquisition and verification manifests.

RAD transfers timed out on full streaming and bounded requests; partials remain excluded. Default reproducible acquisition therefore requires RAD metadata only. `--rad-science` is an explicit optional raw download, not a parsed/accepted measurement. Neither a partial download nor verified label justifies a numeric dose display.

Initial sandbox test runs failed Windows temporary-directory access / Node worker spawning; approved execution passed all checks. First browser launch refused occupied port 8000; isolated API 8001 fixed the harness without stopping the user's server. Existing NumPy/Starlette deprecation and ~551 kB Vite bundle warnings are nonfatal. No scientific fallback, new dependency, commit or publication.

## Exact files changed or added for M4

- Documentation: `AGENTS.md`, `PRD.md`, `DATA_SOURCES.md`, `PLANS.md`, `STATUS.md`, `readme.md`, `backend/API.md`, this evidence directory.
- Acquisition/processing/audit: `scripts/fetch_environment.py`, `scripts/preprocess_environment.py`, `scripts/verify_m4.py`.
- Backend: new `backend/environment.py`; `backend/api.py` adds independent historical artifact loading/availability and GET endpoint. M2 engine unchanged.
- Frontend: new `frontend/src/EnvironmentPanel.jsx`; `MissionControl.jsx`, `main.jsx`, `mission.css` extend existing context cards and correct availability language. `frontend/vite.config.js` supports a bounded loopback API-port override for isolated tests; default remains 8000.
- Tests: `tests/test_environment.py`, `frontend/tests/browser/environment.spec.js`; existing `map.spec.js` / `mission.spec.js` only change evidence destinations, retaining all assertions. `frontend/playwright.config.js` supports an isolated API port. Locks, package dependencies, terrain sources and M0–M3 evidence unchanged.

Next: M5, starting with actual SIM 3464 feature acquisition/native-CRS inspection/pilot overlap and its documented 100–200 m registration limitation, then a scientifically validated specific CRISM observation. Official challenge/source-use verification remains required before submission.
