"""Fetch the verified CRISM MTRDR summary product that intersects our pilot."""
from __future__ import annotations

import hashlib
import json
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/crism"
PDS_BASE = "https://pds-geosciences.wustl.edu/mro/mro-m-crism-5-rdr-mptargeted-v1/mrocr_4001/mtrdr/2007/2007_057/frt000047a3/"
PRODUCT = "frt000047a3_07_if166j_mtr3"
FILES = {
    "frt000047a3_07_sr166j_mtr3.img": (PDS_BASE + "frt000047a3_07_sr166j_mtr3.img", 164_250_240, "10eb37e4dd8f2f95a6c3ebdfda5a0b066bd02c33bb2d1e03558c024f3b16ec2d"),
    "frt000047a3_07_sr166j_mtr3.hdr": (PDS_BASE + "frt000047a3_07_sr166j_mtr3.hdr", 1_802, "dfb912294226519e500701bd5e215e15dc5b747212c25d4bef2287f4d39a61e4"),
    "frt000047a3_07_sr166j_mtr3.lbl": (PDS_BASE + "frt000047a3_07_sr166j_mtr3.lbl", 8_394, "10ac486d769f8fdc82ed08fb88f42e37dd1f4cb29a0b6db57a39a7e6cb7ac3c9"),
}
ODE_URL = "https://oderest.rsl.wustl.edu/live2?" + urllib.parse.urlencode({
    "query": "product", "target": "mars", "results": "opm", "ihid": "MRO", "iid": "CRISM",
    "pt": "MTRDR", "pdsid": PRODUCT, "output": "JSON", "limit": 1,
})


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def retrieve(url: str, path: Path, expected_bytes: int, expected_sha: str) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        actual = digest(path)
        if path.stat().st_size != expected_bytes or actual != expected_sha:
            raise ValueError(f"Existing CRISM asset fails its pinned identity; preserving it: {path}")
    else:
        part = path.with_suffix(path.suffix + ".part")
        if part.exists():
            raise FileExistsError(f"Inspect incomplete asset before retry; not overwriting {part}")
        digest_state = hashlib.sha256()
        size = 0
        request = urllib.request.Request(url, headers={"User-Agent": "MARSWALK scientific data prototype"})
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, context=context, timeout=90) as response, part.open("xb") as stream:
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > expected_bytes:
                    raise ValueError(f"Source exceeded expected size for {path.name}")
                digest_state.update(block)
                stream.write(block)
        if size != expected_bytes or digest_state.hexdigest() != expected_sha:
            raise ValueError(f"CRISM size/checksum mismatch for {path.name}; partial preserved at {part}")
        part.replace(path)
    return {"url": url, "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size, "sha256": expected_sha}


def main() -> None:
    records = [retrieve(url, RAW / name, size, digest) for name, (url, size, digest) in FILES.items()]
    metadata_path = RAW / f"{PRODUCT}-ode.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        request = urllib.request.Request(ODE_URL, headers={"User-Agent": "MARSWALK scientific data prototype"})
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(request, context=context, timeout=90) as response:
            metadata = json.loads(response.read())
        products = metadata.get("ODEResults", {}).get("Products", {}).get("Product", [])
        product = products[0] if isinstance(products, list) and len(products) == 1 else products
        if product.get("pdsid", "").lower() != PRODUCT or not product.get("Footprint_GL_geometry"):
            raise ValueError("ODE did not return the expected georeferenced MTRDR product")
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    records.append({"url": ODE_URL, "path": str(metadata_path.relative_to(ROOT)).replace("\\", "/"),
                    "bytes": metadata_path.stat().st_size,
                    "sha256": digest(metadata_path)})
    print(json.dumps({"product_id": PRODUCT, "assets": records}, indent=2))


if __name__ == "__main__":
    main()
