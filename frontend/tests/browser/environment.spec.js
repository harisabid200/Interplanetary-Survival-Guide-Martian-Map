import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const evidenceStage=process.env.MARSWALK_EVIDENCE_STAGE||'m4';
const source=JSON.parse(readFileSync(new URL('../../../data/processed/environment/environment.json',import.meta.url)));

test('actual MEDA series, detector selection, pressure, provenance and independent contexts',async({page})=>{
  await page.setViewportSize({width:1600,height:1000});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button',{name:/Compare routes/})).toBeEnabled();
  const request=page.waitForResponse(response=>response.url().endsWith('/api/environment'));
  await page.getByLabel('Temperature & weather context',{exact:true}).check();
  expect((await request).status()).toBe(200);
  const card=page.locator('.context-card').filter({has:page.getByRole('heading',{name:'Temperature & weather',exact:true})});
  await expect(card).toContainText('190.58–252.15');
  await expect(card).toContainText('721.69–741.33');
  await expect(card).toContainText('54,121 accepted');
  await expect(card).toContainText('26654.5 spacecraft-clock seconds');
  const plot=card.getByRole('img',{name:/ATS_LOCAL_TEMP1/});
  expect(await plot.locator('circle').count()).toBe(source.meda.temperature[0].bins.filter(bin=>bin.count>0).length);
  await card.getByLabel('Air-temperature detector').selectOption('ATS_LOCAL_TEMP2');
  await expect(card).toContainText('192.84–260.60');
  await expect(card.getByRole('img',{name:/ATS_LOCAL_TEMP2/})).toBeVisible();
  await card.getByText('Location, sampling & provenance',{exact:true}).click();
  await expect(card).toContainText('M2020_TOPO');
  await expect(card).toContainText('not longitude/latitude');
  await expect(card).toContainText('Pressure uncertainty label lists kelvin');
  await expect(card).toContainText(source.meda.temperature_product.data_sha256);
  await page.getByLabel('Atmospheric dust & storms context',{exact:true}).check();
  await expect(page.getByText('Observed 17–23 January 2022',{exact:false})).toBeVisible();
  await page.getByLabel('Radiation reference context',{exact:true}).check();
  await expect(page.getByText('GALE REFERENCE ONLY · NOT JEZERO',{exact:true})).toBeVisible();
  await expect(page.getByText(/Numeric dose unavailable/)).toBeVisible();
  await page.getByLabel('Temperature & weather context',{exact:true}).uncheck();
  await expect(page.getByRole('heading',{name:'Temperature & weather',exact:true})).toHaveCount(0);
  await expect(page.getByRole('heading',{name:'Radiation reference',exact:true})).toBeVisible();
  await page.getByLabel('Temperature & weather context',{exact:true}).check();
  await expect(page.getByLabel('Air-temperature detector')).toBeVisible();
  await card.evaluate(node=>{const panel=node.closest('.mission-insights');panel.scrollTop=node.offsetTop-panel.offsetTop;});
  await page.screenshot({path:`../evidence/${evidenceStage}/environment-desktop.png`});
  expect(errors).toEqual([]);
});

test('environment failure and retry preserve actual route planning',async({page})=>{
  await page.route('**/api/environment',route=>route.fulfill({status:503,contentType:'application/json',body:'{"message":"Verified environmental archive unavailable."}'}));
  await page.goto('/');
  await page.getByLabel('Temperature & weather context',{exact:true}).check();
  await expect(page.getByRole('button',{name:'Retry environmental data'})).toBeVisible();
  await expect(page.getByLabel('Air-temperature detector')).toHaveCount(0);
  await page.getByRole('button',{name:'Load verification pair',exact:true}).click();
  await page.getByRole('button',{name:/Compare routes/}).click();
  await expect(page.getByTestId('distance-distance')).toHaveText('3,507.3 m');
  await page.unroute('**/api/environment');
  await page.getByRole('button',{name:'Retry environmental data'}).click();
  await expect(page.getByLabel('Air-temperature detector')).toBeVisible();
});

test('mobile historical panel fits viewport and labels scope',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await page.getByLabel('Temperature & weather context',{exact:true}).check();
  await expect(page.getByLabel('Air-temperature detector')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(390);
  await expect(page.getByText(/Spatial layer unavailable.*historical context only/)).toBeVisible();
  await page.screenshot({path:`../evidence/${evidenceStage}/environment-mobile.png`,fullPage:true});
});
