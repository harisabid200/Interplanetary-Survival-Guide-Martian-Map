"""Fetch and mosaic real zoom-13 Mars Trek / USGS Jezero CTX tiles."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "evidence/m0/wmts-capabilities.xml"
REGION = ROOT / "data/processed/jezero-m1/manifest.json"
RAW = ROOT / "data/raw"
OUTPUT = ROOT / "data/processed/jezero-m1"
PUBLIC = ROOT / "frontend/public/data"
MATRIX_ID = "13"
LAYER = "JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0"
NS = {"wm": "http://www.opengis.net/wmts/1.0", "ows": "http://www.opengis.net/ows/1.1"}


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="fetch missing, official zoom-13 source tiles")
    args = parser.parse_args()
    region = json.loads(REGION.read_text(encoding="utf-8"))
    capabilities = ET.parse(CAPABILITIES).getroot()
    layer = next((item for item in capabilities.findall("wm:Contents/wm:Layer", NS)
                  if item.findtext("ows:Identifier", namespaces=NS) == LAYER), None)
    matrix_set = capabilities.find("wm:Contents/wm:TileMatrixSet", NS)
    matrix = next((item for item in matrix_set.findall("wm:TileMatrix", NS)
                   if item.findtext("ows:Identifier", namespaces=NS) == MATRIX_ID), None)
    if layer is None or matrix is None:
        raise ValueError("Saved NASA Mars Trek capabilities do not advertise the expected CTX layer and zoom 13")
    cols, rows = int(float(matrix.findtext("wm:MatrixWidth", namespaces=NS))), int(float(matrix.findtext("wm:MatrixHeight", namespaces=NS)))
    tile_width, tile_height = int(matrix.findtext("wm:TileWidth", namespaces=NS)), int(matrix.findtext("wm:TileHeight", namespaces=NS))
    span = 360.0 / cols
    if rows * 2 != cols or (tile_width, tile_height) != (256, 256):
        raise ValueError("Unsupported Mars Trek angular tile matrix")
    west, south, east, north = region["imagery_bounds_lonlat"]
    c0, c1 = math.floor((west + 180) / span), math.floor(math.nextafter((east + 180) / span, -math.inf))
    r0, r1 = math.floor((90 - north) / span), math.floor(math.nextafter((90 - south) / span, -math.inf))
    if c0 < 0 or c1 >= cols or r0 < 0 or r1 >= rows:
        raise ValueError("Requested tile footprint exceeds the advertised matrix")
    template = layer.find("wm:ResourceURL", NS).attrib["template"]
    style = layer.findtext("wm:Style/ows:Identifier", namespaces=NS)
    matrix_set_id = matrix_set.findtext("ows:Identifier", namespaces=NS)
    mosaic = Image.new("RGBA", ((c1 - c0 + 1) * tile_width, (r1 - r0 + 1) * tile_height))
    records = []
    for row in range(r0, r1 + 1):
        for col in range(c0, c1 + 1):
            url = template
            for key, value in {"Style": style, "TileMatrixSet": matrix_set_id,
                               "TileMatrix": MATRIX_ID, "TileRow": row, "TileCol": col}.items():
                url = url.replace("{" + key + "}", str(value))
            path = RAW / f"ctx_{MATRIX_ID}_{row}_{col}.png"
            headers = OUTPUT / f"ctx_{MATRIX_ID}_{row}_{col}.headers.txt"
            if not path.exists():
                if not args.fetch:
                    raise FileNotFoundError(f"Missing actual source tile {path}; rerun with --fetch")
                part = path.with_suffix(".png.part")
                if part.exists():
                    raise FileExistsError(f"Inspect interrupted download; preserving {part}")
                completed = subprocess.run(["curl.exe", "-fL", "--retry", "2", "--connect-timeout", "20",
                                            "--max-time", "90", "-H", "Origin: http://localhost:5173",
                                            "-D", str(headers), "-o", str(part), url],
                                           check=True, capture_output=True, text=True)
                with Image.open(part) as check:
                    check.load()
                    if check.format != "PNG" or check.size != (tile_width, tile_height):
                        raise ValueError(f"Unexpected source image from {url}")
                part.replace(path)
                if not headers.exists():
                    headers.write_text(completed.stdout, encoding="utf-8")
            with Image.open(path) as image:
                image.load()
                if image.format != "PNG" or image.size != (tile_width, tile_height):
                    raise ValueError(f"Cached source tile failed validation: {path}")
                rgba = image.convert("RGBA")
                if np.asarray(rgba)[..., :3].std() < 1:
                    raise ValueError(f"Blank source image tile: {path}")
                mosaic.paste(rgba, ((col - c0) * tile_width, (row - r0) * tile_height))
            records.append({"url": url, "path": path.relative_to(ROOT).as_posix(),
                            "bytes": path.stat().st_size, "sha256": digest(path), "row": row, "column": col})
    target = OUTPUT / "imagery-detail.png"
    public_target = PUBLIC / "imagery-detail.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    mosaic.save(target, optimize=True)
    mosaic.save(public_target, optimize=True)
    dx = 360 / cols
    image_bounds_lonlat = [-180 + c0 * dx, 90 - (r1 + 1) * dx,
                           -180 + (c1 + 1) * dx, 90 - r0 * dx]
    radius = region["crs"]["radius_m"]
    standard = math.radians(region["crs"]["standard_parallel_deg"])
    lon_scale, lat_scale = radius * math.cos(standard) * math.pi / 180, radius * math.pi / 180
    bounds_m = [image_bounds_lonlat[0] * lon_scale, image_bounds_lonlat[1] * lat_scale,
                image_bounds_lonlat[2] * lon_scale, image_bounds_lonlat[3] * lat_scale]
    if any(abs(a - b) >= 1e-6 for a, b in zip(bounds_m, region["imagery_bounds_m"])):
        raise ValueError("High-detail tile mosaic does not exactly match the validated M1 imagery extent")
    alpha = np.asarray(mosaic)[..., 3]
    control_samples = []
    for point in region["control_points"]:
        lon = point["lonlat"][0]
        lat = point["lonlat"][1]
        px = int((lon - image_bounds_lonlat[0]) / (image_bounds_lonlat[2] - image_bounds_lonlat[0]) * mosaic.width)
        py = int((image_bounds_lonlat[3] - lat) / (image_bounds_lonlat[3] - image_bounds_lonlat[1]) * mosaic.height)
        if not (0 <= px < mosaic.width and 0 <= py < mosaic.height and alpha[py, px] == 255):
            raise ValueError("CTX imagery fails coverage at a verified M1 terrain control point")
        control_samples.append({"row": point["row"], "column": point["col"], "pixel": [px, py], "alpha": int(alpha[py, px])})
    region_bytes = (ROOT / "data/processed/jezero-m1/manifest.json").read_bytes()
    manifest = {"schema_version": 1, "status": "source-derived", "publisher": "NASA/JPL Mars Trek; source product USGS Astrogeology",
                "layer": LAYER, "citation": region["sources"]["imagery"]["citation"],
                "license": region["sources"]["imagery"]["license"], "matrix_id": MATRIX_ID,
                "source_mars_equatorial_pixel_m": radius * math.pi / 180 * dx / tile_width,
                "tile_size_px": [tile_width, tile_height], "mosaic_size_px": list(mosaic.size),
                "tile_coverage_lonlat": image_bounds_lonlat, "image_bounds_m": bounds_m,
                "region_manifest_sha256": hashlib.sha256(region_bytes).hexdigest(),
                "output": {"path": "imagery-detail.png", "bytes": target.stat().st_size, "sha256": digest(target)},
                "tile_count": len(records), "tiles": records, "terrain_control_point_coverage": control_samples,
                "limits": "Actual CTX orbital imagery, not numeric elevation or guaranteed surface colour. Effective information is limited by the source mosaic; raster pixel spacing does not establish obstacle-scale accuracy."}
    meta = OUTPUT / "imagery-detail-manifest.json"
    public_meta = PUBLIC / meta.name
    encoded = json.dumps(manifest, indent=2) + "\n"
    meta.write_text(encoded, encoding="utf-8")
    public_meta.write_text(encoded, encoding="utf-8")
    print(json.dumps({"status": "validated", "matrix_id": MATRIX_ID, "tile_count": len(records),
                      "mosaic_size_px": list(mosaic.size), "source_pixel_spacing_m": manifest["source_mars_equatorial_pixel_m"],
                      "output_bytes": target.stat().st_size, "sha256": digest(target)}, indent=2))


if __name__ == "__main__":
    main()
