// The site's claims are copies, so each is checked against the file it was copied from: a number changed in the README
// and not on the page, or the other way round, turns this red.
const fs = require('node:fs');
const path = require('node:path');
const { test, expect, panes, ready } = require('./site');

const REPO = path.join(__dirname, '..', '..');
const read = (file) => fs.readFileSync(path.join(REPO, file), 'utf8');
// Markdown markup and typographic quotes are not part of a claim. A quote may start mid-sentence in its source, so both
// sides are lower-cased, and a full stop the page adds at the end of a quoted clause is dropped.
const plain = (s) => s.replace(/\*\*|`/g, '').replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, ' ').trim().toLowerCase();

test('every passage marked with a source is in that file word for word', async ({ page, site, viewer }) => {
  const marked = [];
  for (const url of [site, viewer]) {
    await page.goto(url);
    marked.push(...(await page.locator('[data-source]').evaluateAll((els) => els.map((e) => [e.dataset.source, e.textContent]))));
  }
  expect(marked.length).toBeGreaterThan(0);
  const missing = marked.filter(([file, text]) => !plain(read(file)).includes(plain(text).replace(/[.:]$/, '')));
  expect(missing).toEqual([]);
});

test('the results table is the README table, its runs shown as columns', async ({ page, site }) => {
  await page.goto(site);
  const readme = read('README.md');
  const section = readme.slice(readme.indexOf('## The phone tap gate, measured on GhostEI'));
  const runs = section.split('\n').filter((line) => line.startsWith('| ')).slice(0, 3).map((line) => line.split('|').slice(1, -1).map(plain));
  const shown = await page.locator('#result table tr').evaluateAll((trs) => trs.map((tr) => [...tr.cells].map((c) => c.textContent)));
  expect(shown[0].map((_, c) => shown.map((row) => plain(row[c])))).toEqual(runs);
});

test('the viewer stays off the landing page, and says it plays a placeholder on its link, its page and each pane', async ({ page, site, viewer }) => {
  await page.goto(site);
  await expect(page.locator('.pane, .stage')).toHaveCount(0);
  await expect(page.locator('a[href="arena.html"]')).toContainText('placeholder');
  await page.goto(viewer);
  await ready(page);
  await expect(page.locator('header .placeholder')).toContainText('Placeholder data');
  for (const pane of await panes(page).all()) await expect(pane.locator('.tag')).toHaveText('Placeholder data');
});

test('the demo clip waits for the visitor: its own controls, no autoplay, loaded from this site', async ({ page, site }) => {
  await page.goto(site);
  const clip = page.locator('header video');
  await expect(clip).toHaveAttribute('controls', '');
  await expect(clip).not.toHaveAttribute('autoplay');
  const state = () => clip.evaluate((v) => [v.paused, v.videoWidth, new URL(v.currentSrc).origin === location.origin]);
  await expect.poll(state).toEqual([true, 720, true]);
});
