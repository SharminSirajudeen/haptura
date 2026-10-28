const { test, expect, ready } = require('./site');

const network = (url) => /^(https?|wss?|ftp):/.test(url); // data:, blob: and about: never leave the machine

test('the page makes no request to another origin', async ({ page, site }) => {
  const home = new URL(site);
  const urls = [];
  page.context().on('request', (r) => urls.push(r.url()));
  // belt and braces: if a page ever does ask elsewhere, this test must not be the thing that sends it
  await page.context().route((u) => u.origin !== home.origin && network(u.href), (route) => route.abort());
  await page.goto(site);
  await ready(page);

  const local = urls.filter(network).filter((u) => new URL(u).origin === home.origin);
  const outside = urls.filter(network).filter((u) => new URL(u).origin !== home.origin);
  expect(outside).toEqual([]);
  // a page that loaded nothing would pass the line above: the five files the page is made of were asked for here
  const asked = local.map((u) => new URL(u).pathname.slice(home.pathname.length));
  expect(asked).toEqual(expect.arrayContaining(['', 'style.css', 'app.js', 'fixtures/episode.json', 'fixtures/clip.mp4']));
});

test('the page runs under a sub-path because every path in it is relative', async ({ page, site }) => {
  await page.goto(site);
  await ready(page);
  await expect(page.locator('video').first()).toHaveJSProperty('videoWidth', 128);
});
