# Jezero high-detail map base

## What changed

The application previously displayed a 512 × 512 mosaic made from four actual NASA/JPL Mars Trek / USGS CTX zoom-11 tiles. At the map's default fit that image was enlarged, and slope shading was enabled by default, so the basemap looked soft and overlay-heavy.

The application now mosaics 64 source-verified zoom-13 CTX tiles (2,048 × 2,048 px) for the **same** image footprint. The angular tile grid spacing is approximately 5.0876 m/pixel at Mars equator; the source product is nominally ~6 m. This improves how the actual orbital imagery displays. It does not change the 20 m DEM, slope calculations, routing inputs, DEM footprint or obstacle-scale certainty. Slope starts off; its toggle remains available. A metric scale bar uses the existing Mars projection's point-resolution calculation.

The app's initial map extent is now **7.5 × 7.5 km** (1.5× around the pilot) so users see more of the actual surrounding landscape. The toolbar button toggles between **Wider view** and **Fit pilot**. The dashed 5 × 5 km boundary still marks the only verified DEM, point-sampling and route-analysis footprint. Outside that boundary the user sees CTX imagery only; no elevation or route is inferred there. The already acquired image tiles cover this wider view, so this change adds no unverified geography.

## Source and integrity checks

- Official service/layer: [NASA Mars Trek](https://trek.nasa.gov/mars/) `JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0`, published through NASA/JPL Mars Trek with USGS Astrogeology source data.
- Tile service template comes from the saved official WMTS capabilities; no guessed XYZ path or Earth Web Mercator tile source is used.
- All 64 downloaded PNGs were checked for decoding, 256 × 256 dimensions and nonblank pixels; each URL, size and SHA-256 are in [zoom13-validation.json](zoom13-validation.json).
- Output mosaic SHA-256: `a4268d21c98c70b3b480fd95cbef44826c310994727a5836a245cbd4a57b6d06` (2,187,858 bytes).
- Mosaic bounds equal the existing M1 imagery extent within 1e−6 projected metres. All five M1 terrain control points land on opaque imagery pixels. The client checks the image hash, matrix/layer identity, bounds and M1 region-manifest hash before selecting it. If detail metadata is absent it falls back to the prior M1 image; invalid detail data is rejected visibly.
- Raw tiles and generated runtime assets remain ignored (`data/raw/ctx_13_*.png`, `data/processed/jezero-m1/imagery-detail*`, `frontend/public/data/imagery-detail*`). No tile binaries are tracked.

## Run and validation

```powershell
.\.venv\Scripts\python.exe scripts/build_detail_basemap.py --fetch
npm.cmd run build --prefix frontend
$env:MARSWALK_API_PORT='8008'
npm.cmd run test:browser --prefix frontend -- --grep-invert thermal
```

Validation: **19 non-thermal Chrome cases passed**, including a dedicated test that checks product identity, all five control-point coverage records, successful local image load, default slope-off state, scale bar, sampling, and no browser exceptions. The 18 existing non-thermal cases for terrain, routes, environmental and scientific layers also passed. Four established M4 thermal browser cases were excluded from this run; earlier M4 evidence remains preserved. Production build passed with the existing Vite >500 kB chunk advisory.

The map remains optical CTX imagery, not a colored elevation raster. It has no labels beyond the app's data panels, and the 5 km pilot remains the only verified numeric route footprint.

Screenshot: [map-upgrade-desktop.png](map-upgrade-desktop.png).
