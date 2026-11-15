import {test,expect} from '@playwright/test';

test('keyboard focus is visible and the mission map has no horizontal overflow at 320 px',async({page})=>{
  await page.setViewportSize({width:320,height:740});
  await page.goto('/');
  await expect(page.getByRole('button',{name:/Compare routes/})).toBeEnabled();
  await page.keyboard.press('Tab');
  const focused=page.locator(':focus');
  await expect(focused).toBeVisible();
  const outline=await focused.evaluate(element=>getComputedStyle(element).outlineStyle);
  expect(outline).not.toBe('none');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBe(320);
  const map=page.locator('#terrain-map');
  await expect(map).toHaveAttribute('aria-label',/Interactive Jezero terrain map/);
  await map.focus();
  await page.keyboard.press('ArrowRight');
  await expect(map).toBeFocused();
});
