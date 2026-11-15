"""Export source-mapped SIM 3464 point features as optional science stops."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fiona
from fiona.transform import transform_geom

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data/raw/sim3464/sim3464_database.zip"
GDB = ROOT / "data/raw/sim3464/extracted/sim3464_JezeroNili_FINAL/Geodatabase/Nili.gdb"
REGION = ROOT / "data/processed/jezero-expanded-7p5km/manifest.json"
OUTPUT = ROOT / "frontend/public/data/expanded/science-destinations"


def build(archive: Path, region_path: Path, output: Path) -> dict:
    if not archive.is_file():
        raise FileNotFoundError(f"Official USGS SIM 3464 archive not found: {archive}")
    if not GDB.is_dir():
        raise FileNotFoundError(f"Extract the official SIM 3464 archive first: {GDB}")
    source_hash = hashlib.sha256(archive.read_bytes()).hexdigest()
    region_bytes = region_path.read_bytes()
    region = json.loads(region_bytes)
    west, south, east, north = region["bounds_m"]
    features = []
    source_counts: dict[str, int] = {}
    with fiona.open(GDB, layer="LocationFeatures") as source:
        source_crs = source.crs_wkt
        for source_index, feature in enumerate(source):
            raw_type = feature["properties"]["TYPE"]
            source_counts[raw_type] = source_counts.get(raw_type, 0) + 1
            geometry = transform_geom(source_crs, region["crs"]["wkt"], feature["geometry"], precision=-1)
            x, y = geometry["coordinates"]
            if not (west <= x <= east and south <= y <= north):
                continue
            # No scientific rank or safety claim: these preserve the published point feature type.
            source_id = int(feature["id"])
            features.append({
                "type": "Feature",
                "id": f"sim3464-location-{source_id:04d}",
                "geometry": {"type": "Point", "coordinates": [x, y]},
                "properties": {
                    "source_feature_id": source_id,
                    "feature_type": raw_type,
                    "display_name": f"SIM 3464 mapped {raw_type} · {len(features) + 1:02d}",
                    "map_label": f"C{len(features) + 1:02d}",
                    "role": "user-selectable science stop; not ranked or safety-screened",
                },
            })

    collection = {"type": "FeatureCollection", "features": features}
    encoded = (json.dumps(collection, separators=(",", ":"), ensure_ascii=False) + "\n").encode()
    output.mkdir(parents=True, exist_ok=True)
    geo_path = output / "sim3464-location-features.geojson"
    geo_path.write_bytes(encoded)
    manifest = {
        "schema_version": 1,
        "status": "source-derived",
        "product_id": "USGS-SIM-3464-LocationFeatures",
        "source": "Sun & Stack (2020), USGS SIM 3464, Nili.gdb / LocationFeatures",
        "source_url": "https://doi.org/10.3133/sim3464",
        "source_archive_sha256": source_hash,
        "source_layer": "LocationFeatures",
        "source_feature_count": sum(source_counts.values()),
        "source_feature_type_counts": source_counts,
        "region_id": region.get("region_id") or region_path.parent.name,
        "region_bounds_m": region["bounds_m"],
        "region_manifest_sha256": hashlib.sha256(region_bytes).hexdigest(),
        "intersecting_feature_count": len(features),
        "feature_collection_sha256": hashlib.sha256(encoded).hexdigest(),
        "feature_collection_bytes": len(encoded),
        "source_crs": "Mars Transverse Mercator; central meridian 77.5 E; sphere R=3,396,190 m; metres",
        "output_crs": region["crs"]["code"],
        "map_scale": "1:75,000",
        "positional_limit": "USGS reports random 100-200 m offsets versus the controlled CTX surface-operations mosaic; no shift applied.",
        "interpretation_limit": "Source points are mapped feature locations, not verified crater centroids, routes, science priorities, hazards, or safety-qualified destinations.",
        "use_limit": "Optional user-selected exploration stops only. No ranking or accessibility claim is made.",
        "source_license": "USGS public domain",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ARCHIVE)
    parser.add_argument("--region", type=Path, default=REGION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(build(args.archive.resolve(), args.region.resolve(), args.output.resolve()), indent=2))


if __name__ == "__main__":
    main()
