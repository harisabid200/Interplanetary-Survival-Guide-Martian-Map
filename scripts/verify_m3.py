"""Independent M3 actual HTTP-adapter and source-preservation evidence.

Uses TestClient for reproducibility; Chrome smoke tests separately exercise TCP.
Never overwrites prior milestone artifacts.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.routing import DEFAULT_REGION,ROOT,sha256
from scripts.verify_routes import audit


def main():
    out=ROOT/'evidence/m3'
    old=json.loads((ROOT/'evidence/m2/verification.json').read_text())
    assert sha256(ROOT/'backend/routing.py')==old['routing_source_sha256'],'M2 engine unexpectedly changed'
    with TestClient(create_app()) as client:
        region=client.get('/api/region').json()
        points=region['region']['control_points']
        response=client.post('/api/routes',json=dict(start_lonlat=points[0]['lonlat'],end_lonlat=points[1]['lonlat'],
            terrain_weight=100,primary_objective='terrain',region_manifest_sha256=region['region_manifest_sha256']))
        assert response.status_code==200
        result=response.json()
        checks=audit(result,client.app.state.grid)
        tcp_result=json.loads((out/'http-route-response.json').read_text())
        assert tcp_result==result,'Browser HTTP result differs from independent adapter result'
    files=[]
    for milestone in ['m0','m1','m2']:
        for path in sorted((ROOT/f'evidence/{milestone}').iterdir()):
            if path.is_file():
                files.append(dict(path=str(path.relative_to(ROOT)).replace('\\','/'),sha256=sha256(path)))
    snapshot=[]
    for path in sorted((ROOT/'docs/history/pre-expansion').iterdir()):
        snapshot.append(dict(path=str(path.relative_to(ROOT)).replace('\\','/'),sha256=sha256(path)))
    fetched=[]
    for filename,url in [
        ('sim3464-catalog.html','https://pubs.usgs.gov/publication/sim3464'),
        ('sim3464_readme.txt','https://pubs.usgs.gov/sim/3464/sim3464_readme.txt'),
        ('sim3464_metadata.xml','https://pubs.usgs.gov/sim/3464/sim3464_metadata.xml')]:
        path=out/filename
        fetched.append(dict(path=str(path.relative_to(ROOT)).replace('\\','/'),url=url,sha256=sha256(path),
                            local_download_completed_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()))
    report=dict(status='passed',generated_utc=datetime.now(timezone.utc).isoformat(),
                m2_engine_unchanged=True,m2_engine_sha256=sha256(ROOT/'backend/routing.py'),
                m1_manifest_unchanged=sha256(DEFAULT_REGION/'manifest.json')==old['input_manifest_sha256'],
                browser_tcp_and_adapter_results_identical=True,independent_real_route_audit=checks,
                previous_milestone_evidence=files,pre_expansion_documents=snapshot,
                new_source_metadata=fetched,
                remaining_sources='MEDA/MARCI/RAD/CRISM documentation researched; no numeric/environmental or scientific spatial asset imported')
    assert report['m1_manifest_unchanged']
    (out/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({key:report[key] for key in ['status','m2_engine_unchanged','m1_manifest_unchanged','browser_tcp_and_adapter_results_identical']},indent=2))


if __name__=='__main__':
    main()
