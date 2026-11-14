"""Reproduce M0 acquisition. Existing files are preserved, partial files rejected.

Run from any directory with project .venv Python. Requires curl.exe on Windows.
The DEM is checked against this session's SHA256 before it is promoted from .part.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from inspect_dem import ROOT, OUT, SOURCE, sha256

CATALOG = 'https://astrogeology.usgs.gov/search/map/mars_2020_science_investigation_ctx_dem_mosaic'
API = 'https://trek.nasa.gov/tiles/apidoc/'
DEM = 'https://planetarymaps.usgs.gov/mosaic/mars2020_trn/CTX/ScienceInvestigationMaps_JPL/M20_JezeroCrater_CTXDEM_20m.tif'
DEM_HASH = 'ba7f706ea1b5d63a562f28a7dcf7a7f3c79bce7f048e6974b57e8a33c30d1ba2'
LABEL = 'https://astrogeology.usgs.gov/ckan/dataset/f8ef46b8-d512-4c46-b825-fe9633c38e1c/resource/5691ea08-1db4-4018-a341-e415e716add7/download/m20_jezerocrater_ctxdem_20m.xml'


def fetch(url, dest, expected_hash=None):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        if expected_hash and sha256(dest) != expected_hash:
            raise ValueError(f'Existing file checksum mismatch; preserve and investigate: {dest}')
        print(f'Preserving {dest.relative_to(ROOT)}')
        return
    partial = dest.with_suffix(dest.suffix+'.part')
    if partial.exists():
        raise FileExistsError(f'Inspect/remove incomplete download first: {partial}')
    subprocess.run(['curl.exe', '-fL', '--retry', '2', '--connect-timeout', '20', '--max-time', '300',
                    '-H', 'Origin: http://localhost:5173', '-D', str(dest.with_suffix(dest.suffix+'.headers.txt')),
                    '-o', str(partial), url], check=True)
    if expected_hash and sha256(partial) != expected_hash:
        raise ValueError(f'Upstream file changed or corrupt; preserving partial for investigation: {partial}')
    partial.rename(dest)


def main():
    sources = [(CATALOG, OUT/'ctx-catalog.html'), (API+'trekAPI.html?body=mars', OUT/'trek-api.html'),
               (API+'js/trekApi.js', OUT/'trekApi.js'), (API+'config/config.json', OUT/'trek-config.json'),
               (LABEL, OUT/'ctx-dem-label.xml'), (DEM, SOURCE)]
    for url, dest in sources:
        fetch(url, dest, DEM_HASH if dest == SOURCE else None)
    # Follow the same discovery chain used by the NASA API web page.
    config = json.loads((OUT/'trek-config.json').read_text())['mars']['service_endpoints']
    catalog_url = config['listVisibleLayersUrl'].replace('PROJECTIONTYPE', 'eq')
    fetch(catalog_url, OUT/'trek-layers.json')
    sources.append((catalog_url, OUT/'trek-layers.json'))
    docs = json.loads((OUT/'trek-layers.json').read_text())['response']['docs']
    item = next(d for d in docs if d['productLabel'] == 'JEZ_ctx_B_soc_008_orthoMosaic_6m_Eqc_latTs0_lon0')
    service_url = config['getLayerServiceUrl']+item['item_UUID']
    fetch(service_url, OUT/'trek-ctx-service.json')
    sources.append((service_url, OUT/'trek-ctx-service.json'))
    endpoint = json.loads((OUT/'trek-ctx-service.json').read_text())['response']['docs'][0]['endPoint']
    capabilities_url = endpoint.rstrip('/')+'/1.0.0/WMTSCapabilities.xml'
    fetch(capabilities_url, OUT/'wmts-capabilities.xml')
    sources.append((capabilities_url, OUT/'wmts-capabilities.xml'))
    manifest = dict(generated_utc=datetime.now(timezone.utc).isoformat(),
                    timestamp_note='File modification times record local download completion; existing files are never overwritten',
                    sources=[dict(url=url, path=str(path.relative_to(ROOT)).replace('\\', '/'),
                                  bytes=path.stat().st_size, sha256=sha256(path),
                                  local_download_completed_utc=datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat())
                             for url, path in sources])
    (OUT/'acquisition-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
