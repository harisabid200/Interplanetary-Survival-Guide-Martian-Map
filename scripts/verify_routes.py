"""M2 real Jezero smoke test + independent path/metric audit and Dijkstra check.

No synthetic fixture is imported. The endpoints are M1 verification cells,
not invented science targets. Outputs are reproducible scientific evidence.
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pyproj import CRS, Geod, Transformer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.routing import DEFAULT_REGION, ROOT, RoutingError, TerrainGrid, sha256

OUT=ROOT/'evidence/m2'


def audit(result, grid):
    # Re-read source arrays separately; do not use engine's distance cache or metrics.
    manifest=json.loads((DEFAULT_REGION/'manifest.json').read_text())
    z=np.fromfile(DEFAULT_REGION/'elevation.f32',dtype='<f4').reshape(grid.height,grid.width)
    local_slope=np.fromfile(DEFAULT_REGION/'slope.f32',dtype='<f4').reshape(z.shape)
    valid=np.fromfile(DEFAULT_REGION/'valid.u8',dtype='uint8').reshape(z.shape).astype(bool)
    valid &= np.fromfile(DEFAULT_REGION/'slope-valid.u8',dtype='uint8').reshape(z.shape).astype(bool)
    valid &= np.isfinite(z) & np.isfinite(local_slope)
    limit=result['parameters']['max_cell_slope_deg']
    if limit is not None:
        valid &= local_slope <= limit
    crs=CRS(manifest['crs']['wkt'])
    to_ll=Transformer.from_crs(crs,crs.geodetic_crs,always_xy=True)
    geod=Geod(a=3396190,b=3396190)
    a,_,c,_,e,f=manifest['affine']
    checks=[]
    for route in result['routes']:
        assert route['status']=='ok'
        cells=route['cells']
        assert cells[0]==[result['endpoints']['start']['row'],result['endpoints']['start']['col']]
        assert cells[-1]==[result['endpoints']['end']['row'],result['endpoints']['end']['col']]
        assert len(cells)==len(route['profile'])
        assert len(cells)==len(set(map(tuple,cells))), 'Path contains a loop'
        coordinates=[list(to_ll.transform(c+(cc+.5)*a,f+(rr+.5)*e)) for rr,cc in cells]
        np.testing.assert_allclose(route['geometry']['coordinates'],coordinates,rtol=0,atol=1e-12)
        distances=[]; changes=[]; slopes=[]
        for i,(r,col) in enumerate(cells):
            assert 0<=r<grid.height and 0<=col<grid.width and valid[r,col]
            assert route['profile'][i]['elevation_m']==float(z[r,col])
            assert route['profile'][i]['cell_slope_deg']==float(local_slope[r,col])
            if i:
                pr,pc=cells[i-1]; dr,dc=r-pr,col-pc
                assert max(abs(dr),abs(dc))==1
                if dr and dc:
                    assert valid[pr+dr,pc] and valid[pr,pc+dc]
                d=geod.inv(*coordinates[i-1],*coordinates[i])[2]
                dz=float(z[r,col])-float(z[pr,pc])
                distances.append(d); changes.append(dz)
                slope=math.degrees(math.atan2(dz,d)); slopes.append(slope)
                assert math.isclose(route['profile'][i]['incoming_segment_slope_deg'],slope,abs_tol=1e-9)
            assert math.isclose(route['profile'][i]['distance_m'],sum(distances),abs_tol=1e-8)
        expected=dict(distance_m=sum(distances),positive_ascent_m=sum(max(x,0) for x in changes),
                      descent_m=sum(max(-x,0) for x in changes),max_sampled_segment_slope_deg=max(map(abs,slopes),default=0),
                      max_sampled_cell_slope_deg=max(float(local_slope[r,col]) for r,col in cells),
                      terrain_penalty_cost_m=sum(d*route['effective_terrain_weight']*(abs(dz)/d)**2 for d,dz in zip(distances,changes)),
                      objective_cost_m=sum(d*(1+route['effective_terrain_weight']*(abs(dz)/d)**2) for d,dz in zip(distances,changes)))
        for key,value in expected.items():
            assert math.isclose(route['metrics'][key],value,rel_tol=1e-12,abs_tol=1e-7),(key,route['metrics'][key],value)
        checks.append(dict(objective=route['objective'],verified_cells=len(cells),all_cells_and_diagonal_support_valid=True,
                           independently_recomputed_metrics=expected))
    return checks


def preview(result, manifest):
    with Image.open(DEFAULT_REGION/'imagery.png') as im:
        image=np.asarray(im.convert('RGB'))
    w,s,e,n=manifest['bounds_m']; iw,isouth,ie,inorth=manifest['imagery_bounds_m']
    size=700
    xx,yy=np.meshgrid(w+(np.arange(size)+.5)/size*(e-w),n-(np.arange(size)+.5)/size*(n-s))
    px=np.floor((xx-iw)/(ie-iw)*image.shape[1]).astype(int)
    py=np.floor((inorth-yy)/(inorth-isouth)*image.shape[0]).astype(int)
    canvas=Image.new('RGB',(size,size+120),'#172124')
    canvas.paste(Image.fromarray(image[py,px]),(0,65))
    draw=ImageDraw.Draw(canvas)
    try:
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    except OSError:
        font=ImageFont.load_default()
    draw.text((16,10),'MARSWALK / M2 · REAL JEZERO CTX TERRAIN',font=font,fill='#f5e8cd')
    draw.text((16,33),'5 × 5 km proposed pilot · N ↑ · no safety classification',font=font,fill='#c2c9c3')
    colors=['#67e0ef','#ffb176']
    for route,color in zip(result['routes'],colors):
        points=[((col+.5)/manifest['width']*size,(row+.5)/manifest['height']*size+65) for row,col in route['cells']]
        draw.line(points,fill='#192326',width=7)
        draw.line(points,fill=color,width=3)
        for label,(x,y) in [('START',points[0]),('END',points[-1])]:
            draw.ellipse((x-5,y-5,x+5,y+5),fill='#172124',outline='white',width=2)
            draw.text((min(x+9,size-45),max(67,y-20)),label,font=font,fill='white',stroke_width=1,stroke_fill='#172124')
    for i,(route,color) in enumerate(zip(result['routes'],colors)):
        metrics=route['metrics']
        draw.text((16,size+70+i*23),f"{route['objective'].upper()}: {metrics['distance_m']:.1f} m | ascent {metrics['positive_ascent_m']:.1f} m | max segment {metrics['max_sampled_segment_slope_deg']:.2f}°",font=font,fill=color)
    canvas.save(OUT/'routes-preview.png')


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    t=time.perf_counter(); grid=TerrainGrid.load(); load_s=time.perf_counter()-t
    manifest=json.loads((DEFAULT_REGION/'manifest.json').read_text())
    # Real M1 reference #1 -> #2, not designated base or science target.
    start,end=[manifest['control_points'][i]['lonlat'] for i in [0,1]]
    t=time.perf_counter(); result=grid.compare(start,end,terrain_weight=100); astar_s=time.perf_counter()-t
    checks=audit(result,grid)
    t=time.perf_counter(); oracle=grid.compare(start,end,terrain_weight=100,algorithm='dijkstra'); dijkstra_s=time.perf_counter()-t
    for a,b in zip(result['routes'],oracle['routes']):
        assert math.isclose(a['metrics']['objective_cost_m'],b['metrics']['objective_cost_m'],rel_tol=1e-12,abs_tol=1e-7)
    assert result==grid.compare(start,end,terrain_weight=100), 'Determinism failed'
    same=grid.compare(start,start)
    assert all(r['geometry']['type']=='Point' and r['metrics']['distance_m']==0 for r in same['routes'])
    # Find a real low-gradient pair to exercise an assumed 10° exclusion.
    limited_start=[float(grid.lon[125,50]),float(grid.lat[125,50])]
    limited_end=[float(grid.lon[125,200]),float(grid.lat[125,200])]
    limited=grid.compare(limited_start,limited_end,terrain_weight=100,max_cell_slope_deg=10)
    limited_checks=audit(limited,grid)
    for name,data in [('real-routes.json',result),('real-routes-cell-limit-10deg.json',limited)]:
        (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    geojson=dict(type='FeatureCollection',features=[dict(type='Feature',geometry=r['geometry'],
                 properties=dict(objective=r['objective'],**r['metrics'])) for r in result['routes']],
                 coordinate_reference='Mars sphere R=3396190 m; positive-east longitude, planetocentric latitude. NOT Earth WGS84 despite GeoJSON-shaped serialization.')
    (OUT/'real-routes.mars.json').write_text(json.dumps(geojson,indent=2)+'\n',encoding='utf-8')
    preview(result,manifest)
    report=dict(status='passed',data='real M1 Jezero CTX products only; no synthetic fixtures',
                endpoints='M1 verification sample 1 to sample 2, not actual base or science target',
                terrain_weight=100,default_run_cell_slope_limit=None,checks=checks,
                real_cell_slope_limit_10deg_checks=limited_checks,
                repeated_result_identical=True,astar_costs_match_dijkstra=True,
                real_same_cell_route_passed=True,identical_paths=result['identical_paths'],
                timings_seconds=dict(load_and_edge_precompute=load_s,astar_both_objectives=astar_s,dijkstra_both_objectives=dijkstra_s),
                input_manifest_sha256=sha256(DEFAULT_REGION/'manifest.json'),routing_source_sha256=sha256(ROOT/'backend/routing.py'))
    (OUT/'verification.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
