"""Validate SIM 3464 mapped science-stop outputs against actual source manifests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(region_id: str, public_dir: Path) -> dict:
    region_path = ROOT / "data/processed" / region_id / "manifest.json"
    # The expanded directory name is intentionally distinct from the app region ID.
    if region_id == "jezero-expanded-7p5km":
        expected_id = "expanded-7p5km"
    else:
        expected_id = "jezero-m1"
    region = json.loads(region_path.read_text(encoding="utf-8"))
    manifest_path = public_dir / "manifest.json"
    geo_path = public_dir / "sim3464-location-features.geojson"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    collection = json.loads(geo_path.read_text(encoding="utf-8"))
    source_hash = digest(ROOT / "data/raw/sim3464/sim3464_database.zip")
    region_hash = digest(region_path)
    if manifest["region_id"] != expected_id or manifest["region_manifest_sha256"] != region_hash:
        raise ValueError(f"{expected_id} science-stop manifest targets a different region")
    if manifest["source_archive_sha256"] != source_hash:
        raise ValueError("Science-stop source archive checksum changed")
    if digest(geo_path) != manifest["feature_collection_sha256"]:
        raise ValueError("Science-stop GeoJSON checksum mismatch")
    if len(collection["features"]) != manifest["intersecting_feature_count"]:
        raise ValueError("Science-stop feature count mismatch")
    west, south, east, north = region["bounds_m"]
    for feature in collection["features"]:
        if feature["geometry"]["type"] != "Point" or feature["properties"]["feature_type"] != "small crater":
            raise ValueError("Unexpected source feature type")
        x, y = feature["geometry"]["coordinates"]
        if not (west <= x <= east and south <= y <= north):
            raise ValueError("Science-stop point lies outside selected terrain bounds")
    return {
        "region_id": expected_id,
        "region_manifest_sha256": region_hash,
        "source_archive_sha256": source_hash,
        "feature_count": len(collection["features"]),
        "types": sorted({f["properties"]["feature_type"] for f in collection["features"]}),
        "feature_collection_sha256": manifest["feature_collection_sha256"],
        "positional_limit": manifest["positional_limit"],
        "use_limit": manifest["use_limit"],
    }


def main() -> None:
    products = {
        "pilot": verify("jezero-m1", ROOT / "frontend/public/data/science-destinations"),
        "expanded": verify("jezero-expanded-7p5km", ROOT / "frontend/public/data/expanded/science-destinations"),
    }
    result = {"status": "verified", "source_layer": "USGS SIM 3464 LocationFeatures", "products": products}
    output = ROOT / "evidence/m5/science-destinations-verification.json"
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
