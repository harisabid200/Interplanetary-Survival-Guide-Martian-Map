"""Real M1 input-integrity and CLI boundary checks. Requires preprocessing."""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

from backend import cli
from backend.routing import DEFAULT_REGION, RoutingError, TerrainGrid


class RealInputBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((DEFAULT_REGION/'manifest.json').read_text())
        cls.point=cls.manifest['control_points'][0]['lonlat']

    def copy_region(self,path):
        for name in ['manifest.json','dem.tif','slope.tif','valid-mask.tif','slope-mask.tif']:
            shutil.copyfile(DEFAULT_REGION/name,path/name)

    def test_tampered_real_product_is_rejected_before_routing(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp); self.copy_region(directory)
            with (directory/'dem.tif').open('r+b') as stream:
                stream.seek(-1,2); old=stream.read(1); stream.seek(-1,2); stream.write(bytes([old[0]^1]))
            with self.assertRaises(RoutingError) as error:
                TerrainGrid.load(directory)
            self.assertEqual(error.exception.code,'checksum_mismatch')

    def test_mismatched_manifest_geometry_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp); self.copy_region(directory)
            changed=dict(self.manifest); changed['width']+=1
            (directory/'manifest.json').write_text(json.dumps(changed),encoding='utf-8')
            with self.assertRaises(RoutingError) as error:
                TerrainGrid.load(directory)
            self.assertEqual(error.exception.code,'invalid_grid')

    def call_cli(self,extra=None):
        args=['backend.cli','--start',*map(str,self.point),'--end',*map(str,self.point),*(extra or [])]
        stdout=io.StringIO(); stderr=io.StringIO()
        # unittest enables third-party deprecations normally hidden by Python.
        # Filter only this known NumPy masked-array compatibility warning when
        # asserting the CLI JSON channel; do not suppress data/GDAL warnings.
        with patch('sys.argv',args),contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr),warnings.catch_warnings():
            warnings.filterwarnings('ignore',category=DeprecationWarning,
                                    message='Setting the shape on a NumPy array has been deprecated in NumPy 2.5.')
            code=cli.main()
        return code,stdout.getvalue(),stderr.getvalue()

    def test_real_cli_serializes_finite_single_cell_geometry(self):
        code,out,err=self.call_cli()
        self.assertEqual(code,0); self.assertEqual(err,'')
        result=json.loads(out)
        self.assertEqual(result['status'],'ok')
        self.assertEqual(result['routes'][0]['geometry']['type'],'Point')
        self.assertEqual(result['routes'][0]['metrics']['distance_m'],0)

    def test_cli_invalid_parameter_returns_structured_error(self):
        code,out,err=self.call_cli(['--terrain-weight','nan'])
        self.assertEqual(code,2); self.assertEqual(out,'')
        self.assertTrue(err.startswith('{'),repr(err))
        self.assertEqual(json.loads(err)['status'],'invalid_request')

    def test_cli_never_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'existing.json'; dest.write_text('preserve me',encoding='utf-8')
            code,out,err=self.call_cli(['--output',str(dest)])
            self.assertEqual(code,2); self.assertEqual(out,'')
            self.assertEqual(json.loads(err)['status'],'output_error')
            self.assertEqual(dest.read_text(),'preserve me')


if __name__=='__main__':
    unittest.main()
