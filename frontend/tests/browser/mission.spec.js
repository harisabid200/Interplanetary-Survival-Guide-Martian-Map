import {test,expect} from '@playwright/test';
import {readFileSync,writeFileSync} from 'node:fs';
import {projectionFunctions,cellCenter} from '../../src/coordinates.js';
const evidenceStage=process.env.MARSWALK_EVIDENCE_STAGE||'m4';
const region=JSON.parse(readFileSync(new URL('../../public/data/manifest.json',import.meta.url)));

async function ready(page) {
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Compare routes →',exact:true})).toBeEnabled();
}
async function fillEndpoints(page,start,end) {
  for (const [name,value] of [['Starting location longitude',start[0]],['Starting location latitude',start[1]],['Destination longitude',end[0]],['Destination latitude',end[1]]]) await page.getByRole('spinbutton',{name,exact:true}).fill(String(value));
}

test('actual browser → API → M2 comparison, profiles, route controls and source panels',async({page})=>{
  await page.setViewportSize({width:1600,height:1000});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await ready(page);
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  await page.getByLabel('Exploration objective').selectOption('terrain');
  const responsePromise=page.waitForResponse(response=>response.url().endsWith('/api/routes')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  const response=await responsePromise;
  expect(response.status()).toBe(200);
  const result=await response.json();
  expect(result.status).toBe('ok');expect(result.primary_objective).toBe('terrain');
  expect(result.routes[0].geometry.coordinates.length).toBe(125);
  writeFileSync(new URL(`../../../evidence/${evidenceStage}/http-route-response.json`,import.meta.url),JSON.stringify(result,null,2)+'\n');
  await expect(page.getByTestId('distance-distance')).toHaveText('3,507.3 m');
  await expect(page.getByTestId('terrain-distance')).toHaveText('3,964.3 m');
  await expect(page.getByTestId('distance-slope')).toHaveText('13.30°');
  await expect(page.getByTestId('terrain-slope')).toHaveText('8.69°');
  await expect(page.getByRole('img',{name:'Actual route elevation profiles in metres versus horizontal Mars distance'})).toBeVisible();
  await expect(page.getByTestId('map-route-status')).toContainText('2 calculated route layers');
  await page.getByRole('checkbox',{name:'distance route layer',exact:true}).uncheck();
  await expect(page.getByTestId('map-route-status')).toContainText('1 calculated route layers');
  await page.getByRole('checkbox',{name:'distance route layer',exact:true}).check();
  await page.getByRole('button',{name:'Focus distance route',exact:true}).click();
  await expect(page.getByRole('button',{name:'Focus distance route',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.getByRole('checkbox',{name:'Elevation tint',exact:true}).check();
  await expect(page.getByText(/Elevation tint: purple/)).toBeVisible();
  await page.getByRole('checkbox',{name:'Elevation tint',exact:true}).uncheck();
  await page.getByRole('checkbox',{name:'Radiation reference context',exact:true}).check();
  await page.getByRole('checkbox',{name:'Ancient-water evidence context',exact:true}).check();
  await expect(page.getByRole('heading',{name:'Radiation reference',exact:true})).toBeVisible();
  await expect(page.getByText(/Gale radiation is not measured Jezero radiation/)).toBeVisible();
  await expect(page.getByText(/Ancient water evidence is not accessible drinking water/)).toBeVisible();
  // Return sidebar and right panel to their start for a reviewable mission view.
  await page.evaluate(()=>{document.querySelector('.sidebar').scrollTop=0;document.querySelector('.mission-insights').scrollTop=0;});
  await page.screenshot({path:`../evidence/${evidenceStage}/mission-control-desktop.png`});
  expect(errors).toEqual([]);
});

test('map picks populate real endpoints and changing inputs clears stale geometry',async({page})=>{
  await page.setViewportSize({width:1500,height:1000});
  await ready(page);
  await page.getByRole('button',{name:'Pick start on map',exact:false}).click();
  const box=await page.locator('#terrain-map').boundingBox();
  await page.mouse.click(box.x+box.width*.5,box.y+box.height*.45);
  await expect(page.getByRole('spinbutton',{name:'Starting location longitude',exact:true})).not.toHaveValue('');
  await page.getByRole('button',{name:'Pick destination on map',exact:false}).click();
  await page.mouse.click(box.x+box.width*.6,box.y+box.height*.4);
  await expect(page.getByRole('spinbutton',{name:'Destination longitude',exact:true})).not.toHaveValue('');
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByTestId('distance-distance')).toBeVisible();
  await page.getByRole('spinbutton',{name:'Destination longitude',exact:true}).fill('77');
  await expect(page.getByTestId('map-route-status')).toHaveCount(0);
  await expect(page.getByTestId('distance-distance')).toHaveCount(0);
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('outside valid');
});

test('actual same-cell request has zero travel and coincident objective paths',async({page})=>{
  await ready(page);
  const point=region.control_points[0].lonlat;
  await fillEndpoints(page,point,point);
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByTestId('distance-distance')).toHaveText('0.0 m');
  await expect(page.getByText(/Start and destination share one cell/)).toBeVisible();
});

test('actual disconnected low-gradient cells return no path without a drawn route',async({page})=>{
  await ready(page);
  const bytes=readFileSync(new URL('../../public/data/slope.f32',import.meta.url));
  const indices=[];
  for(let i=0;i<region.width*region.height;i++) {const slope=bytes.readFloatLE(i*4);if(Number.isFinite(slope)&&slope<=.1)indices.push(i);}
  const inverse=projectionFunctions(region.crs).inverse;
  const ll=index=>inverse(cellCenter(Math.floor(index/region.width),index%region.width,region));
  await fillEndpoints(page,ll(indices[0]),ll(indices.at(-1)));
  await page.getByText('Terrain assumptions',{exact:true}).click();
  await page.getByLabel('Cell-slope limit',{exact:true}).fill('0.1');
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByRole('heading',{name:'No connected route',exact:true})).toBeVisible();
  await expect(page.getByTestId('map-route-status')).toHaveCount(0);
  await expect(page.getByTestId('distance-distance')).toHaveCount(0);
});

test('API unavailable preserves terrain inspector and can reconnect',async({page})=>{
  await page.route('**/api/region',route=>route.fulfill({status:503,contentType:'application/json',body:'{"code":"test_api_unavailable"}'}));
  await page.goto('/');
  await expect(page.getByRole('button',{name:'Reconnect routing',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:'Compare routes →',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
  await page.unroute('**/api/region');
  await page.getByRole('button',{name:'Reconnect routing',exact:true}).click();
  await expect(page.getByRole('button',{name:'Compare routes →',exact:true})).toBeEnabled();
});

test('dataset mismatch response shows error and no invented route',async({page})=>{
  await ready(page);
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  await page.route('**/api/routes',route=>route.fulfill({status:409,contentType:'application/json',body:'{"code":"dataset_mismatch","message":"Map and routing datasets differ. Reload verified data."}'}));
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('datasets differ');
  await expect(page.getByTestId('map-route-status')).toHaveCount(0);
});

test('mobile actual comparison and independent source contexts fit viewport',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await ready(page);
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await expect(page.getByTestId('terrain-distance')).toHaveText('3,964.3 m');
  await page.getByRole('checkbox',{name:'Geological features context',exact:true}).check();
  await expect(page.getByRole('heading',{name:'Geological features',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({path:`../evidence/${evidenceStage}/mission-control-mobile.png`,fullPage:true});
});

test('editing endpoints during an actual in-flight request never restores stale geometry',async({page})=>{
  await ready(page);
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  let release,notifyFetched,notifySettled;
  const gate=new Promise(resolve=>{release=resolve;});
  const fetched=new Promise(resolve=>{notifyFetched=resolve;});
  const settled=new Promise(resolve=>{notifySettled=resolve;});
  await page.route('**/api/routes',async route=>{
    const response=await route.fetch();
    expect(response.status()).toBe(200);
    notifyFetched();
    await gate;
    try {await route.fulfill({response});} catch { /* The edited request is intentionally aborted. */ }
    notifySettled();
  });
  await page.getByRole('button',{name:'Compare routes →',exact:true}).click();
  await fetched;
  await page.getByRole('spinbutton',{name:'Destination longitude',exact:true}).fill('77.43');
  release(); await settled;
  await expect(page.getByTestId('map-route-status')).toHaveCount(0);
  await expect(page.getByTestId('distance-distance')).toHaveCount(0);
});

test('tampered numeric grid fails closed against manifest checksum',async({page})=>{
  const bytes=readFileSync(new URL('../../public/data/elevation.f32',import.meta.url));
  const changed=Buffer.from(bytes);changed[0]^=1;
  await page.route('**/data/elevation.f32',route=>route.fulfill({status:200,body:changed,contentType:'application/octet-stream'}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Terrain unavailable',exact:true})).toBeVisible();
  await expect(page.getByTestId('distance-distance')).toHaveCount(0);
});
