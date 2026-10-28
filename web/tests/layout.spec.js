const { test, expect, panes, ready } = require('./site');

const boxes = (page) => Promise.all([panes(page).first().boundingBox(), panes(page).last().boundingBox()]);

test('the panes sit side by side on a desktop and stack on a phone', async ({ page, site }) => {
  await page.goto(site);
  await ready(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  const [left, right] = await boxes(page);
  expect(right.y).toBe(left.y);
  expect(right.x).toBeGreaterThanOrEqual(left.x + left.width);
  await page.setViewportSize({ width: 375, height: 700 });
  const [top, bottom] = await boxes(page);
  expect(bottom.y).toBeGreaterThanOrEqual(top.y + top.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
