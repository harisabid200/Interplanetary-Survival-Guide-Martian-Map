import {test,expect} from '@playwright/test';
import {mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';

const output=new URL('../../../evidence/m6/',import.meta.url);
mkdirSync(output,{recursive:true});

test('user assumptions produce separate round-trip budgets and an explainable terrain candidate list',async({page})=>{
  await page.setViewportSize({width:1600,height:1000});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/');
  await expect(page.getByRole('button',{name:/Compare routes/})).toBeEnabled();
  await page.getByRole('button',{name:'Load verification pair'}).click();
  await expect(page.getByRole('spinbutton',{name:'Starting location longitude'})).not.toHaveValue('');
  await page.getByLabel('Candidate maximum buffered slope').fill('90');
  await page.getByLabel('Candidate maximum distance km').fill('5');
  await page.getByRole('button',{name:'Filter mapped stops'}).click();
  const candidates=page.locator('.candidate-results li');
  await expect(page.getByText(/not a continuous path\/access check, hazard assessment/)).toBeVisible();
  if(await candidates.count()) {
    await candidates.first().getByRole('button',{name:'Use as destination B'}).click();
    await expect(page.getByRole('spinbutton',{name:'Destination longitude'})).not.toHaveValue('');
  } else {
    await expect(page.getByText('No mapped points meet these inputs and complete terrain-coverage requirements.')).toBeVisible();
  }
  await page.getByRole('button',{name:/Compare routes/}).click();
  await expect(page.getByTestId('distance-distance')).toBeVisible({timeout:30000});
  await page.getByLabel('Assumed walking speed km per hour').fill('4');
  await page.getByLabel('Available mission time minutes').fill('180');
  await page.getByLabel('Science stop duration minutes').fill('20');
  await page.getByLabel('Reserve time minutes').fill('15');
  await page.getByRole('button',{name:'Estimate round-trip time'}).click();
  await expect(page.getByRole('heading',{name:/Round-trip time estimate/})).toBeVisible({timeout:30000});
  await expect(page.locator('.budget-card')).toHaveCount(2);
  await expect(page.locator('.budget-card').first()).toContainText('Outbound / return');
  await expect(page.getByText(/Arithmetic only; not an EVA duration or safety guarantee/)).toBeVisible();
  await page.screenshot({path:fileURLToPath(new URL('mission-budget-candidates-desktop.png',output))});
  expect(errors).toEqual([]);
});

test('mission budget requires every user-entered assumption',async({page})=>{
  await page.goto('/');
  await expect(page.getByRole('button',{name:/Compare routes/})).toBeEnabled();
  await page.getByRole('button',{name:'Load verification pair'}).click();
  await expect(page.getByRole('spinbutton',{name:'Starting location longitude'})).not.toHaveValue('');
  await page.getByRole('button',{name:/Compare routes/}).click();
  await expect(page.getByTestId('distance-distance')).toBeVisible({timeout:30000});
  await page.getByLabel('Assumed walking speed km per hour').fill('4');
  await page.getByRole('button',{name:'Estimate round-trip time'}).click();
  await expect(page.getByRole('alert')).toContainText('Enter every mission time assumption');
});
