const { test, expect, panes, ready } = require('./site');

const GUTTER = 16; // body padding, 1rem

for (const width of [1440, 1920, 2560]) {
  test(`the layout fills a ${width} px screen minus the gutter`, async ({ page, site }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(site);
    await ready(page);
    const main = await page.locator('main').boundingBox();
    expect(main.width).toBeGreaterThanOrEqual(width - 2 * GUTTER - 1);
  });
}

test('nothing the browser draws covers the clip, and the scrubber moves the video', async ({ page, site }) => {
  await page.goto(site);
  await ready(page);
  const pane = panes(page).first();
  expect(await pane.locator('video').getAttribute('controls')).toBeNull();
  const stage = await pane.locator('.stage').boundingBox();
  const bar = await pane.locator('.bar').boundingBox();
  expect(bar.y).toBeGreaterThanOrEqual(stage.y + stage.height);
  await pane.locator('.scrub').fill('3.5');
  await expect.poll(() => pane.locator('video').evaluate((v) => v.currentTime)).toBeCloseTo(3.5, 1);
});
