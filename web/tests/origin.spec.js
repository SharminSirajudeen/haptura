const { test, expect, ready } = require('./site');

const network = (url) => /^(https?|wss?|ftp):/.test(url); // data:, blob: and about: never leave the machine

test('the page makes no request to another origin', async ({ page, site, viewer }) => {
  test.slow(); // one tap on the landing page loads Python first
  const home = new URL(site);
  const urls = [];
  page.context().on('request', (r) => urls.push(r.url()));
  // belt and braces: if a page ever does ask elsewhere, this test must not be the thing that sends it
  await page.context().route((u) => u.origin !== home.origin && network(u.href), (route) => route.abort());
  await page.goto(site); // the landing page, until its clip has its size and one tap is judged (Python loaded); then the viewer, until both panes draw
  await expect(page.locator('video')).toHaveJSProperty('videoWidth', 720);
  await page.locator('#try .recorded').first().click();
  await expect(page.locator('#try .kind').first()).toHaveText(/Allowed|Blocked/, { timeout: 30000 });
  await page.goto(viewer);
  await ready(page);
  const outside = urls.filter(network).filter((u) => new URL(u).origin !== home.origin);
  expect(outside).toEqual([]);
  // a page that loaded nothing would pass the line above: the files both pages are made of were asked for here
  const asked = urls.filter(network).filter((u) => new URL(u).origin === home.origin).map((u) => new URL(u).pathname.slice(home.pathname.length));
  expect(asked).toEqual(expect.arrayContaining(['', 'style.css', 'media/case26-dialog.mp4', 'gate.js', 'captures/replay.json', 'phone/windows.py', 'phone/rules.py', 'vendor/pyodide/pyodide.mjs', 'vendor/pyodide/pyodide.asm.wasm', 'vendor/pyodide/python_stdlib.zip', 'arena.html', 'app.js', 'episodes/baseline.json', 'episodes/baseline.mp4', 'episodes/gated.json', 'episodes/gated.mp4']));
});

test('the page runs under a sub-path because every path in it is relative', async ({ page, viewer }) => {
  await page.goto(viewer);
  await ready(page);
  await expect(page.locator('video').first()).toHaveJSProperty('videoWidth', 128);
});
