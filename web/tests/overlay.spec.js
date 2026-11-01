const { test, expect, panes, ready, showFrame, playFixture, FRAME, LOG } = require('./site');

const EYES_SWAPPED = 'my eyes swapped two objects, corrected';

// Runs in the page. For each point (in video pixels) counts the non-transparent canvas pixels within `r` of it.
function ink(canvas, { points, r }) {
  const scale = canvas.width / canvas.previousElementSibling.videoWidth; // canvas pixels per video pixel
  const { data } = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height);
  const range = (lo, hi) => Array.from({ length: Math.max(0, hi - lo) }, (_, i) => lo + i);
  const around = (c, limit) => range(Math.max(0, Math.floor((c - r) * scale)), Math.min(limit, Math.ceil((c + r) * scale)));
  const alphas = ([x, y]) => around(y, canvas.height).flatMap((py) => around(x, canvas.width).map((px) => data[(py * canvas.width + px) * 4 + 3]));
  return points.map((p) => alphas(p).filter((a) => a > 0).length);
}

test('the overlay draws and the caption names the eyes swap', async ({ page, viewer }) => {
  await playFixture(page);
  await page.goto(viewer);
  await ready(page);
  const tracked = Object.values(LOG.blocks[2].tracks).map((pts) => pts[FRAME.act - 60]);
  const empty = [110, 10]; // far from every element and from every label
  for (const pane of await panes(page).all()) {
    await showFrame(pane, FRAME.act, 'block 3 of 3, act');
    const counts = await pane.locator('canvas').evaluate(ink, { points: [...tracked, empty], r: 7 });
    expect(counts.slice(0, -1).every((n) => n > 0)).toBe(true); // ink at every tracked position
    expect(counts.at(-1)).toBe(0); // and none where there is no element
    await expect(pane.locator('.caption')).toContainText(EYES_SWAPPED);
  }
});
