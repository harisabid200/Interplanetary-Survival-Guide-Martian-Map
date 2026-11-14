"""Audit source-derived geology, CRISM and THEMIS products for expanded terrain."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    region_path = ROOT/'data/processed/jezero-expanded-7p5km/manifest.json'
    region = read(region_path)
    bounds = region['bounds_m']
    region_hash = digest(region_path)

    geology_dir = ROOT/'data/processed/jezero-expanded-7p5km/geology'
    geology = read(geology_dir/'manifest.json')
    geojson = geology_dir/'sim3464-units.geojson'
    if geology['region_manifest_sha256'] != region_hash:
        raise ValueError('SIM 3464 manifest is for a different terrain region')
    if digest(geojson) != geology['feature_collection_sha256']:
        raise ValueError('SIM 3464 GeoJSON checksum mismatch')

    crism_dir = ROOT/'data/processed/jezero-expanded-7p5km/crism'
    crism = read(crism_dir/'manifest.json')
    if crism['terrain_manifest_sha256'] != region_hash:
        raise ValueError('CRISM manifest is for a different terrain region')
    for name, record in crism['outputs'].items():
        path = crism_dir/name
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError(f'CRISM product checksum mismatch: {name}')

    thermal_dir = ROOT/'data/processed/jezero-expanded-7p5km/environment-map'
    thermal = read(thermal_dir/'manifest.json')
    if thermal['terrain_manifest_sha256'] != region_hash:
        raise ValueError('THEMIS manifest is for a different terrain region')
    thermal_bounds = thermal['bounds_map_m']
    if not (thermal_bounds[0] <= bounds[0] and thermal_bounds[1] <= bounds[1]
            and thermal_bounds[2] >= bounds[2] and thermal_bounds[3] >= bounds[3]):
        raise ValueError('Transformed THEMIS footprint does not contain the expanded DEM extent')
    for name, record in thermal['outputs'].items():
        path = thermal_dir/name
        if path.stat().st_size != record['bytes'] or digest(path) != record['sha256']:
            raise ValueError(f'THEMIS product checksum mismatch: {name}')
    if thermal['valid_pixels'] != thermal['total_pixels']:
        raise ValueError('Unexpected missing THEMIS pixels in the expanded source crop')

    result = {
        'status': 'verified',
        'region_id': region['region_id'],
        'region_manifest_sha256': region_hash,
        'geology': {
            'source_archive_sha256': geology['source_archive_sha256'],
            'source_feature_count': geology['source_feature_count'],
            'intersecting_polygons': geology['region_intersecting_feature_count'],
            'geojson_sha256': geology['feature_collection_sha256'],
            'registration_uncertainty': '100-200 m; USGS reported random offset; no shift applied',
        },
        'crism': {
            'product_id': crism['product_id'],
            'source_image_sha256': crism['source_image_sha256'],
            'footprint_intersection_m2': crism['region_intersection_area_map_m2'],
            'region_area_m2': crism['region_area_map_m2'],
            'area_intersection_fraction': crism['region_area_intersection_fraction'],
            'valid_grid_cells': crism['valid_pixels'],
            'total_grid_cells': crism['total_pixels'],
            'valid_fraction': crism['valid_fraction'],
            'interpretation': 'D2300 spectral parameter only; not mineral concentration or resource detection',
        },
        'themis': {
            'source_sha256': thermal['source_sha256'],
            'quantity': thermal['quantity'],
            'source_pixel_size_m': thermal['source_pixel_size_m'],
            'native_grid_shape_width_height': [thermal['width'], thermal['height']],
            'valid_pixels': thermal['valid_pixels'],
            'total_pixels': thermal['total_pixels'],
            'bounds_map_m': thermal_bounds,
            'contains_expanded_terrain_bounds': True,
            'interpretation': 'Published thermal inertia; not temperature, weather, dust or radiation',
        },
        'limitations': [
            'CTX imagery remains visual context, not numeric terrain.',
            'CRISM cells without a valid observed value remain nodata/transparent.',
            'Geology retains its source registration uncertainty and qualitative map meaning.',
            'THEMIS is a published derived thermal property at native 100 m source spacing.',
        ],
    }
    output = ROOT/'evidence/map-expansion/layer-footprints.json'
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
