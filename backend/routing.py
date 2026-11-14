"""M2 eight-neighbor A* with actual Mars spherical geodesic edge distances.

The heuristic is geodesic distance to goal: triangle inequality makes it a
consistent lower bound when every edge costs at least its geodesic length.
No interpolated terrain, diagonal corner cutting, or physiological model.
"""
from __future__ import annotations

import hashlib
import heapq
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from pyproj import CRS, Transformer

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGION = ROOT / 'data/processed/jezero-m1'
DIRECTIONS = ((-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1))
MODEL = 'marswalk-grid-astar-v1'


class RoutingError(ValueError):
    """Invalid request/endpoint or inconsistent scientific inputs, not no-path."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def finite_number(value, name, minimum=0, maximum=None):
    if isinstance(value, (bool, np.bool_, str, bytes)):
        raise RoutingError('invalid_parameter', f'{name} must be a finite number')
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise RoutingError('invalid_parameter', f'{name} must be a finite number') from None
    if not math.isfinite(number) or number < minimum or (maximum is not None and number > maximum):
        raise RoutingError('invalid_parameter', f'{name} is outside its permitted finite range')
    return number


class TerrainGrid:
    def __init__(self, elevation, valid, slope_deg, slope_valid, affine, crs, provenance=None):
        self.elevation = np.array(elevation, dtype=np.float64, copy=True)
        self.slope = np.array(slope_deg, dtype=np.float64, copy=True)
        elevation_mask = np.array(valid, dtype=bool, copy=True)
        slope_mask = np.array(slope_valid, dtype=bool, copy=True)
        if self.elevation.ndim != 2 or not self.elevation.size:
            raise RoutingError('invalid_grid', 'Elevation must be a nonempty 2D array')
        if any(a.shape != self.elevation.shape for a in [self.slope, elevation_mask, slope_mask]):
            raise RoutingError('invalid_grid', 'Terrain arrays and masks must have identical shapes')
        self.height, self.width = self.elevation.shape
        self.affine = Affine(*list(affine)[:6])
        if (self.affine.a <= 0 or self.affine.e >= 0 or self.affine.b != 0 or self.affine.d != 0
                or not all(math.isfinite(x) for x in self.affine)):
            raise RoutingError('invalid_grid', 'Expected finite north-up raster transform in metres')
        self.crs = CRS(crs)
        if (not self.crs.is_projected or self.crs.ellipsoid.semi_major_metre != 3396190
                or self.crs.ellipsoid.semi_minor_metre != 3396190
                or any(a.unit_conversion_factor != 1 for a in self.crs.axis_info)):
            raise RoutingError('invalid_crs', 'Expected projected metres on the verified Mars sphere R=3396190 m')
        self.to_ll = Transformer.from_crs(self.crs, self.crs.geodetic_crs, always_xy=True)
        self.to_xy = Transformer.from_crs(self.crs.geodetic_crs, self.crs, always_xy=True)
        self.geod = self.crs.get_geod()
        self.valid = (elevation_mask & slope_mask & np.isfinite(self.elevation)
                      & np.isfinite(self.slope) & (self.slope >= 0) & (self.slope < 90))
        self.provenance = provenance or {'status': 'explicitly synthetic test fixture'}
        xx, yy = np.meshgrid(self.affine.c+(np.arange(self.width)+.5)*self.affine.a,
                             self.affine.f+(np.arange(self.height)+.5)*self.affine.e)
        self.lon, self.lat = self.to_ll.transform(xx, yy)
        if not (np.isfinite(self.lon).all() and np.isfinite(self.lat).all()):
            raise RoutingError('invalid_crs', 'Nonfinite Mars coordinates')
        self.edges = {}
        # Precompute real distances once, including no out-of-bounds pairs.
        for dr, dc in DIRECTIONS:
            rs, cs = slice(max(0,-dr), min(self.height,self.height-dr)), slice(max(0,-dc), min(self.width,self.width-dc))
            rt, ct = slice(max(0,dr), min(self.height,self.height+dr)), slice(max(0,dc), min(self.width,self.width+dc))
            distances = np.full(self.elevation.shape, np.nan)
            if self.lon[rs, cs].size:
                _, _, d = self.geod.inv(self.lon[rs,cs], self.lat[rs,cs], self.lon[rt,ct], self.lat[rt,ct])
                if not (np.isfinite(d).all() and (d > 0).all()):
                    raise RoutingError('invalid_grid', 'Neighbor distances must be finite and positive')
                distances[rs,cs] = d
            self.edges[(dr,dc)] = distances
        for array in [self.elevation, self.slope, self.valid, self.lon, self.lat, *self.edges.values()]:
            array.flags.writeable = False

    @classmethod
    def load(cls, directory=DEFAULT_REGION):
        directory = Path(directory)
        manifest_path = directory/'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        names = ['dem.tif', 'slope.tif', 'valid-mask.tif', 'slope-mask.tif']
        arrays = []
        for name in names:
            if sha256(directory/name) != manifest['outputs'][name]['sha256']:
                raise RoutingError('checksum_mismatch', f'{name} differs from the M1 manifest; revalidate inputs')
            with rasterio.open(directory/name) as ds:
                if (ds.shape != (manifest['height'],manifest['width'])
                        or list(ds.transform)[:6] != manifest['affine']
                        or CRS(ds.crs) != CRS(manifest['crs']['wkt']) or ds.count != 1):
                    raise RoutingError('invalid_grid', f'{name} geometry differs from the M1 manifest')
                a = ds.read(1, masked=True)
                if name.endswith('mask.tif'):
                    arrays.append(a.filled(0) == 1)
                else:
                    arrays.append(a.filled(np.nan))
        dem, slope, valid, slope_valid = arrays
        return cls(dem, valid, slope, slope_valid, manifest['affine'], manifest['crs']['wkt'],
                   dict(status='verified M1 real-data products', region_manifest_sha256=sha256(manifest_path),
                        input_sha256={name:manifest['outputs'][name]['sha256'] for name in names},
                        source_dem=manifest['sources']['dem'], pixel_spacing_projected_m=[20,20],
                        crs_wkt=manifest['crs']['wkt'], bounds_m=manifest['bounds_m'],
                        bounds_lonlat=manifest['bounds_lonlat'], versions=manifest['versions']))

    def cell_from_projected(self, x, y):
        if not (math.isfinite(x) and math.isfinite(y)):
            raise RoutingError('invalid_coordinate', 'Projected coordinates must be finite')
        c, r = (~self.affine) @ (x,y)
        # Transform roundoff at exact edges: <=2e-7 m on the 20 m grid.
        c = round(c) if abs(c-round(c)) <= 1e-8 else c
        r = round(r) if abs(r-round(r)) <= 1e-8 else r
        row, col = math.floor(r), math.floor(c)
        if not (0 <= row < self.height and 0 <= col < self.width):
            raise RoutingError('outside_coverage', 'Endpoint is outside the native pilot DEM')
        return row,col

    def endpoint(self, lonlat, mask):
        if (not isinstance(lonlat, (list,tuple,np.ndarray)) or getattr(lonlat,'ndim',1) != 1
                or len(lonlat) != 2 or not all(np.isscalar(value) for value in lonlat)):
            raise RoutingError('invalid_coordinate', 'Use [positive-east longitude, planetocentric latitude]')
        lon = finite_number(lonlat[0], 'longitude', 0, 360)
        lat = finite_number(lonlat[1], 'latitude', -90, 90)
        if lon == 360:
            raise RoutingError('invalid_coordinate', 'Longitude must be in [0,360)')
        r,c = self.cell_from_projected(*self.to_xy.transform(lon,lat))
        if not self.valid[r,c]:
            raise RoutingError('nodata_endpoint', 'Endpoint has missing elevation or required slope neighbors')
        if not mask[r,c]:
            raise RoutingError('excluded_endpoint', 'Endpoint exceeds the assumed cell-slope limit')
        center = self.affine @ (c+.5,r+.5)
        center_ll = [float(self.lon[r,c]),float(self.lat[r,c])]
        _,_,offset = self.geod.inv(lon,lat,*center_ll)
        return dict(requested_lonlat=[lon,lat], row=r,col=c, snapped_lonlat=center_ll,
                    snapped_projected_m=list(center), snap_distance_m=float(offset))

    def _search(self, start, end, mask, weight, algorithm):
        sr,sc=start; er,ec=end
        if algorithm == 'astar':
            _,_,heuristic = self.geod.inv(self.lon,self.lat,
                                          np.full(self.lon.shape,self.lon[er,ec]),
                                          np.full(self.lat.shape,self.lat[er,ec]))
        else:
            heuristic = np.zeros(self.elevation.shape)
        size=self.width*self.height
        cost=np.full(size,np.inf)
        previous=np.full(size,-1,dtype=np.int64)
        first,last=sr*self.width+sc,er*self.width+ec
        cost[first]=0
        heap=[(float(heuristic[sr,sc]),0.,first)]
        expanded=0
        while heap:
            _,g,index=heapq.heappop(heap)
            if g != cost[index]:
                continue
            expanded+=1
            if index == last:
                path=[]
                while index != -1:
                    path.append(divmod(int(index),self.width))
                    index=previous[index]
                return path[::-1],float(g),expanded
            r,c=divmod(index,self.width)
            for dr,dc in DIRECTIONS:
                nr,nc=r+dr,c+dc
                if not (0 <= nr < self.height and 0 <= nc < self.width and mask[nr,nc]):
                    continue
                if dr and dc and not (mask[r+dr,c] and mask[r,c+dc]):
                    continue
                distance=float(self.edges[(dr,dc)][r,c])
                dz=float(self.elevation[nr,nc]-self.elevation[r,c])
                try:
                    segment_cost=distance*(1+weight*(abs(dz)/distance)**2)
                except OverflowError:
                    raise RoutingError('cost_overflow', 'Terrain weight produced a nonfinite edge cost') from None
                if not math.isfinite(segment_cost):
                    raise RoutingError('cost_overflow', 'Terrain weight produced a nonfinite edge cost')
                candidate=g+segment_cost
                if not math.isfinite(candidate):
                    raise RoutingError('cost_overflow', 'Accumulated objective cost overflowed')
                neighbor=nr*self.width+nc
                if candidate < cost[neighbor]:
                    cost[neighbor]=candidate
                    previous[neighbor]=index
                    heapq.heappush(heap,(candidate+float(heuristic[nr,nc]),candidate,neighbor))
        return [],None,expanded

    def _result(self, path, score, expanded, objective, weight, mask):
        result=dict(objective=objective, effective_terrain_weight=weight,
                    algorithm='A*; geodesic lower bound',expanded_cells=expanded)
        if not path:
            return dict(**result,status='no_path',reason='No connected path through the shared eligible grid',
                        geometry=None,cells=[],profile=[],metrics=None)
        coords=[[float(self.lon[r,c]),float(self.lat[r,c])] for r,c in path]
        distances=[]; deltas=[]
        for (r,c),(nr,nc) in zip(path,path[1:]):
            distances.append(float(self.edges[(nr-r,nc-c)][r,c]))
            deltas.append(float(self.elevation[nr,nc]-self.elevation[r,c]))
        cumulative=np.r_[0.,np.cumsum(distances)]
        segment_slopes=[math.degrees(math.atan2(dz,d)) for dz,d in zip(deltas,distances)]
        elevation=[float(self.elevation[r,c]) for r,c in path]
        cell_slopes=[float(self.slope[r,c]) for r,c in path]
        profile=[dict(distance_m=float(cumulative[i]),elevation_m=z,cell_slope_deg=cell_slopes[i],
                      incoming_segment_slope_deg=0. if i==0 else segment_slopes[i-1]) for i,z in enumerate(elevation)]
        return dict(**result,status='ok',geometry=dict(type='Point' if len(coords)==1 else 'LineString',
                                                      coordinates=coords[0] if len(coords)==1 else coords),
                    cells=[list(p) for p in path],profile=profile,
                    metrics=dict(distance_m=float(cumulative[-1]),positive_ascent_m=sum(max(dz,0.) for dz in deltas),
                                 descent_m=sum(max(-dz,0.) for dz in deltas),
                                 max_sampled_segment_slope_deg=max(map(abs,segment_slopes),default=0.),
                                 max_sampled_cell_slope_deg=max(cell_slopes), elevation_range_m=[min(elevation),max(elevation)],
                                 terrain_penalty_cost_m=sum(d*weight*(abs(dz)/d)**2 for d,dz in zip(distances,deltas)),
                                 objective_cost_m=score),
                    coverage=dict(all_cells_eligible=True,all_diagonal_support_cells_eligible=True,
                                  native_cells=len(path),eligible_cells_in_region=int(mask.sum())))

    def compare(self, start_lonlat, end_lonlat, terrain_weight=100., max_cell_slope_deg=None, algorithm='astar'):
        weight=finite_number(terrain_weight,'terrain_weight')
        limit=None if max_cell_slope_deg is None else finite_number(max_cell_slope_deg,'max_cell_slope_deg',0,90)
        if algorithm not in ('astar','dijkstra'):
            raise RoutingError('invalid_parameter','algorithm must be astar or dijkstra')
        mask=self.valid if limit is None else self.valid & (self.slope <= limit)
        start=self.endpoint(start_lonlat,mask); end=self.endpoint(end_lonlat,mask)
        routes=[]
        for objective,effective_weight in [('distance',0.),('terrain',weight)]:
            path,score,expanded=self._search((start['row'],start['col']),(end['row'],end['col']),mask,effective_weight,algorithm)
            result=self._result(path,score,expanded,objective,effective_weight,mask)
            result['algorithm']='A*; geodesic lower bound' if algorithm=='astar' else 'Dijkstra; zero heuristic'
            routes.append(result)
        return dict(schema_version=1,status='ok' if routes[0]['status']=='ok' else 'no_path',
                    model=MODEL, routing_source_sha256=sha256(Path(__file__)),
                    endpoints=dict(start=start,end=end),
                    parameters=dict(terrain_weight=weight,max_cell_slope_deg=limit,
                                    slope_limit_applies_to='native local cell slope, not segment slope',
                                    common_valid_mask='finite DEM AND valid finite slope with required neighbors; optional cell-slope limit',
                                    diagonal_rule='both adjacent cardinal cells must also be eligible'),
                    distance_definition='Sum of Mars sphere geodesic distances between successive native cell centers; excludes endpoint snap offsets',
                    cost_definition='distance: d; terrain: d * (1 + terrain_weight * (abs(delta_z) / d)^2)',
                    cost_units_note='Terrain objective cost has penalized metre units; it is not traveled distance, effort or time.',
                    geometry_coordinate_order='positive-east longitude,planetocentric latitude in degrees',
                    grid_coordinate_order='zero-based crop row,column',
                    identical_paths=None if not routes[0]['cells'] else routes[0]['cells']==routes[1]['cells'],
                    coverage=dict(width=self.width,height=self.height,valid_cells=int(self.valid.sum()),eligible_cells=int(mask.sum())),
                    provenance=self.provenance,routes=routes,
                    assumptions=['Heuristic terrain penalty, not a physiological effort, travel time or safety model.',
                                 '20 m sampling cannot resolve astronaut-scale rocks, holes or other hazards.',
                                 'Optional cell-slope exclusion is user-assumed and does not certify travel; segment slopes may exceed it.',
                                 'Endpoints snap to native cell centers; reported path metrics exclude snap offsets.',
                                 'No terrain interpolation, path smoothing, invented no-path geometry or environmental data.',
                                 'A single-cell route has Point geometry, zero distance/ascent and one profile sample.'])
