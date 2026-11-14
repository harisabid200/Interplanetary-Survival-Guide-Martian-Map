# Verified 7.5 km terrain expansion

Generated from the same actual M20 Jezero CTX DEM used by M1. This is a native 20 m crop, not interpolated terrain.

- Source asset: `data/raw/M20_JezeroCrater_CTXDEM_20m.tif`
- Source SHA-256: `ba7f706ea1b5d63a562f28a7dcf7a7f3c79bce7f048e6974b57e8a33c30d1ba2`
- Original M1 source window: `[col=1119,row=2394,width=250,height=250]`
- Expanded source window: `[col=1057,row=2332,width=375,height=375]`
- Projected extent: `[4350139.999999998,1089280.0000000028,4357639.999999998,1096780.0000000028]` m
- Valid DEM: 140,625 / 140,625 cells; slope-valid: 140,625 / 140,625 cells
- Elevation range: minus 2649.7273 to minus 2396.5696 m
- Output manifest SHA-256: `398e5bfc3db222c6fa277c2c770add0b886e719590f89a1c9702ef833a10e896`

The DEM source and original M1 files were not overwritten. `manifest.json` records output checksums and the source M1 manifest checksum. Slope uses the existing central-difference method with a native one-cell halo and Mars geodesic neighbor distances.

The frontend can select the original 5 km region or the expanded region; API requests use the selected region ID and manifest hash. The M2 routing engine is unchanged. Real CTX imagery provides background coverage around the region. The original M1 overlays remain available, and separately manifested SIM 3464 geology, CRISM D2300 and THEMIS thermal-inertia overlays now cover only their verified expanded footprints. Partial CRISM coverage remains transparent outside observed valid pixels.

Reproduce after normal M1 preprocessing:

```powershell
.\.venv\Scripts\python.exe scripts/preprocess_expanded.py
npm.cmd run build --prefix frontend
```

To reproduce expanded scientific layers after acquiring the documented source assets:

```powershell
.\.venv\Scripts\python.exe scripts/build_geology.py --region data/processed/jezero-expanded-7p5km/manifest.json --output frontend/public/data/expanded/geology --processed data/processed/jezero-expanded-7p5km/geology --evidence evidence/map-expansion/geology
.\.venv\Scripts\python.exe scripts/build_crism_overlay.py --region data/processed/jezero-expanded-7p5km/manifest.json --output data/processed/jezero-expanded-7p5km/crism --public frontend/public/data/expanded/crism
.\.venv\Scripts\python.exe scripts/environment_map.py --region data/processed/jezero-expanded-7p5km/manifest.json --output data/processed/jezero-expanded-7p5km/environment-map --public frontend/public/data/expanded/environment-map --evidence evidence/map-expansion/environment-map
.\.venv\Scripts\python.exe scripts/verify_expanded_overlays.py
```

## Expanded scientific source coverage

The same source products were independently built for the expanded grid, preserving the M1 assets:

- SIM 3464: 19 polygons intersect; source archive hash is retained in `geology/manifest.json`; registration offset remains 100-200 m.
- CRISM FRT000047A3 D2300: observed ODE footprint intersection is 22,312,980.489 m2 (39.6675% of the expanded region); the 20 m target grid has 54,063/140,625 valid cells (38.4448%). Nodata remains transparent.
- THEMIS-derived thermal inertia: native 100 m source pixels, 80 x 76 output pixels, 6,080/6,080 valid. Its transformed footprint contains the complete selected terrain extent. It is not temperature, weather or radiation.

Run `scripts/verify_expanded_overlays.py` to check region identities, asset hashes, CRISM coverage counts and THEMIS bounds. Per-layer manifest snapshots are in this directory.

Verification on 2026-11-15: expanded terrain and all three overlays rebuilt; source/hash/footprint audit passed; 60 Python tests, 9 JavaScript tests and all 24 Chrome tests passed. The production build and expanded route/hash smoke also passed. The full browser run includes original M1 layer, mission, mobile and failure-state regressions.
