"""M4 scientific checks. Synthetic cases here are never demo measurements."""
import csv
import json
import math
import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from fastapi.testclient import TestClient
from backend.api import create_app
from backend.environment import digest, read_product, summarize, lmst_seconds, number, load_environment
from scripts.preprocess_environment import build, ROOT, RAW


class SyntheticEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.field=dict(name='SYNTHETIC',unit='kelvin',description='Explicit synthetic fixture',special_constants=['-9999'])
        self.meta=dict(sol=15,fields=[self.field])
        self.rows=[dict(LMST='00015M00:00:00.000',SCLK='100',SYNTHETIC='200',FLAG='1'),
                   dict(LMST='00015M00:00:01.000',SCLK='101',SYNTHETIC='220',FLAG='0'),
                   dict(LMST='00015M00:20:00.000',SCLK='1300',SYNTHETIC='240',FLAG='1')]

    def test_gaps_are_null_not_interpolated(self):
        s=summarize(self.meta,self.rows,'SYNTHETIC','kelvin')
        self.assertEqual(len(s['bins']),288)
        self.assertEqual(s['bins'][0]['mean'],210)
        self.assertIsNone(s['bins'][1]['mean'])
        self.assertEqual(s['bins'][1]['count'],0)
        self.assertEqual(s['max_accepted_gap_sclk_seconds'],1199)

    def test_explicit_quality_rule_excludes_flag_zero(self):
        s=summarize(self.meta,self.rows,'SYNTHETIC','kelvin',quality_field='FLAG')
        self.assertEqual((s['accepted'],s['rejected']),(2,1))
        self.assertEqual(s['bins'][0]['mean'],200)

    def test_empty_nonfinite_special_constants_rejected(self):
        for value in ['', 'NaN', 'Inf', '-9999', 'not_a_number']:
            self.assertIsNone(number(value,self.field))
        self.assertEqual(number('0',self.field),0) # Do not invent a nodata convention.

    def test_incorrect_unit_fails(self):
        with self.assertRaisesRegex(ValueError,'Unexpected unit'):
            summarize(self.meta,self.rows,'SYNTHETIC','pascal')

    def test_invalid_sol_clock_and_nonmonotonic_samples_fail(self):
        for value in ['00016M00:00:00','00015M24:00:00','00015M00:60:00','bad']:
            with self.assertRaises(ValueError):
                lmst_seconds(value,15)
        with self.assertRaisesRegex(ValueError,'increasing'):
            summarize(self.meta,list(reversed(self.rows)),'SYNTHETIC','kelvin')


class RealEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=build()

    def test_actual_ats_matches_independent_csv_reduction(self):
        path=next((RAW/'sol-0015').glob('*CAL_ATS*.CSV'))
        with path.open(newline='') as stream:
            rows=list(csv.DictReader(stream))
        for series in self.data['meda']['temperature']:
            values=[float(r[series['field']]) for r in rows]
            self.assertEqual(len(values),54121)
            self.assertEqual(series['minimum'],min(values))
            self.assertEqual(series['maximum'],max(values))
            self.assertAlmostEqual(series['sample_mean'],math.fsum(values)/len(values),places=12)
            groups=defaultdict(list)
            for r in rows:
                groups[int(r['LMST'][6:8])*12+int(r['LMST'][9:11])//5].append(float(r[series['field']]))
            for i,bin in enumerate(series['bins']):
                chosen=groups[i]
                self.assertEqual(bin['count'],len(chosen))
                self.assertEqual(bin['mean'],math.fsum(chosen)/len(chosen) if chosen else None)
            self.assertIn('No per-row quality flag',series['quality'])

    def test_actual_pressure_units_and_archive_anomaly_are_explicit(self):
        s=self.data['meda']['pressure']
        self.assertEqual((s['accepted'],s['unit'],s['minimum'],s['maximum']),(26818,'pascal',721.69,741.33))
        f=self.data['meda']['pressure_product']['fields'][4]
        self.assertEqual((f['name'],f['label_name'],f['unit']),('PRESSURE_UNCERTAINTY','PRESSURE UNCERTAINTY','kelvin'))
        self.assertNotIn('uncertainty',s)

    def test_real_label_checksum_and_table_reject_tampering(self):
        source=next((RAW/'sol-0015').glob('*CAL_ATS*.xml'))
        with tempfile.TemporaryDirectory() as tmp:
            label=Path(tmp)/source.name
            label.write_bytes(source.read_bytes())
            raw=Path(tmp)/self.data['meda']['temperature_product']['filename']
            original=source.with_suffix('.CSV').read_bytes()
            raw.write_bytes(b'X'+original[1:])
            with self.assertRaisesRegex(ValueError,'MD5'):
                read_product(label)
            raw.write_bytes(original[:-1])
            with self.assertRaisesRegex(ValueError,'size'):
                read_product(label)

    def test_native_position_frame_and_reference_semantics(self):
        d=self.data
        self.assertEqual(d['spatial_overlays'],[])
        self.assertIn('M2020_TOPO',d['meda']['location']['description'])
        self.assertEqual(d['meda']['location']['axes'][0]['maximum'],30.07)
        self.assertIn('2022',d['dust']['date_label'])
        self.assertIn('not contemporaneous',d['dust']['limit'])
        self.assertIn('Gale radiation is not measured Jezero radiation',d['radiation']['limit'])
        self.assertNotIn('dose',d['radiation'])

    def test_runtime_is_reproducible_and_source_bound(self):
        path=ROOT/'data/processed/environment/environment.json'
        self.assertEqual(json.loads(path.read_text()),self.data)
        loaded=load_environment(path.parent)
        self.assertEqual(loaded['artifact_sha256'],digest(path))

    def test_environment_api_real_data_and_security_headers(self):
        with TestClient(create_app()) as client:
            r=client.get('/api/environment')
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json()['meda']['temperature'][0]['minimum'],190.58)
            self.assertEqual(r.headers['x-content-type-options'],'nosniff')
            self.assertEqual(client.get('/api/environment',headers={'Host':'untrusted.example'}).status_code,400)

    def test_missing_or_corrupt_environment_does_not_disable_routing(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            for corrupted in [False,True]:
                if corrupted:
                    (directory/'manifest.json').write_text(json.dumps(dict(path='environment.json',bytes=2,sha256='0'*64)))
                    (directory/'environment.json').write_text('{}')
                with TestClient(create_app(environment_dir=directory)) as client:
                    self.assertEqual(client.get('/api/environment').status_code,503)
                    self.assertEqual(client.get('/api/health').status_code,200)
                    self.assertTrue(client.get('/api/region').json()['routing_available'])


if __name__=='__main__':
    unittest.main()
