"""M3 API contract checks against actual M1 Jezero products / M2 engine."""
import unittest
import json

import numpy as np
from fastapi.testclient import TestClient

from backend.api import create_app


class MissionApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=create_app()
        cls.context=TestClient(cls.app)
        cls.client=cls.context.__enter__()
        cls.region=cls.client.get('/api/region').json()
        points=cls.region['region']['control_points']
        cls.body={'start_lonlat':points[0]['lonlat'],'end_lonlat':points[1]['lonlat'],
                  'terrain_weight':100.,'max_cell_slope_deg':None,'primary_objective':'distance',
                  'region_manifest_sha256':cls.region['region_manifest_sha256']}

    @classmethod
    def tearDownClass(cls):
        cls.context.__exit__(None,None,None)

    def test_region_exposes_verified_provenance_and_planned_capabilities(self):
        self.assertTrue(self.region['routing_available'])
        self.assertEqual(self.region['region']['crs']['radius_m'],3396190)
        self.assertEqual(self.region['availability']['terrain'],'validated')
        self.assertEqual(self.region['availability']['minerals'],'validated_CRISM_D2300_parameter')
        self.assertEqual(self.region['availability']['geology'],'validated_SIM3464_units')
        self.assertEqual(self.region['availability']['science_destinations'],'validated_SIM3464_mapped_points')
        self.assertEqual(self.region['availability']['ancient_water'],'cited_historical_context_only')
        self.assertEqual(self.region['availability']['budgets_recommendations'],'implemented_user_assumed_budget_and_terrain_screen')
        self.assertIn('Gale_reference_only',self.region['availability']['radiation'])

    def test_actual_routes_match_m2_evidence(self):
        response=self.client.post('/api/routes',json=self.body)
        self.assertEqual(response.status_code,200)
        result=response.json()
        self.assertEqual(result['region_manifest_sha256'],self.body['region_manifest_sha256'])
        self.assertAlmostEqual(result['routes'][0]['metrics']['distance_m'],3507.303793900053,places=6)
        self.assertAlmostEqual(result['routes'][1]['metrics']['distance_m'],3964.3021282773148,places=6)
        self.assertEqual(result['primary_objective'],'distance')
        self.assertEqual(result['routes'][0]['geometry']['type'],'LineString')

    def test_mission_budget_computes_independent_outbound_and_return_routes(self):
        payload={**self.body,'walking_speed_kmh':4.0,'available_time_min':180.0,'science_stop_min':20.0,'reserve_min':15.0}
        response=self.client.post('/api/mission-budget',json=payload)
        self.assertEqual(response.status_code,200)
        body=response.json()
        self.assertEqual(body['status'],'ok')
        self.assertEqual(body['assessment'],'arithmetic_only_not_an_operational_or_safety_guarantee')
        for objective,budget in body['budgets'].items():
            self.assertGreater(budget['outbound_distance_m'],0)
            self.assertGreater(budget['return_distance_m'],0)
            self.assertAlmostEqual(budget['round_trip_distance_m'],budget['outbound_distance_m']+budget['return_distance_m'])
            self.assertAlmostEqual(budget['walking_time_min'],budget['round_trip_distance_m']/4000*60)
            self.assertAlmostEqual(budget['required_total_min'],budget['walking_time_min']+35)
            self.assertEqual(budget['within_time_budget'],budget['required_total_min']<=180)
        self.assertEqual(body['region_manifest_sha256'],self.body['region_manifest_sha256'])

    def test_mission_budget_reports_no_path_without_fabricating_a_total(self):
        grid=self.app.state.grid
        rows,cols=np.where(grid.valid & (grid.slope<=.1))
        start=[float(grid.lon[rows[0],cols[0]]),float(grid.lat[rows[0],cols[0]])]
        end=[float(grid.lon[rows[-1],cols[-1]]),float(grid.lat[rows[-1],cols[-1]])]
        payload={**self.body,'start_lonlat':start,'end_lonlat':end,'max_cell_slope_deg':.1,
                 'walking_speed_kmh':4.0,'available_time_min':180.0,'science_stop_min':20.0,'reserve_min':15.0}
        response=self.client.post('/api/mission-budget',json=payload)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'no_path')
        self.assertNotIn('budgets',response.json())

    def test_mission_budget_requires_explicit_finite_user_assumptions(self):
        payload={**self.body,'walking_speed_kmh':4.0,'available_time_min':180.0,'science_stop_min':20.0,'reserve_min':15.0}
        for patch in [{'walking_speed_kmh':0},{'walking_speed_kmh':'4'},
                      {'science_stop_min':-1},{'reserve_min':-1},{'missing':'extra'}]:
            with self.subTest(patch=patch):
                self.assertEqual(self.client.post('/api/mission-budget',json={**payload,**patch}).status_code,422)
        nonfinite=json.dumps({**payload,'available_time_min':float('inf')})
        response=self.client.post('/api/mission-budget',content=nonfinite,headers={'content-type':'application/json'})
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.post('/api/mission-budget',json={**payload,'region_manifest_sha256':'0'*64}).status_code,409)

    def test_same_cell_actual_point_geometry(self):
        body={**self.body,'end_lonlat':self.body['start_lonlat']}
        result=self.client.post('/api/routes',json=body).json()
        self.assertTrue(result['identical_paths'])
        self.assertEqual(result['routes'][0]['geometry']['type'],'Point')
        self.assertEqual(result['routes'][0]['metrics']['distance_m'],0)

    def test_real_no_path_under_assumed_cell_limit_has_no_geometry(self):
        grid=self.app.state.grid
        rows,cols=np.where(grid.valid & (grid.slope<=.1))
        self.assertGreater(len(rows),1)
        start=[float(grid.lon[rows[0],cols[0]]),float(grid.lat[rows[0],cols[0]])]
        end=[float(grid.lon[rows[-1],cols[-1]]),float(grid.lat[rows[-1],cols[-1]])]
        response=self.client.post('/api/routes',json={**self.body,'start_lonlat':start,'end_lonlat':end,'max_cell_slope_deg':.1})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['status'],'no_path')
        self.assertTrue(all(route['geometry'] is None for route in response.json()['routes']))

    def test_mismatch_is_rejected(self):
        response=self.client.post('/api/routes',json={**self.body,'region_manifest_sha256':'0'*64})
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['code'],'dataset_mismatch')

    def test_outside_and_excluded_endpoints_are_honest_errors(self):
        response=self.client.post('/api/routes',json={**self.body,'start_lonlat':[77.,18.]})
        self.assertEqual(response.status_code,422)
        self.assertEqual(response.json()['code'],'outside_coverage')
        response=self.client.post('/api/routes',json={**self.body,'max_cell_slope_deg':0})
        self.assertEqual(response.json()['code'],'excluded_endpoint')

    def test_strict_finite_schema_and_unknown_fields(self):
        for patch in [{'start_lonlat':['77',18]},{'start_lonlat':[True,18]}, {'start_lonlat':[77]},
                      {'terrain_weight':-1},{'terrain_weight':1e7},{'max_cell_slope_deg':91},
                      {'primary_objective':'safest'},{'unexpected':'field'}]:
            with self.subTest(patch=patch):
                response=self.client.post('/api/routes',json={**self.body,**patch})
                self.assertEqual(response.status_code,422)
                self.assertEqual(response.json()['code'],'invalid_request')
        response=self.client.post('/api/routes',content='{"start_lonlat":[NaN,18]}',headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,422)

    def test_rejects_untrusted_browser_origin(self):
        response=self.client.post('/api/routes',json=self.body,headers={'Origin':'https://untrusted.example'})
        self.assertEqual(response.status_code,403)

    def test_local_proxy_origin_works(self):
        response=self.client.post('/api/routes',json={**self.body,'end_lonlat':self.body['start_lonlat']},headers={'Origin':'http://127.0.0.1:4173'})
        self.assertEqual(response.status_code,200)

    def test_bounds_body_and_content_type(self):
        response=self.client.post('/api/routes',content='x'*5000,headers={'Content-Type':'application/json'})
        self.assertEqual(response.status_code,413)
        response=self.client.post('/api/routes',content='{}',headers={'Content-Type':'text/plain'})
        self.assertEqual(response.status_code,415)

    def test_single_computation_limit_reports_busy(self):
        lock=self.app.state.route_lock
        lock.acquire()
        try:
            response=self.client.post('/api/routes',json=self.body)
            self.assertEqual(response.status_code,429)
            self.assertEqual(response.headers['Retry-After'],'1')
        finally:
            lock.release()

    def test_data_unavailable_and_recovery_keep_terrain_files(self):
        grid=self.app.state.grid
        self.app.state.grid=None
        try:
            self.assertEqual(self.client.get('/api/region').status_code,503)
            self.assertEqual(self.client.post('/api/routes',json=self.body).status_code,503)
            self.assertEqual(self.client.get('/data/manifest.json').status_code,200)
        finally:
            self.app.state.grid=grid
        self.assertEqual(self.client.get('/api/health').status_code,200)

    def test_host_and_response_guards(self):
        self.assertEqual(self.client.get('/api/region',headers={'Host':'attacker.example'}).status_code,400)
        self.assertEqual(self.client.get('/api/region').headers['X-Content-Type-Options'],'nosniff')


if __name__=='__main__':
    unittest.main()
