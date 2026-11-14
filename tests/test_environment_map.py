"""Independent checks of real THEMIS native pixels and map geometry."""
import json
import unittest
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from pyproj import CRS, Transformer
from backend.environment import digest

ROOT=Path(__file__).resolve().parents[1]


class ThermalMapTests(unittest.TestCase):
    def setUp(self):
        self.directory=ROOT/'data/processed/environment-map'
        self.meta=json.loads((self.directory/'manifest.json').read_text())

    def test_native_values_match_original_source_without_resampling(self):
        m=self.meta
        output=np.fromfile(self.directory/'thermal.f32',dtype='<f4').reshape(m['height'],m['width'])
        with rasterio.open(ROOT/'data/raw/environment-map/Jezero_Thermal_Inertia_v1.tiff') as ds:
            for row in range(m['height']):
                for col in range(m['width']):
                    x=m['affine'][2]+(col+.5)*100;y=m['affine'][5]-(row+.5)*100
                    sr,sc=ds.index(x,y)
                    actual=ds.read(1,window=rasterio.windows.Window(sc,sr,1,1))[0,0]
                    self.assertEqual(output[row,col],actual)
        self.assertEqual(output.shape,(51,54))
        self.assertEqual(m['valid_pixels'],2754)

    def test_projection_control_points_match_independent_proj(self):
        m=self.meta
        region=json.loads((ROOT/'data/processed/jezero-m1/manifest.json').read_text())
        transform=Transformer.from_crs(CRS.from_wkt(m['source_crs_wkt']),CRS.from_wkt(region['crs']['wkt']),always_xy=True)
        w,s,e,n=m['bounds_map_m']
        for point in m['controls']:
            expected=transform.transform(*point['source_xy_m'])
            self.assertAlmostEqual(w+(point['col']+.5)*(e-w)/m['width'],expected[0],places=7)
            self.assertAlmostEqual(n-(point['row']+.5)*(n-s)/m['height'],expected[1],places=7)

    def test_numeric_masks_colours_and_public_hashes_agree(self):
        m=self.meta
        values=np.fromfile(self.directory/'thermal.f32',dtype='<f4')
        mask=np.fromfile(self.directory/'valid.u8',dtype='uint8')
        pixels=np.asarray(Image.open(self.directory/'thermal.png')).reshape(-1,4)
        for i in range(len(values)):
            self.assertEqual(bool(mask[i]),bool(pixels[i,3]))
            if mask[i]:
                band=int(np.searchsorted(m['legend']['breaks'],values[i],side='right'))
                self.assertEqual(list(pixels[i,:3]),m['legend']['colors'][band])
        for name,record in m['outputs'].items():
            self.assertEqual(digest(self.directory/name),record['sha256'])
            self.assertEqual(digest(ROOT/'frontend/public/data/environment-map'/name),record['sha256'])

    def test_quantity_source_and_limits_are_explicit(self):
        m=self.meta
        self.assertEqual(m['quantity'],'thermal_inertia')
        self.assertEqual(m['source_pixel_size_m'],100)
        self.assertIn('not temperature',m['kind'])
        self.assertIn('not air/surface temperature',m['limits'])
        self.assertEqual(m['license'],'CC BY 4.0')
        self.assertEqual(m['terrain_manifest_sha256'],digest(ROOT/'data/processed/jezero-m1/manifest.json'))
