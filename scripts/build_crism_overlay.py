"""Build an integrity-checked, region-clipped CRISM D2300 observation layer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer
from rasterio.enums import Resampling
from rasterio.warp import reproject
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/crism"
REGION = ROOT / "data/processed/jezero-m1/manifest.json"
OUTPUT = ROOT / "data/processed/crism"
PUBLIC = ROOT / "frontend/public/data/crism"
PRODUCT = "frt000047a3_07_if166j_mtr3"
SUMMARY = "frt000047a3_07_sr166j_mtr3"
IMG_SHA256 = "10eb37e4dd8f2f95a6c3ebdfda5a0b066bd02c33bb2d1e03558c024f3b16ec2d"
IMG_BYTES = 164_250_240
STRETCH = (-0.01, 0.02)
COLORS = ((77, 132, 170), (182, 183, 163), (229, 145, 88))


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def clip_polygon(poly, axis, bound, keep_greater):
    result = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        inside_a = a[axis] >= bound if keep_greater else a[axis] <= bound
        inside_b = b[axis] >= bound if keep_greater else b[axis] <= bound
        if inside_a != inside_b:
            fraction = (bound - a[axis]) / (b[axis] - a[axis])
            result.append((a[0] + fraction * (b[0] - a[0]), a[1] + fraction * (b[1] - a[1])))
        if inside_b:
            result.append(b)
    return result


def polygon_area(poly) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])) / 2)


def parse_ode_polygon(wkt: str):
    match = re.fullmatch(r"\s*POLYGON\s*\(\((.*?)\)\)\s*", wkt)
    if not match:
        raise ValueError("Only the verified single-ring ODE product footprint is supported")
    return [tuple(map(float, pair.split())) for pair in match.group(1).split(",")]


def interpolate_color(values: np.ndarray) -> np.ndarray:
    low, high = STRETCH
    scaled = np.clip((values - low) / (high - low), 0, 1)
    out = np.empty((*values.shape, 4), dtype=np.uint8)
    for mask, left, right, fraction in (
        (scaled <= .5, COLORS[0], COLORS[1], scaled * 2),
        (scaled > .5, COLORS[1], COLORS[2], (scaled - .5) * 2),
    ):
        for channel in range(3):
            out[..., channel][mask] = (left[channel] + (right[channel] - left[channel]) * fraction[mask]).astype(np.uint8)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW)
    parser.add_argument("--region", type=Path, default=REGION)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--public", type=Path, default=PUBLIC)
    args = parser.parse_args()
    raw, region_path = args.raw.resolve(), args.region.resolve()
    img = raw / f"{SUMMARY}.img"
    header = raw / f"{SUMMARY}.hdr"
    label = raw / f"{SUMMARY}.lbl"
    ode_path = raw / f"{PRODUCT}-ode.json"
    for path in (img, header, label, ode_path, region_path):
        if not path.is_file():
            raise FileNotFoundError(f"Required verified CRISM input missing: {path}")
    if img.stat().st_size != IMG_BYTES or digest(img) != IMG_SHA256:
        raise ValueError("CRISM refined-summary image differs from its verified PDS identity")
    label_text = label.read_text(encoding="ascii", errors="strict")
    header_text = header.read_text(encoding="ascii", errors="strict")
    for expected in ("PRODUCT_ID                     = \"FRT000047A3_07_SR166J_MTR3\"", "PRODUCT_TYPE                  = MPTARGETED_RDR",
                     "MAP_PROJECTION_TYPE          = \"EQUIRECTANGULAR\"", "COORDINATE_SYSTEM_NAME       = \"PLANETOCENTRIC\"",
                     "SAMPLE_BITS              = 32", '"D2300"'):
        if expected not in label_text:
            raise ValueError(f"CRISM PDS label missing verified field: {expected}")
    if "data ignore value = 6.55350000e+04" not in header_text.lower():
        raise ValueError("CRISM ENVI header missing its declared ignore value")
    ode = json.loads(ode_path.read_text(encoding="utf-8"))["ODEResults"]["Products"]["Product"]
    if isinstance(ode, list):
        ode = next((item for item in ode if item.get("pdsid", "").lower() == PRODUCT), None)
    if not ode or ode.get("pdsid", "").lower() != PRODUCT or ode.get("pt") != "MTRDR":
        raise ValueError("ODE product identity/type mismatch")
    region_bytes = region_path.read_bytes()
    region = json.loads(region_bytes)
    target_crs = CRS.from_wkt(region["crs"]["wkt"])
    with rasterio.open(img) as source:
        if (source.width, source.height, source.count, source.dtypes[0], source.nodata) != (847, 808, 60, "float32", 65535.0):
            raise ValueError("Unexpected MTRDR SR dimensions, datatype, or missing value")
        if tuple(source.descriptions).count("D2300") != 1:
            raise ValueError("Expected unique D2300 spectral-summary band is missing")
        source_crs_obj = CRS.from_wkt(source.crs.to_wkt())
        if not math.isclose(source_crs_obj.ellipsoid.semi_major_metre, 3_394_839.813316312, abs_tol=.01):
            raise ValueError("Unexpected MTRDR Mars reference sphere")
        src_proj = source.crs.to_dict()
        if src_proj.get("proj") != "eqc" or not math.isclose(src_proj.get("lat_ts", 0), 15, abs_tol=1e-9):
            raise ValueError("Unexpected MTRDR equirectangular projection")
        band_index = source.descriptions.index("D2300") + 1
        to_target = Transformer.from_crs(source_crs_obj.geodetic_crs, target_crs, always_xy=True)
        footprint_lonlat = parse_ode_polygon(ode["Footprint_GL_geometry"])
        footprint_map = [to_target.transform(lon, lat) for lon, lat in footprint_lonlat]
        west, south, east, north = region["bounds_m"]
        clipped = footprint_map
        for axis, bound, greater in ((0, west, True), (0, east, False), (1, south, True), (1, north, False)):
            clipped = clip_polygon(clipped, axis, bound, greater)
        if len(clipped) < 3:
            raise ValueError("ODE footprint does not intersect the project pilot")
        intersection_area = polygon_area(clipped)

        width, height = region["width"], region["height"]
        transform = Affine(*region["affine"])
        nodata = np.float32(-9999)
        values = np.full((height, width), nodata, dtype=np.float32)
        reproject(source=rasterio.band(source, band_index), destination=values,
                  src_transform=source.transform, src_crs=source.crs, src_nodata=source.nodata,
                  dst_transform=transform, dst_crs=target_crs, dst_nodata=nodata,
                  resampling=Resampling.nearest, init_dest_nodata=True)
        valid = np.isfinite(values) & (values != nodata)
        if not valid.any():
            raise ValueError("No actual D2300 pixels intersect the pilot")
        v = values[valid]
        rgba = interpolate_color(values)
        rgba[~valid, 3] = 0
        source_crs = source_crs_obj.to_wkt()
        source_resolution_m = [float(item) for item in source.res]
        source_shape = [source.height, source.width]

    args.output.mkdir(parents=True, exist_ok=True)
    args.public.mkdir(parents=True, exist_ok=True)
    processed = args.output.resolve()
    public = args.public.resolve()
    files = {
        "d2300.f32": np.where(valid, values, np.nan).astype("<f4").tobytes(),
        "valid.u8": valid.astype("uint8").tobytes(),
    }
    for name, payload in files.items():
        (processed / name).write_bytes(payload)
        (public / name).write_bytes(payload)
    Image.fromarray(rgba).save(processed / "d2300.png")
    Image.fromarray(rgba).save(public / "d2300.png")
    footprint_feature = {"type": "Feature", "properties": {"product_id": PRODUCT},
                         "geometry": {"type": "Polygon", "coordinates": [[list(point) for point in clipped + [clipped[0]]]]}}
    footprint_geojson = {"type": "FeatureCollection", "features": [footprint_feature]}
    footprint_bytes = (json.dumps(footprint_geojson, separators=(",", ":")) + "\n").encode()
    (processed / "footprint.geojson").write_bytes(footprint_bytes)
    (public / "footprint.geojson").write_bytes(footprint_bytes)

    manifest = {
        "schema_version": 1, "status": "source-derived", "product_id": PRODUCT,
        "summary_product_id": f"FRT000047A3_07_SR166J_MTR3", "band_index_1based": band_index,
        "quantity": "D2300 spectral summary parameter", "unit": "dimensionless band-math index",
        "interpretation": "2.3 micrometre spectral drop parameter; a spectral-shape indicator used in hydrated-mineral/clay studies, not a mineral identification by itself.",
        "source_description": "MTRDR SR is the CRISM team's noise-mitigated/refined spectral summary product; processing may interpolate flagged outlier pixels.",
        "source_url": "https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/2007/2007_057/frt000047a3/",
        "ode_product_url": ode["ProductURL"], "ode_label_url": ode["LabelURL"],
        "observation_time_utc": [ode["UTC_start_time"], ode["UTC_stop_time"]],
        "observation_id": ode["Observation_id"], "orbit": ode.get("Start_orbit_number"),
        "source_pixel_size_m": 18, "source_shape_lines_samples": source_shape,
        "source_image_bytes": IMG_BYTES, "source_image_sha256": IMG_SHA256,
        "source_label_sha256": digest(label), "source_header_sha256": digest(header),
        "source_crs_wkt": source_crs,
        "source_crs": {"sphere_radius_m": 3_394_839.813316312, "projection": "equirectangular", "standard_parallel_deg": 15,
                       "central_meridian_deg": 0, "coordinates": "metres; planetocentric latitude; positive-east longitude"},
        "ode_footprint_lonlat_wkt": ode["Footprint_GL_geometry"],
        "pilot_intersection_area_map_m2": intersection_area,
        "pilot_area_map_m2": (east - west) * (north - south),
        "pilot_area_intersection_fraction": intersection_area / ((east - west) * (north - south)),
        "region_intersection_area_map_m2": intersection_area,
        "region_area_map_m2": (east - west) * (north - south),
        "region_area_intersection_fraction": intersection_area / ((east - west) * (north - south)),
        "footprint_area_geojson_sha256": hashlib.sha256(footprint_bytes).hexdigest(),
        "crs": region["crs"], "width": width, "height": height,
        "affine": list(transform)[:6], "bounds_m": region["bounds_m"],
        "terrain_manifest_sha256": hashlib.sha256(region_bytes).hexdigest(),
        "resampling": "nearest-neighbour from native 18 m summary parameter to the 20 m app grid; nodata preserved",
        "valid_pixels": int(valid.sum()), "total_pixels": int(valid.size), "valid_fraction": float(valid.mean()),
        "range": [float(v.min()), float(v.max())], "median": float(np.median(v)),
        "p95": float(np.percentile(v, 95)), "positive_value_fraction": float((v > 0).mean()),
        "display_stretch": list(STRETCH), "display_colors_negative_neutral_positive": [list(x) for x in COLORS],
        "limits": "Parameter values are spectral indices, not concentration or categorical mineral detections. Positive values do not independently confirm a mineral; noise, spectral overlap, atmospheric/residual effects, surface mixtures, and SR outlier interpolation matter. No mineral threshold or safety/resource scoring is applied. Coverage is only the actual ODE footprint intersection; remaining pilot cells stay nodata.",
        "outputs": {name: {"bytes": (processed / name).stat().st_size, "sha256": digest(processed / name)} for name in ["d2300.f32", "valid.u8", "d2300.png", "footprint.geojson"]},
    }
    encoded = (json.dumps(manifest, indent=2, allow_nan=False) + "\n").encode()
    for destination in (processed / "manifest.json", public / "manifest.json"):
        destination.write_bytes(encoded)
    print(json.dumps({key: manifest[key] for key in ("product_id", "quantity", "pilot_intersection_area_map_m2", "valid_pixels", "valid_fraction", "range", "median", "p95")}, indent=2))


if __name__ == "__main__":
    main()
