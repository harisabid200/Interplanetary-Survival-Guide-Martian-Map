"""Explicitly synthetic routing fixtures. Never used by the real-data CLI/demo."""
import math
import unittest

import numpy as np
from affine import Affine

from backend.routing import RoutingError, TerrainGrid

MARS_CRS='+proj=eqc +lat_ts=18.4663 +lon_0=0 +R=3396190 +units=m +no_defs'


def synthetic(z, valid=None, slope=None, slope_valid=None):
    z=np.asarray(z,dtype=float)
    return TerrainGrid(z,np.ones(z.shape,dtype=bool) if valid is None else valid,
                       np.zeros(z.shape) if slope is None else slope,
                       np.ones(z.shape,dtype=bool) if slope_valid is None else slope_valid,
                       Affine(20,0,4351380,0,-20,1095540),MARS_CRS,
                       {'status':'explicitly synthetic unit-test fixture, excluded from demo outputs'})


def lonlat(grid,row,col):
    return [float(grid.lon[row,col]),float(grid.lat[row,col])]


def run(grid,start,end,**kwargs):
    return grid.compare(lonlat(grid,*start),lonlat(grid,*end),**kwargs)


class SyntheticRoutingTests(unittest.TestCase):
    def test_flat_grid_shortest_diagonals_and_mars_distance(self):
        grid=synthetic(np.zeros((5,5)))
        result=run(grid,(1,1),(3,3))
        for route in result['routes']:
            self.assertEqual(route['cells'],[[1,1],[2,2],[3,3]])
            expected=sum(grid.geod.inv(*lonlat(grid,i,i),*lonlat(grid,i+1,i+1))[2] for i in [1,2])
            self.assertAlmostEqual(route['metrics']['distance_m'],expected,places=9)
            self.assertEqual(route['metrics']['positive_ascent_m'],0)
            self.assertEqual(route['metrics']['max_sampled_segment_slope_deg'],0)
        self.assertTrue(result['identical_paths'])

    def test_zero_terrain_weight_matches_distance(self):
        grid=synthetic(np.arange(25).reshape(5,5))
        result=run(grid,(0,0),(4,4),terrain_weight=0)
        self.assertTrue(result['identical_paths'])
        self.assertEqual(result['routes'][0]['metrics'],result['routes'][1]['metrics'])

    def test_steep_synthetic_hill_gets_longer_lower_grade_detour(self):
        z=np.zeros((7,9)); z[3,3:6]=100
        grid=synthetic(z)
        result=run(grid,(3,1),(3,7),terrain_weight=100)
        distance,terrain=result['routes']
        self.assertGreater(terrain['metrics']['distance_m'],distance['metrics']['distance_m'])
        self.assertLess(terrain['metrics']['max_sampled_segment_slope_deg'],distance['metrics']['max_sampled_segment_slope_deg'])
        self.assertTrue(all(z[r,c]==0 for r,c in terrain['cells']))

    def test_blocked_wall_returns_no_geometry(self):
        valid=np.ones((7,7),dtype=bool); valid[:,3]=False
        result=run(synthetic(np.zeros((7,7)),valid),(3,1),(3,5))
        self.assertEqual(result['status'],'no_path')
        self.assertIsNone(result['identical_paths'])
        for route in result['routes']:
            self.assertIsNone(route['geometry']); self.assertIsNone(route['metrics'])
            self.assertEqual(route['cells'],[]); self.assertEqual(route['profile'],[])

    def test_two_blocked_cardinals_prevent_diagonal_corner_cut(self):
        grid=synthetic(np.zeros((2,2)),[[True,False],[False,True]])
        self.assertEqual(run(grid,(0,0),(1,1))['status'],'no_path')

    def test_one_blocked_cardinal_also_prevents_diagonal_corner_cut(self):
        grid=synthetic(np.zeros((2,2)),[[True,False],[True,True]])
        for route in run(grid,(0,0),(1,1))['routes']:
            self.assertEqual(route['cells'],[[0,0],[1,0],[1,1]])

    def test_start_equals_end_is_single_point(self):
        grid=synthetic(np.full((3,3),100.))
        result=run(grid,(1,1),(1,1))
        self.assertTrue(result['identical_paths'])
        for route in result['routes']:
            self.assertEqual(route['geometry']['type'],'Point')
            self.assertEqual(route['cells'],[[1,1]])
            self.assertEqual(len(route['profile']),1)
            for name in ['distance_m','positive_ascent_m','descent_m','max_sampled_segment_slope_deg','objective_cost_m']:
                self.assertEqual(route['metrics'][name],0)

    def test_nodata_endpoint_rejected(self):
        valid=np.ones((3,3),dtype=bool); valid[1,1]=False
        grid=synthetic(np.zeros((3,3)),valid)
        with self.assertRaises(RoutingError) as error:
            run(grid,(1,1),(0,0))
        self.assertEqual(error.exception.code,'nodata_endpoint')

    def test_nonfinite_terrain_not_traversed(self):
        for missing in [np.nan,np.inf]:
            z=np.zeros((3,3)); z[:,1]=missing
            grid=synthetic(z)
            self.assertEqual(run(grid,(1,0),(1,2))['status'],'no_path')

    def test_required_slope_neighbors_share_mask_for_both_objectives(self):
        slope_valid=np.ones((3,3),dtype=bool); slope_valid[:,1]=False
        grid=synthetic(np.zeros((3,3)),slope_valid=slope_valid)
        result=run(grid,(1,0),(1,2))
        self.assertEqual([r['status'] for r in result['routes']],['no_path','no_path'])

    def test_assumed_cell_slope_threshold_blocks_same_cells_in_both_objectives(self):
        slope=np.zeros((3,3)); slope[:,1]=25
        grid=synthetic(np.zeros((3,3)),slope=slope)
        result=run(grid,(1,0),(1,2),max_cell_slope_deg=20)
        self.assertEqual([r['status'] for r in result['routes']],['no_path','no_path'])
        self.assertEqual(result['coverage']['eligible_cells'],6)

    def test_excluded_endpoint_is_invalid_request_not_no_path(self):
        slope=np.zeros((3,3)); slope[1,1]=25
        grid=synthetic(np.zeros((3,3)),slope=slope)
        with self.assertRaises(RoutingError) as error:
            run(grid,(1,1),(0,0),max_cell_slope_deg=20)
        self.assertEqual(error.exception.code,'excluded_endpoint')

    def test_cell_threshold_is_not_mislabeled_as_segment_limit(self):
        grid=synthetic([[0,100]])  # synthetic cell gradients supplied as zero
        route=run(grid,(0,0),(0,1),max_cell_slope_deg=0)['routes'][0]
        self.assertGreater(route['metrics']['max_sampled_segment_slope_deg'],0)

    def test_coordinate_domain_and_nonfinite_requests_rejected(self):
        grid=synthetic(np.zeros((3,3)))
        end=lonlat(grid,1,1)
        for point in [[np.nan,18],[77,np.inf],[True,18],['77',18],[-1,18],[360,18],[77,91],[77],None,np.array(77),[[77],[18]]]:
            with self.subTest(point=point),self.assertRaises(RoutingError):
                grid.compare(point,end)

    def test_exact_edges_and_outside_cells_rejected_without_clamping(self):
        grid=synthetic(np.zeros((3,3)))
        west,north=grid.affine @ (0,0); east,south=grid.affine @ (3,3)
        self.assertEqual(grid.cell_from_projected(west,north),(0,0))
        for point in [(east,north),(west,south),(west-1,north),(west,north+1)]:
            with self.subTest(point=point),self.assertRaises(RoutingError) as error:
                grid.cell_from_projected(*point)
            self.assertEqual(error.exception.code,'outside_coverage')
        for point in [grid.to_ll.transform(east,north),grid.to_ll.transform(west,south)]:
            with self.assertRaises(RoutingError):
                grid.compare(list(point),lonlat(grid,1,1))

    def test_endpoint_offsets_explicit_and_not_added_to_path_length(self):
        grid=synthetic(np.zeros((3,3)))
        center=grid.affine @ (1.5,1.5)
        requested=list(grid.to_ll.transform(center[0]+5,center[1]+5))
        result=grid.compare(requested,lonlat(grid,1,1))
        self.assertGreater(result['endpoints']['start']['snap_distance_m'],7)
        self.assertEqual(result['routes'][0]['metrics']['distance_m'],0)

    def test_invalid_cost_parameters_rejected(self):
        grid=synthetic(np.zeros((3,3)))
        for weight in [-1,np.nan,np.inf,True,'100']:
            with self.subTest(weight=weight),self.assertRaises(RoutingError):
                run(grid,(0,0),(1,1),terrain_weight=weight)
        for limit in [-1,91,np.nan,True]:
            with self.subTest(limit=limit),self.assertRaises(RoutingError):
                run(grid,(0,0),(1,1),max_cell_slope_deg=limit)
        with self.assertRaises(RoutingError):
            run(grid,(0,0),(1,1),algorithm='unverified')

    def test_reverse_profile_ascent_and_descent(self):
        grid=synthetic([[0,10,5]])
        out=run(grid,(0,0),(0,2))['routes'][0]
        back=run(grid,(0,2),(0,0))['routes'][0]
        self.assertAlmostEqual(out['metrics']['distance_m'],back['metrics']['distance_m'])
        self.assertEqual(out['metrics']['positive_ascent_m'],10)
        self.assertEqual(back['metrics']['positive_ascent_m'],5)
        self.assertEqual(out['metrics']['descent_m'],5)
        self.assertEqual(back['metrics']['descent_m'],10)
        self.assertEqual([p['elevation_m'] for p in out['profile']],[0,10,5])
        self.assertGreater(out['profile'][1]['incoming_segment_slope_deg'],0)
        self.assertLess(out['profile'][2]['incoming_segment_slope_deg'],0)

    def test_astar_matches_dijkstra_on_seeded_synthetic_grids(self):
        for seed in range(8):
            rng=np.random.default_rng(seed)
            z=rng.uniform(0,30,(5,5)); valid=rng.random((5,5))>.15
            valid[0,0]=valid[4,4]=True
            grid=synthetic(z,valid)
            astar=run(grid,(0,0),(4,4),terrain_weight=20)
            oracle=run(grid,(0,0),(4,4),terrain_weight=20,algorithm='dijkstra')
            self.assertEqual(astar['status'],oracle['status'])
            for a,b in zip(astar['routes'],oracle['routes']):
                if a['status']=='ok':
                    self.assertAlmostEqual(a['metrics']['objective_cost_m'],b['metrics']['objective_cost_m'],places=7)

    def test_repeated_comparisons_are_deterministic(self):
        grid=synthetic(np.arange(49).reshape(7,7))
        self.assertEqual(run(grid,(0,0),(6,6)),run(grid,(0,0),(6,6)))

    def test_wrong_planet_crs_rejected(self):
        with self.assertRaises(RoutingError) as error:
            TerrainGrid([[0]],[[1]],[[0]],[[1]],Affine(20,0,0,0,-20,20),'EPSG:3857')
        self.assertEqual(error.exception.code,'invalid_crs')

    def test_cost_overflow_is_invalid_request_not_false_no_path(self):
        grid=synthetic([[0,100]])
        with self.assertRaises(RoutingError) as error:
            run(grid,(0,0),(0,1),terrain_weight=1e308)
        self.assertEqual(error.exception.code,'cost_overflow')


if __name__=='__main__':
    unittest.main()
