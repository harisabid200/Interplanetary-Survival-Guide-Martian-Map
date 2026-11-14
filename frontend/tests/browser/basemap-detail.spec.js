import {test,expect} from '@playwright/test';
import {readFileSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const manifest=JSON.parse(readFileSync(new URL('../../public/data/imagery-detail-manifest.json',import.meta.url)));
const output=new URL('../../../evidence/map-upgrade/',import.meta.url);
mkdirSync(output,{recursive:true});

test('actual NASA Mars Trek zoom-13 CTX basemap is integrity-bound and aligned with M1 controls',async({page})=>{
  expect(manifest.status).toBe('source-derived');
  expect(manifest.matrix_id).toBe('13');
  expect(manifest.tile_count).toBe(64);
  expect(manifest.mosaic_size_px).toEqual([2048,2048]);
  expect(manifest.source_mars_equatorial_pixel_m).toBeCloseTo(5.0876,3);
  expect(manifest.terrain_control_point_coverage).toHaveLength(5);
  expect(manifest.terrain_control_point_coverage.every(point=>point.alpha===255)).toBe(true);
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const local=[];page.on('request',request=>{if(request.url().startsWith('http://127.0.0.1:4173'))local.push(request.url());});
  await page.setViewportSize({width:1600,height:1000});
  const detailed=page.waitForResponse(response=>response.url().endsWith('/data/imagery-detail.png'));
  await page.goto('/');
  expect((await detailed).status()).toBe(200);
  await expect(page.getByText('Z13 · ~5 M TILE',{exact:false})).toBeVisible();
  await expect(page.getByRole('checkbox',{name:'Terrain slope'})).not.toBeChecked();
  await expect(page.locator('.mars-scale-line')).toBeVisible();
  await expect(page.getByText('NASA / USGS CTX ORBITAL IMAGERY',{exact:true})).toBeVisible();
  await expect(page.getByText(/5.*km native DEM/)).toBeVisible();
  await page.getByRole('button',{name:'Fit terrain',exact:false}).click();
  await expect(page.getByRole('button',{name:'Wider view',exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Wider view',exact:false}).click();
  await expect(page.getByRole('button',{name:'Fit terrain',exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
  await page.screenshot({path:fileURLToPath(new URL('map-upgrade-desktop.png',output))});
  expect(errors).toEqual([]);
  expect(local.some(url=>url.endsWith('/data/imagery-detail.png'))).toBe(true);
});
