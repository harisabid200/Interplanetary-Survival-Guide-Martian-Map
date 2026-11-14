# Environmental map overlay extension

The user clarified that environmental features must appear as coloured geographic layers on the actual map. Implemented the first supported spatial environmental layer: **Surface thermal response**, using the published THEMIS-derived thermal-inertia mosaic. It is explicitly **not temperature, dust/storm distribution or radiation**. Those requested geographic variables remain unavailable; historical context alone is not counted as their implementation.

Source: Edwards & Buz (2021), [DOI 10.5281/zenodo.4931348](https://doi.org/10.5281/zenodo.4931348), CC BY 4.0. Dataset publication is 11 June 2021; individual observation dates are not supplied in the TIFF. This is a model-derived mosaic from NASA Odyssey THEMIS, not direct/current air-temperature telemetry. Source model, blending and albedo limitations are shown. Source-described offsets of up to about 20 units are not a full uncertainty bound.

Actual file `Jezero_Thermal_Inertia_v1.tiff`: **1,721,889 bytes**, MD5 `53fec7c990a90629e98c871a7a0da474`, SHA256 `84401e7717d43ae80cbd80213b91bd141ee48197eb8648293197447c43c2829c`. Actual raster 890×890 float32, 100 m projected source cells, nodata 0, Mars sphere R=3396190 m, equirectangular standard parallel 0°. Raw file remains ignored and immutable. [Metadata](zenodo-record.json), [acquisition](acquisition.json), [inspection/geometry/legend/output checksums](inspection.json).

The pilot crop preserves **54×51 native pixels, 2,754 valid**, range **154.8913–304.5992 J m⁻² K⁻¹ s⁻½**. No value resampling, gap filling or artificial 20 m detail. Native crop image placement uses a linear same-sphere equirectangular transform, verified against independent PROJ control points. Overlay is clipped to the pilot. All crop values independently compared to original raster cells; PNG colours/mask and public/runtime hashes verified. This checks numerical placement, not absolute survey registration accuracy.

## Use and reproduce

Enable **Environmental map → Surface thermal response**, adjust Overlay opacity, and inspect a point. Legend uses real thermal-inertia units; lower means faster heating/cooling, higher means greater resistance. Source property is not a hot/cold temperature scale. Colour analysis switches between thermal response and terrain/elevation to keep quantities distinguishable; route layers remain visible. Missing/corrupt assets disable only this overlay. Historical environmental context controls remain independent.

```powershell
.\.venv\Scripts\python.exe scripts/environment_map.py --fetch
npm.cmd run build --prefix frontend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd test --prefix frontend
$env:MARSWALK_API_PORT='8001'
$env:MARSWALK_EVIDENCE_STAGE='environment-map'
npm.cmd run test:browser --prefix frontend
.\.venv\Scripts\python.exe scripts/verify_environment_map.py
Remove-Item Env:MARSWALK_API_PORT
Remove-Item Env:MARSWALK_EVIDENCE_STAGE
```

Fresh setup still needs original M0–M4 acquisition/preprocessing and existing lockfiles. Omit `--fetch` for offline processing. Runtime files are ignored `data/processed/environment-map/` and `frontend/public/data/environment-map/`; no M1 manifest/buffer or M4 historical artifact is changed. Build is ready; refresh 8000 or 5173. Backend request/model code is unchanged.

## Actual validation

- **60 Python tests passed**: 56 existing, four native-raster/PROJ/colour-mask/provenance checks.
- **9 JS tests passed**: seven existing, two native sampling/coverage/missing-value checks. Explicit synthetic missing masks remain tests only.
- **19-case full Chrome suite passed**, then **four overlay cases passed**, including the newly added mobile case. All 20 distinct current browser cases have passed. Covers actual rendered colour changes/native readout, opacity, retained actual M2 comparison, missing/corrupt thermal data and mobile width. Desktop/mobile screenshots visually inspected.
- Production build passed; Vite's existing >500 kB chunk warning remains. Existing scientific-stack deprecations and source CRS-to-PROJ conversion warning are nonfatal; full source WKT is retained, while actual projection/control points are checked.
- Isolated test API 8001 and preview 4173 were stopped by the harness; existing user-owned servers preserved. Screenshots and TCP results save in this directory, preserving all M0–M4 evidence. [Preservation audit](verification.json), [desktop](thermal-desktop.png), [mobile](thermal-mobile.png).

## Files

Added `scripts/environment_map.py`, `scripts/verify_environment_map.py`, `frontend/src/environmentMap.js`, `tests/test_environment_map.py`, `frontend/tests/environment-map.test.js`, `frontend/tests/browser/environment-map.spec.js`, this evidence directory. Updated `frontend/src/main.jsx`, `frontend/src/mission.css`, frontend package test command, and environmental browser screenshot destinations (all existing assertions retained); all five project docs/root README updated. No new dependency, routing/API model change, commit or publication.

Next environmental work: validate an actual dated georeferenced surface brightness-temperature product and its coverage before adding a temperature colour layer. Current MEDA/Gale/report inputs cannot provide local temperature/storm/radiation surfaces. M5 science and M6 budgets remain separate pending milestones.
