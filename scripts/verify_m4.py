"""M4 preservation, artifact reproducibility and independent actual route audit."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.environment import digest
from backend.routing import ROOT
from scripts.preprocess_environment import build
from scripts.verify_routes import audit


def main():
    old=json.loads((ROOT/'evidence/m3/verification.json').read_text())
    assert digest(ROOT/'backend/routing.py')==old['m2_engine_sha256']
    preserved=old['previous_milestone_evidence']
    for item in preserved:
        assert digest(ROOT/item['path'])==item['sha256'],item['path']
    actual=build()
    assert actual==json.loads((ROOT/'data/processed/environment/environment.json').read_text())
    with TestClient(create_app()) as client:
        environment=client.get('/api/environment')
        assert environment.status_code==200
        assert environment.json()['spatial_overlays']==[]
        region=client.get('/api/region').json()
        # Identity matches the unchanged M3 browser result, not a copied constant.
        previous_route=json.loads((ROOT/'evidence/m3/http-route-response.json').read_text())
        assert region['region_manifest_sha256']==previous_route['region_manifest_sha256']
        points=region['region']['control_points']
        response=client.post('/api/routes',json=dict(start_lonlat=points[0]['lonlat'],end_lonlat=points[1]['lonlat'],
            terrain_weight=100,primary_objective='terrain',region_manifest_sha256=region['region_manifest_sha256']))
        assert response.status_code==200
        result=response.json()
        checks=audit(result,client.app.state.grid)
        assert result==previous_route
        assert result==json.loads((ROOT/'evidence/m4/http-route-response.json').read_text())
    records=[]
    for stage in ['m0','m1','m2','m3']:
        for p in sorted((ROOT/'evidence'/stage).iterdir()):
            if p.is_file():
                records.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)))
    report=dict(status='passed',generated_utc=datetime.now(timezone.utc).isoformat(),
                m2_engine_unchanged=True,m1_manifest_unchanged=True,m0_m2_evidence_matches_m3_snapshot=True,
                m3_and_m4_browser_routes_identical=True,environment_rebuild_matches_runtime=True,
                independent_route_audit=checks,previous_milestone_evidence=records,
                environment_sha256=environment.json()['artifact_sha256'],
                regression_note='This audit does not execute test suites. Session results and exact commands are recorded in STATUS.md and evidence/m4/README.md.',
                limitations=['No environmental spatial overlays','RAD metadata reference only; no dose values',
                             'No current Jezero weather, forecasts, wind, humidity or opacity import',
                             'No per-row ATS/pressure quality flags; finite-only screening',
                             'Ancillary positions remain landing-site-relative, not registered map coordinates'])
    (ROOT/'evidence/m4/verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: historical import reproducible; M0–M2 evidence, M1 identity and M2 engine preserved; M3/M4 actual routes identical.')


if __name__=='__main__':
    main()
