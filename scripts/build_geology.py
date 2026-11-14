"""Extract real SIM 3464 geologic units overlapping a manifested MARSWALK region."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

import fiona
from fiona.transform import transform_geom

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/raw/sim3464/sim3464_database.zip"
GDB = ROOT / "data/raw/sim3464/extracted/sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
REGION = ROOT / "data/processed/jezero-m1/manifest.json"
OUTPUT = ROOT / "frontend/public/data/geology"


def extract_gdb() -> None:
    if (GDB / "a00000001.gdbtable").is_file():
        return
    if not ARCHIVE.is_file():
        raise FileNotFoundError(f"Official USGS archive not found: {ARCHIVE}")
    with ZipFile(ARCHIVE) as archive:
        prefix = "sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb/"
        for member in archive.infolist():
            if not member.filename.startswith(prefix) or member.is_dir() or ".sr.lock" in member.filename:
                continue
            name = member.filename[len(prefix):]
            if not re.fullmatch(r"(?:a[0-9a-f]{8}(?:\.[A-Za-z0-9_.-]+)?|gdb|timestamps)", name):
                raise ValueError(f"Unexpected geodatabase member: {member.filename}")
            target = GDB / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(member))


def nested_points(coordinates):
    if isinstance(coordinates, (list, tuple)) and coordinates and isinstance(coordinates[0], (int, float)):
        yield coordinates
    elif isinstance(coordinates, (list, tuple)):
        for child in coordinates:
            yield from nested_points(child)


def _inside(point, rect):
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _segment_hits_rect(a, b, rect):
    dx, dy = b[0] - a[0], b[1] - a[1]
    low, high = 0.0, 1.0
    for p, q in ((-dx, a[0] - rect[0]), (dx, rect[2] - a[0]),
                 (-dy, a[1] - rect[1]), (dy, rect[3] - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            low = max(low, t)
        else:
            high = min(high, t)
        if low > high:
            return False
    return True


def _point_in_ring(point, ring):
    x, y = point
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[1] > y) != (b[1] > y):
            crossing_x = (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]) + a[0]
            if x < crossing_x:
                inside = not inside
    return inside


def intersects_rect(geometry, rect):
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    corners = ((rect[0], rect[1]), (rect[0], rect[3]), (rect[2], rect[1]), (rect[2], rect[3]))
    for polygon in polygons:
        rings = polygon
        for ring in rings:
            if any(_inside(point, rect) for point in ring):
                return True
            if any(_segment_hits_rect(a, b, rect) for a, b in zip(ring, ring[1:])):
                return True
        for corner in corners:
            if _point_in_ring(corner, rings[0]) and not any(_point_in_ring(corner, hole) for hole in rings[1:]):
                return True
    return False


def main() -> None:
    global ARCHIVE, REGION, OUTPUT, GDB
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--region", type=Path, default=REGION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--processed", type=Path, default=None, help="optional ignored processed-output mirror")
    parser.add_argument("--evidence", type=Path, default=None, help="optional small audit-artifact copy")
    args = parser.parse_args()
    ARCHIVE = args.archive.resolve()
    REGION = args.region.resolve()
    OUTPUT = args.output.resolve()
    GDB = ARCHIVE.parent / "extracted/sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
    extract_gdb()

    manifest_bytes = REGION.read_bytes()
    region = json.loads(manifest_bytes)
    west, south, east, north = region["bounds_m"]
    output_features = []
    source_feature_count = 0
    with fiona.open(GDB, layer="GeoUnits_v1") as source:
        source_crs = source.crs_wkt
        target_crs = region["crs"]["wkt"]
        for feature in source:
            source_feature_count += 1
            transformed = transform_geom(source_crs, target_crs, feature["geometry"], precision=-1)
            geometry = {"type": transformed["type"], "coordinates": transformed["coordinates"]}
            points = list(nested_points(geometry["coordinates"]))
            if not points:
                continue
            bounds = (min(p[0] for p in points), min(p[1] for p in points),
                      max(p[0] for p in points), max(p[1] for p in points))
            if bounds[0] > east or bounds[2] < west or bounds[1] > north or bounds[3] < south:
                continue
            if not intersects_rect(geometry, (west, south, east, north)):
                continue
            properties = feature["properties"]
            output_features.append({
                "type": "Feature",
                "id": int(feature["id"]),
                "geometry": geometry,
                "properties": {
                    "map_unit": properties["symbol"],
                    "unit_name": properties["name"],
                    "color_id": int(properties["Color_ID"]),
                    "source_feature_id": int(feature["id"]),
                    "source_bounds_map_m": [round(v, 3) for v in bounds],
                },
            })

    unit_order = sorted({feature["properties"]["map_unit"] for feature in output_features})
    color_index = {symbol: index for index, symbol in enumerate(unit_order)}
    for feature in output_features:
        feature["properties"]["style_index"] = color_index[feature["properties"]["map_unit"]]

    args.output.mkdir(parents=True, exist_ok=True)
    geojson_path = args.output / "sim3464-units.geojson"
    document = {"type": "FeatureCollection", "features": output_features}
    encoded = (json.dumps(document, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    geojson_path.write_bytes(encoded)
    output_manifest = {
        "schema_version": 1,
        "status": "source-derived",
        "source": "Sun & Stack (2020), USGS SIM 3464, GeoUnits_v1",
        "source_url": "https://pubs.usgs.gov/sim/3464/sim3464_database.zip",
        "source_archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
        "source_feature_count": source_feature_count,
        "pilot_intersecting_feature_count": len(output_features),
        "region_intersecting_feature_count": len(output_features),
        "feature_collection_sha256": hashlib.sha256(encoded).hexdigest(),
        "feature_collection_bytes": len(encoded),
        "source_crs": "Mars 2000 sphere, Mars Transverse Mercator; central meridian 77.5 E; metres; R=3396190 m",
        "output_crs": region["crs"]["code"],
        "pilot_bounds_m": region["bounds_m"],
        "region_bounds_m": region["bounds_m"],
        "map_scale": "1:75,000",
        "positional_limit": "USGS README reports random 100–200 m offsets versus the controlled CTX surface-operations mosaic; no auto-shift applied.",
        "interpretation_limit": "Published regional geologic interpretation; unit polygons do not establish mineral concentration, accessible water, or present-day resources.",
        "display_style": "Categorical colors distinguish mapped unit symbols only; they do not represent measurements or hazard scores.",
        "source_license": "USGS public domain",
        "region_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    (args.output / "manifest.json").write_text(json.dumps(output_manifest, indent=2) + "\n", encoding="utf-8")
    for mirror, names in ((args.processed, ("manifest.json", "sim3464-units.geojson")),
                          (args.evidence, ("manifest.json", "sim3464-units.geojson"))):
        if mirror:
            mirror.mkdir(parents=True, exist_ok=True)
            for name in names:
                (mirror / name).write_bytes((args.output / name).read_bytes())
    print(json.dumps(output_manifest, indent=2))


if __name__ == "__main__":
    main()
