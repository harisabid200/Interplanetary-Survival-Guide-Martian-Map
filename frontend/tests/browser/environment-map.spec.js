import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {sampleThermal} from '../../src/environmentMap.js';
const meta=JSON.parse(readFileSync(new URL('../../public/data/environment-map/manifest.json',import.meta.url)));
const bytes=readFileSync(new URL('../../public/data/environment-map/thermal.f32',import.meta.url));
const thermal={meta,values:Float32Array.from({length:meta.width*meta.height},(_,i)=>bytes.readFloatLE(i*4)),valid:readFileSync(new URL('../../public/data/environment-map/valid.u8',import.meta.url))};
const region=JSON.parse(readFileSync(new URL('../../public/data/manifest.json',import.meta.url)));

test('real thermal colour overlay, native point value, opacity and unchanged route comparison',async({page})=>{
  await page.setViewportSize({width:1600,height:1000});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  const checkbox=page.getByLabel('Surface thermal response map',{exact:true});
  await expect(checkbox).toBeEnabled();
  const before=await page.locator('#terrain-map').screenshot();
  await checkbox.check();
  await expect(page.getByLabel('Terrain slope',{exact:true})).not.toBeChecked();
  await expect(page.getByText('THERMAL INERTIA · NOT TEMPERATURE',{exact:true})).toBeVisible();
  await page.getByLabel('Show verification samples',{exact:true}).check();
  await page.getByRole('button',{name:'Inspect verification sample 1',exact:true}).click();
  const expected=sampleThermal(region.control_points[0].lonlat,thermal);
  await expect(page.getByTestId('thermal-value')).toHaveText(expected.value.toFixed(2));
  await expect(page.getByText('Resistance to heating/cooling; not temperature.',{exact:false})).toBeVisible();
  await page.getByLabel('Overlay opacity',{exact:true}).fill('80');
  await expect(page.getByLabel('Overlay opacity',{exact:true})).toHaveValue('80');
  const after=await page.locator('#terrain-map').screenshot();
  expect(after.equals(before)).toBe(false);
  await page.getByText('What these colours mean',{exact:true}).click();
  await expect(page.getByText(/individual acquisition dates are not supplied/)).toBeVisible();
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByTestId('distance-distance')).toHaveText('3,507.3 m');
  await expect(page.getByTestId('terrain-distance')).toHaveText('3,964.3 m');
  await checkbox.scrollIntoViewIfNeeded();
  await page.screenshot({path:'../evidence/environment-map/thermal-desktop.png'});
  await page.getByLabel('Terrain slope',{exact:true}).check();
  await expect(checkbox).not.toBeChecked();
  await expect(page.getByTestId('thermal-value')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('missing thermal dataset disables only its overlay',async({page})=>{
  await page.route('**/data/environment-map/manifest.json',route=>route.fulfill({status:404,body:'missing'}));
  await page.goto('/');
  await expect(page.getByLabel('Surface thermal response map',{exact:true})).toBeDisabled();
  await expect(page.getByText(/Thermal map unavailable. Run scripts/)).toBeVisible();
  await expect(page.getByRole('button',{name:'Compare routes →',exact:true})).toBeEnabled();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
});

test('corrupt thermal pixels fail closed without fabricated colours or values',async({page})=>{
  await page.route('**/data/environment-map/thermal.f32',route=>route.fulfill({body:Buffer.alloc(bytes.length),contentType:'application/octet-stream'}));
  await page.goto('/');
  await expect(page.getByText('Thermal map checksum mismatch; overlay disabled.',{exact:true})).toBeVisible();
  await expect(page.getByLabel('Surface thermal response map',{exact:true})).toBeDisabled();
  await expect(page.getByTestId('thermal-value')).toHaveCount(0);
});

test('mobile thermal overlay and native readout fit the viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await page.getByLabel('Surface thermal response map',{exact:true}).check();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('thermal-value')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({path:'../evidence/environment-map/thermal-mobile.png',fullPage:true});
});
