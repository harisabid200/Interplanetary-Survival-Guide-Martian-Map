import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
const evidenceStage=process.env.MARSWALK_EVIDENCE_STAGE||'m4';
const region = JSON.parse(readFileSync(new URL('../../public/data/manifest.json', import.meta.url)));

test('real map renders, five reference cells match, layers work, outside coverage rejected', async ({page}) => {
  await page.setViewportSize({width:1440,height:1000});
  const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  const external=[];
  page.on('request', r => {if (!r.url().startsWith('http://127.0.0.1:4173') && !r.url().startsWith('data:')) external.push(r.url());});
  await page.goto('/');
  await expect(page.getByText('LOCAL DATA READY')).toBeVisible();
  await expect(page.locator('#terrain-map canvas')).toBeVisible();
  await page.getByRole('checkbox',{name:'Show verification samples'}).check();
  for(let i=0;i<region.control_points.length;i++) {
    const p=region.control_points[i];
    await page.getByRole('button',{name:`Inspect verification sample ${i+1}`,exact:true}).click();
    await expect(page.getByTestId('elevation')).toHaveText(`${p.elevation_m.toFixed(2)} m`);
    await expect(page.getByTestId('slope')).toHaveText(`${p.slope_deg.toFixed(2)}°`);
    await expect(page.getByTestId('row')).toHaveText(String(p.row));
    await expect(page.getByTestId('col')).toHaveText(String(p.col));
  }
  await page.getByRole('button',{name:'Inspect verification sample 1',exact:true}).click();
  await page.getByRole('checkbox',{name:'Terrain slope',exact:true}).uncheck();
  await expect(page.getByText('SLOPE OVERLAY HIDDEN')).toBeVisible();
  await expect(page.getByRole('slider',{name:'Overlay opacity'})).toBeDisabled();
  await page.screenshot({path:`../evidence/${evidenceStage}/regression-desktop-imagery.png`});
  await page.getByRole('checkbox',{name:'Terrain slope',exact:true}).check();
  await page.getByRole('slider',{name:'Overlay opacity'}).fill('75');
  await expect(page.getByText('75%',{exact:true})).toBeVisible();
  await page.getByRole('slider',{name:'Overlay opacity'}).fill('55');
  await page.getByRole('checkbox',{name:'CTX imagery',exact:true}).uncheck();
  await page.getByRole('checkbox',{name:'CTX imagery',exact:true}).check();
  const box=await page.locator('#terrain-map').boundingBox();
  // Uncovered far-left margin lies outside square pilot at this viewport.
  await page.mouse.click(box.x+10,box.y+box.height/2);
  await expect(page.getByText('No terrain coverage',{exact:true})).toBeVisible();
  // Awaiting the outside-state also lets OL's deferred singleclick complete.
  await page.mouse.click(box.x+box.width/2,box.y+box.height/2);
  await expect(page.getByTestId('elevation')).toBeVisible();
  await page.getByRole('button',{name:'Fit pilot',exact:false}).click();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
  await page.getByRole('button',{name:'Inspect verification sample 1',exact:true}).click();
  await page.locator('#terrain-map').focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('#terrain-map')).toBeFocused();
  await page.getByRole('button',{name:'Fit pilot',exact:false}).click();
  await page.screenshot({path:`../evidence/${evidenceStage}/regression-desktop-slope.png`});
  await page.getByText('Sources & processing').click();
  await expect(page.getByRole('link',{name:'Full manifest, checksums & method'})).toBeVisible();
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test('mobile map, numeric inspection and layout fit viewport', async ({page}) => {
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.locator('#terrain-map canvas')).toBeVisible();
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.screenshot({path:`../evidence/${evidenceStage}/regression-mobile.png`,fullPage:true});
});

test('missing manifest fails visibly and never shows invented values', async ({page}) => {
  await page.route('**/data/manifest.json', route => route.fulfill({status:404,body:'Missing'}));
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Terrain unavailable'})).toBeVisible();
  await expect(page.getByTestId('elevation')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Reload data'})).toBeVisible();
});

test('missing imagery has a visible error with numeric data retained', async ({page}) => {
  await page.route('**/data/imagery.png', route => route.fulfill({status:404,body:'Missing'}));
  await page.goto('/');
  await expect(page.getByRole('alert')).toContainText('Imagery unavailable');
  await page.getByRole('button',{name:'Sample map center',exact:false}).click();
  await expect(page.getByTestId('elevation')).toBeVisible();
});
