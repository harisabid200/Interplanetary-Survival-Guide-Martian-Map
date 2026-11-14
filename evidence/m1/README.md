# M1 evidence · 2026-11-14

M1 gate passed: actual imagery and slope overlay render on a custom Mars map; selected native cells display numeric elevation/slope and explicit coordinates, with verified point-to-cell roundtrips. Local implementation only; no publication or backend API.

## Actual results

| Check | Result |
| --- | --- |
| Native crop | 250×250 cells; 62,500 valid elevation and slope cells |
| Elevation | −2627.249755859375 to −2444.906982421875 m |
| Derived slope | 0.00940795 to 34.37982559° |
| Slope percentiles (50 / 90 / 99) | 2.36321306 / 5.67967157 / 18.36217018° |
| Reference 1 (crop row 125, col 125) | 77.4401411983°E, 18.4400772281°N; −2561.01977539 m; 4.44971275° |
| Source-to-crop check | Every crop elevation equals the source window exactly; CRS, affine and elevation nodata preserved |
| Independent real slope calculation | Five raw 3×3 source neighborhoods recomputed independently; max residual 2.6856522e−7° |
| Imagery placement | Five angular image pixel ↔ projected cell centers; max residual 9.31323e−10 m |
| JS ↔ Python/PROJ | Five control points match to <1e−6 m; all 62,500 native cell centers roundtrip |
| Browser checks | Four Playwright tests passed using installed Chrome on production build |
| Offline behavior | No external data requests in desktop smoke test; real cached imagery and numeric cells used |

## Commands and results

From repository root, `python` below means `.\.venv\Scripts\python.exe`:

- `python scripts/preprocess.py`: passed. Checks raw DEM and tile SHA256s, saves native DEM, slope, valid/slope masks, little-endian numeric grids, imagery/slope PNGs and manifest. Uses one-cell raw halo and Mars geodesic neighbor distances, with missing-neighbor propagation. Raw assets untouched.
- `python -m unittest discover -s tests -v`: **4 passed**. Explicitly synthetic flat/known-gradient planes and missing/nonfinite-cell propagation. These fixtures never reach the demo pipeline.
- `python scripts/verify_m1.py`: **passed**. Reopens actual TIFFs; verifies source/crop equality, masks, CRS/affine/nodata, binary values and output/public hashes. Independently recomputes five real slopes. Outputs [verification.json](verification.json) and [alignment-comparison.png](alignment-comparison.png).
- `npm.cmd test --prefix frontend`: **4 passed** (five real control placements, 62,500 cell roundtrips, exact edges/nonfinite coordinates, explicitly synthetic mask handling). Initial test found signed negative zero at north edge; normalized index to zero and rerun passed.
- `npm.cmd run build --prefix frontend`: **passed**, Vite 8.3.8, React 19.3.1, OpenLayers 10.11.0. JS chunk 520.43 kB / 156.75 kB gzip; Vite emits a nonfatal >500 kB chunk warning. No network required to run built app with generated local assets.
- `npm.cmd run test:browser --prefix frontend`: **4 passed**. Desktop actual canvas rendering, five displayed reference values, real pointer selection, outside-coverage rejection, layer toggles/opacity and source disclosure; map keyboard focus/arrow interaction; mobile sampling and no horizontal overflow at 390 px; missing manifest and missing imagery error states with no invented fallback values. Desktop at 1440×1000; mobile at 390×844. No page errors or external data requests in desktop run. Temporary preview server stopped by test runner.
- `npm.cmd install --prefer-online`: 44 packages added; audit reported **0 vulnerabilities**. Exact versions in `frontend/package-lock.json`.

Initial sandbox npm version lookups were cache-only and Node/Playwright test process creation returned EPERM. Approved network/process execution succeeded. Initial browser harness failures were a hidden desktop status badge assertion on mobile and two rapid map clicks being interpreted as a double-click; corrected checks await real state transitions. Final checks above passed. NumPy 2.5 / Rasterio 1.4.4 emits shape-assignment deprecation warnings during some raster reads; data checks passed. No data substituted and TLS validation unchanged.

## Visual review

- [desktop-imagery.png](desktop-imagery.png): real imagery with five verification markers and center elevation/slope readout.
- [desktop-slope.png](desktop-slope.png): same scene with native slope overlay and boundary.
- [mobile.png](mobile.png): responsive map with terrain inspector below it, leaving map center available for selection.
- [alignment-comparison.png](alignment-comparison.png): actual imagery sampled at native cell centers alongside derived slope, with identical footprint and numbered samples. The delta scarp, central-west small crater and southeast terrain break align between layers on visual inspection. This is qualitative relative alignment; no independent positional-accuracy claim.

## Files and reproduction

Implementation added: `scripts/preprocess.py`, `scripts/verify_m1.py`, `tests/test_preprocess.py`; frontend `package.json`, `package-lock.json`, `index.html`, `src/main.jsx`, `src/coordinates.js`, `src/style.css`, `playwright.config.js`, `tests/coordinates.test.js`, `tests/browser/map.spec.js`. Updated `.gitignore`, root `readme.md`, `STATUS.md`. Reports/screenshots in this directory; `pipeline-report.json` is the checksummed manifest snapshot. No source data or large binary products tracked; no commits made.

For fresh acquisition and local launch, see [root README](../../readme.md). Preprocess before tests/build. The saved M0 manifest's native window selects the pilot; changing region requires revalidating source/imagery overlap and reference samples, not just moving the map view.

## Remaining limits / next task

Both sources are MRO CTX; no additional mission data added. Source units/vertical reference limitations, raster/catalog radius conflict and imagery license uncertainty remain documented in provenance. Cached imagery covers only the shown local footprint; no live tile fetch is required. No route, base/science selection, live environmental data or hazard/safety assessment is implemented in M1. Official challenge resource/eligibility verification is still blocked by the M0 TLS/web errors and must be completed before submission.

Next: M2 deterministic distance and slope-penalized routing, with nodata/bounds rejection, no diagonal corner cutting, explainable costs and real-crop checks. Do not infer astronaut-scale obstacle avoidance from this 20 m DEM.
