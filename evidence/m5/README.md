# M5 geology overlay verification

Date: 2026-11-15. M5 is complete for source-backed context and user-selected science stops. No scientific ranking or safety-qualified destination recommendation is made.

## Source acquisition and inspection

- Official USGS Sun & Stack (2020), *Geologic Map of Jezero Crater and the Nili Planum Region, Mars*, SIM 3464: https://doi.org/10.3133/sim3464
- Database: https://pubs.usgs.gov/sim/3464/sim3464_database.zip
- Retrieved archive: `data/raw/sim3464/sim3464_database.zip`, 349,336,873 bytes; SHA-256 `a88bd53a5573743cc4a20036c10e585106d08a433ad2f34af269e9cea1529f87`. The raw archive is ignored by Git.
- Archive contains ESRI File Geodatabase `Nili.gdb` and supporting map/raster products. Fiona OpenFileGDB read 13 layers. `GeoUnits_v1` contains 1,304 multipolygon features. Its source attributes include `unit`, `name`, `symbol_noSub`, `subscript`, `symbol`, `ORIG_FID`, `Shape_Length`, `Shape_Area`, and `Color_ID`.
- Native CRS: Mars 2000 sphere, radius 3,396,190 m; Mars Transverse Mercator, central meridian 77.5°E; metres. The source map footprint is 76.8–77.8°E, 17.7–18.7°N at publication scale 1:75,000.
- Transformed all 1,304 source geometries to the app's Mars equirectangular CRS and performed a polygon-vs-pilot-rectangle intersection check. **Nine actual polygons** intersect the 5 × 5 km pilot. Their five unique mapped units are Upper etched (Nue), Jezero fan 2 (NHjf2), Eolian bedform (Aeb), Lower etched (Nle), and Jezero floor (Njf). The delivered geometries retain their mapped outlines; map rendering is clipped to the pilot extent.
- The USGS README reports random 100–200 m offsets relative to the controlled CTX surface-operations mosaic. The product discloses this in the map panel and click inspector; no shift or precision correction was applied. Publication scale does not imply pixel-scale positional precision.

## Runtime behavior

In the left sidebar, open **Scientific intelligence → Geological features**. Enabling the checkbox loads the source-derived GeoJSON, validates both its SHA-256 and the input region manifest hash, and draws the unit polygons. Each categorical color only distinguishes unit symbols; color is not a measurement, resource score or hazard value. Clicking a polygon shows its actual unit symbol/name and the source scale/registration limitation. Turning the checkbox off removes the overlay. The right panel links to USGS and states what the map cannot establish.

No mineral concentrations, accessible drinking water, extractable ice, present-day hazards, science destination pins, or route scoring from geology are included.

## CRISM D2300 spectral-index layer

- **Products:** targeted observation `FRT000047A3`, orbit 2743, acquired 2007-02-26 04:34:15.930–04:36:23.656 UTC. Official PDS directory: https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/2007/2007_057/frt000047a3/ ; product information is cross-checked with the NASA/USGS Mars ODE product record and footprint. Exact output/source hashes and geometry are in [crism-validation.json](crism-validation.json).
- **Native data:** the MTRDR I/F label defines 808 × 847 samples × 489 bands, float32, projected Mars equirectangular coordinates and nominal ~18 m pixels. The app does not download or process the 164 MB hyperspectral cube. It acquires the real 164,250,240-byte 60-band SR summary image, source label and header. SHA-256 of the summary image: `10eb37e4dd8f2f95a6c3ebdfda5a0b066bd02c33bb2d1e03558c024f3b16ec2d`. 1-based band 40 is D2300.
- **Footprint and pilot:** independent ODE footprint geometry was transformed from positive-east longitude / planetocentric latitude into the app Mars CRS and intersected with the 5 × 5 km pilot. The polygon intersection is **11,358,784.735 m² (45.435%)**. Nearest-neighbour reprojection to the existing 20 m pilot grid yields **28,095 / 62,500 valid cells (44.952%)**. The rest are transparent nodata; no gap filling. D2300 range in the delivered valid cells is −0.00684693 to 0.01961476, median 0.00526535, p95 0.01191245.
- **Interpretation limits:** D2300 is a dimensionless 2.3 µm spectral-drop parameter used in hydrated-mineral/clay studies. It is not unique mineral identification, concentration, deposit, accessible water or extractable ice. The CRISM SR product is noise-remediated and processing spatially interpolates flagged outlier pixels; spectral overlap, mixtures and residual effects remain. The display uses a continuous stretch from −0.01 to +0.02 without category thresholds. The inspector reports the actual source-derived value and missing coverage honestly. Primary product reference: [CRISM product SIS](https://pds-geosciences.wustl.edu/mro/mro-m-crism-2-edr-v1/mrocr_0002/document/crism_dpsis.htm); [ODE REST manual](https://oderest.rsl.wustl.edu/ODE_REST_V2.1.6.pdf).
- **UI:** enable **Scientific intelligence → CRISM D2300 spectral index**. Change the shared overlay opacity if desired. Click a point inside colored observation coverage for a numeric value; blank cells mean outside source coverage or source nodata. This is not a mineral map.

Rebuild from verified local raw files with `scripts/fetch_crism_candidate.py` and `scripts/build_crism_overlay.py`; raw source files are ignored and fetch refuses to overwrite existing assets. Generated runtime rasters and manifests are ignored under `data/processed/crism/` and `frontend/public/data/crism/`.

## Source-mapped science stops

The acquired official SIM 3464 geodatabase `LocationFeatures` layer contains 341 point records and only one attribute, `TYPE`; all 341 are `small crater`. `scripts/build_science_destinations.py` transforms the actual point coordinates from the source Mars Transverse Mercator CRS into each selected app-region CRS and clips to the verified region. The measured product contains 3 points for `jezero-m1` and 8 for `expanded-7p5km`. Every feature retains its actual source feature ID and point geometry. The user can enable **Scientific intelligence → Mapped science stops** to show C01… markers and choose one in **Mission planning → USGS mapped science stop** to fill destination B. M1 and expanded products have separate region-manifest identities and GeoJSON hashes.

These are hypothetical user-selected stops at source-mapped point locations. The app does not call them crater centroids, identify their individual scientific value, rank them, infer route access, or screen safety. The SIM 3464 1:75,000 scale and 100–200 m random registration offset are disclosed. Reproduce both products using the commands in the root README; `scripts/verify_science_destinations.py` validates source identity, output hashes, region identity, point type and containment. Results: [source/region/hash audit](science-destinations-verification.json).

Dedicated Chrome evidence showing selectable points and calculated routes: [science-destinations-desktop.png](science-destinations-desktop.png). The complete 25-case Chrome regression run passed; its isolated screenshots are under `evidence/m5-regression/` so older milestone images remain unchanged. Current check counts and caveats are in [STATUS.md](../../STATUS.md).

Ancient-lake context now paraphrases NASA/JPL's published Jezero lakeshore explanation with a direct link and retained image-source attribution. It remains historical interpretation and has no local water polygon or resource estimate. No accessible drinking water or extractable ice is claimed.

## Reproduction

From the repository root, with the `requirements-data.lock.txt` environment installed:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_sim3464.py
.\.venv\Scripts\python.exe scripts/build_geology.py
npm.cmd run build --prefix frontend
```

The fetch script refuses to overwrite an existing raw archive. Preprocessing writes the GeoJSON and source/region hash manifest to ignored `frontend/public/data/geology/`. Generated GeoJSON SHA-256: `9bda8e62f2217a716760c9bd8ed45e32956f462243ba8d29ec0089f477cd43a2` (1,514,307 bytes).

## Checks

- Geology builder: passed; 1,304 source polygons read, 9 exact polygon intersections emitted, source/output checksums recorded.
- Production frontend: `npm.cmd run build --prefix frontend` passed. Existing Vite >500 kB chunk advisory remains.
- Python regressions: 60 passed, 32 subtests passed. Some sandbox temp-directory restrictions required the test runner to run with workspace-safe temporary paths and elevated execution.
- JS unit regressions: 9 passed using `node --test --experimental-test-isolation=none ...` to avoid sandbox worker-spawn restrictions.
- Browser regressions: 18 non-thermal Playwright cases passed (map, mission, environment context, geology and CRISM). Four established M4 thermal browser cases were excluded to preserve their existing M4 evidence. The CRISM test verifies product identity, valid coverage, overlay pixels, a real numeric sample at a source-valid pixel, toggle-off and no browser exceptions.
- Browser screenshot: [geology-desktop.png](geology-desktop.png).

## Files

- `scripts/fetch_sim3464.py` — checksum-reporting, no-overwrite official source fetch.
- `scripts/build_geology.py` — safe geodatabase extraction, Mars CRS transform, exact pilot intersection and hashed GeoJSON manifest.
- `frontend/src/main.jsx`, `frontend/src/MissionControl.jsx`, `frontend/src/style.css` — toggle, styled overlay, source details and unit inspector.
- `frontend/tests/browser/geology.spec.js` — source-backed map smoke test.
- `scripts/fetch_crism_candidate.py`, `scripts/build_crism_overlay.py` — pinned PDS product acquisition and integrity/geometry-checked processing.
- `frontend/src/crismMap.js`, `frontend/tests/browser/crism.spec.js` — client-side checksum/identity validation, numeric sampling and source-backed browser test.
- `crism-validation.json`, `crism-desktop.png` — CRISM validation manifest snapshot and map/inspector screenshot.
- `requirements-data.txt`, `requirements-data.lock.txt` — pinned Fiona OpenFileGDB reader.
