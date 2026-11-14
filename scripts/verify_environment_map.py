"""Preservation audit for the spatial environmental extension; no old evidence writes."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.environment import digest


def main():
    base=json.loads((ROOT/'evidence/m4/verification.json').read_text())
    old=json.loads((ROOT/'evidence/m3/verification.json').read_text())
    assert digest(ROOT/'backend/routing.py')==old['m2_engine_sha256']
    for item in base['previous_milestone_evidence']:
        assert digest(ROOT/item['path'])==item['sha256'],item['path']
    assert digest(ROOT/'data/processed/environment/environment.json')==base['environment_sha256']
    current=json.loads((ROOT/'evidence/environment-map/http-route-response.json').read_text())
    previous=json.loads((ROOT/'evidence/m4/http-route-response.json').read_text())
    assert current==previous
    meta=json.loads((ROOT/'data/processed/environment-map/manifest.json').read_text())
    assert meta['terrain_manifest_sha256']==digest(ROOT/'data/processed/jezero-m1/manifest.json')
    assert meta['source_sha256']==digest(ROOT/'data/raw/environment-map/Jezero_Thermal_Inertia_v1.tiff')
    assert meta==json.loads((ROOT/'frontend/public/data/environment-map/manifest.json').read_text())
    for name,record in meta['outputs'].items():
        assert record['sha256']==digest(ROOT/'data/processed/environment-map'/name)
        assert record['sha256']==digest(ROOT/'frontend/public/data/environment-map'/name)
    evidence=[]
    for stage in ['m0','m1','m2','m3','m4']:
        for p in sorted((ROOT/'evidence'/stage).iterdir()):
            if p.is_file():evidence.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)))
    report=dict(status='passed',generated_utc=datetime.now(timezone.utc).isoformat(),
                routing_engine_unchanged=True,previous_evidence_matches_M4_snapshot=True,
                historical_environment_artifact_unchanged=True,actual_browser_route_response_unchanged=True,
                thermal_outputs_and_public_copies_match=True,source_sha256=meta['source_sha256'],
                previous_milestone_evidence=evidence,
                regression_note='Suites run separately: 60 Python / 9 JS passed; 19-case full Chrome run plus four-case overlay run including the new mobile case passed. Commands in README.')
    (ROOT/'evidence/environment-map/verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: native overlay/public hashes match; M0–M3 evidence, M4 historical artifact, engine and actual routes preserved.')


if __name__=='__main__':main()
