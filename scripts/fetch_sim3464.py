"""Download the USGS SIM 3464 GIS package without overwriting an existing copy."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

URL = "https://pubs.usgs.gov/sim/3464/sim3464_database.zip"
DESTINATION = Path(__file__).resolve().parents[1] / "data/raw/sim3464/sim3464_database.zip"


def main() -> None:
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    if DESTINATION.exists():
        raise FileExistsError(f"Refusing to overwrite existing raw source: {DESTINATION}")
    temporary = DESTINATION.with_suffix(".zip.part")
    digest = hashlib.sha256()
    byte_count = 0
    try:
        request = urllib.request.Request(URL, headers={"User-Agent": "MARSWALK-data-acquisition/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("xb") as output:
            expected = int(response.headers.get("Content-Length", "0"))
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
                byte_count += len(block)
        if expected and byte_count != expected:
            raise IOError(f"Incomplete download: {byte_count} of {expected} bytes")
        with temporary.open("rb") as source:
            if source.read(4) != b"PK\x03\x04":
                raise IOError("Downloaded file is not a ZIP archive")
        temporary.replace(DESTINATION)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    report = {"source_url": URL, "path": str(DESTINATION), "bytes": byte_count,
              "sha256": digest.hexdigest(), "content_length": expected or None}
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
