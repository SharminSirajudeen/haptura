// Try the gate (web/gate.js): a tap on a recorded screen is judged in the browser by the gate's own two files, on that
// screen's dump and uid map. The expected verdicts are the records' own (web/captures/*.json, built by phone/captures.py).
const fs = require('node:fs');
const path = require('node:path');
const { test, expect } = require('./site');

const WEB = path.join(__dirname, '..');
const read = (...parts) => fs.readFileSync(path.join(WEB, ...parts), 'utf8');
const CAPTURE = Object.fromEntries(['replay', 'lab'].map((n) => [n, JSON.parse(read('captures', `${n}.json`))]));
const SLOW = { timeout: 30000 }; // the first verdict waits for Python to load
const POINT = /\((\d+), (\d+)\)/; // the display point the page judged, in its "window under" line
test.describe.configure({ timeout: 90000 }); // Python loads once per test, from a cold cache on a runner

const figure = (page, name) => page.locator(`#try figure[data-capture="captures/${name}.json"]`);

// The verdict the figure shows: its kind, its headline, its reason line, and what the focus check said.
async function shown(fig) {
  const out = fig.locator('.verdict');
  await expect(out).toBeVisible();
  const focus = await out.locator('.focus').textContent();
  return { kind: await out.getAttribute('data-kind'), head: await out.locator('.kind').textContent(), reason: await out.locator('.reason').textContent(), focus: /would say (\w+)/.exec(focus)[1] };
}

// Where the mark's centre sits on the screen, in CSS pixels from the screen's corner.
const markCentre = (fig) => fig.locator('.mark').evaluate((m) => [m.offsetLeft + m.offsetWidth / 2, m.offsetTop + m.offsetHeight / 2]);

// Open the page and tap where the screen's recording did, through its button, whose label says where that is: the
// screen shows that recording's frame, the verdict appears, and the mark lands on the point.
async function recordedTap(page, site, name) {
  await page.goto(site);
  const fig = figure(page, name);
  const cap = CAPTURE[name];
  const t = cap.touch;
  await expect(fig.locator('.screen img')).toHaveAttribute('src', cap.image);
  await expect(fig.locator('.recorded')).toContainText(`(${t.x}, ${t.y})`);
  await fig.locator('.recorded').click();
  await expect(fig.locator('.hit')).toContainText(`(${t.x}, ${t.y})`, SLOW);
  await expect(fig.locator('.mark')).toBeVisible();
  const box = await fig.locator('.screen').boundingBox();
  const [mx, my] = await markCentre(fig);
  expect([Math.abs(mx - (box.width * t.x) / cap.screen[0]) <= 1, Math.abs(my - (box.height * t.y) / cap.screen[1]) <= 1]).toEqual([true, true]);
  return { fig, cap, t };
}

// Tap the screen at a display point: the button's box scaled by the screen's size. A click lands on a whole CSS pixel,
// which is cap.screen[0] / box.width display pixels wide, so the judged point can be that far off; every point tapped
// here is further than that from a window's edge.
async function tapAt(fig, cap, [x, y]) {
  const before = await fig.locator('.hit').textContent();
  const box = await fig.locator('.screen').boundingBox();
  await fig.locator('.screen').click({ position: { x: (box.width * x) / cap.screen[0], y: (box.height * y) / cap.screen[1] } });
  await expect(fig.locator('.hit')).not.toHaveText(before, SLOW);
  const [, px, py] = POINT.exec(await fig.locator('.hit').textContent());
  const tolerance = cap.screen[0] / box.width;
  expect([Math.abs(px - x) <= tolerance, Math.abs(py - y) <= tolerance]).toEqual([true, true]);
}

test("the dialog screen: Muse's own tap is blocked and the attacker named; the status bar is allowed", async ({ page, site }) => {
  const { fig, cap, t } = await recordedTap(page, site, 'replay');
  expect(await shown(fig)).toEqual({ kind: t.verdict.kind, head: 'Blocked', reason: t.verdict.reason, focus: 'blocked' });
  await expect(fig.locator('.hit')).toContainText(`uid ${t.receiver_uid}`);
  await tapAt(fig, cap, [360, 30]); // the status bar, the system UI's: allowlisted
  expect(await shown(fig)).toEqual({ kind: 'allow', head: 'Allowed', reason: 'window owned by the allowlisted package com.android.systemui', focus: 'blocked' });
});

test('the keyboard screen: the key is blocked and the keyboard named, the page beside it allowed, and a focus check would allow both', async ({ page, site }) => {
  const { fig, cap, t } = await recordedTap(page, site, 'lab');
  expect(await shown(fig)).toEqual({ kind: 'block', head: 'Blocked', reason: t.verdict.reason, focus: 'allowed' });
  await tapAt(fig, cap, [48, 120]); // the search page's back arrow, above the keyboard
  expect(await shown(fig)).toEqual({ kind: 'allow', head: 'Allowed', reason: `window owned by the task app ${cap.task}`, focus: 'allowed' });
  await tapAt(fig, cap, [360, 690]); // 8 px inside the keyboard's top edge (y = 682): the point is scaled, not the pixel
  expect((await shown(fig)).reason).toEqual(t.verdict.reason);
});

test('Enter on a screen taps where its recording did', async ({ page, site }) => {
  await page.goto(site);
  const fig = figure(page, 'lab');
  await fig.locator('.screen').focus();
  await page.keyboard.press('Enter');
  await expect(fig.locator('.hit')).toContainText(`(${CAPTURE.lab.touch.x}, ${CAPTURE.lab.touch.y})`, SLOW);
});

test('a fetch that failed is tried again on the next tap', async ({ page, site }) => {
  const failedOnce = new Set(); // the capture and one of the gate's files each fail once, on the first tap
  await page.route(/captures\/lab\.json$|phone\/rules\.py$/, (route) => {
    const url = route.request().url();
    if (failedOnce.has(url)) return route.continue();
    failedOnce.add(url);
    return route.fulfill({ status: 404, body: 'gone' });
  });
  await page.goto(site);
  const fig = figure(page, 'lab');
  await fig.locator('.recorded').click();
  await expect(fig.locator('.status')).toContainText('could not load', SLOW);
  await fig.locator('.recorded').click();
  await expect(fig.locator('.hit')).toContainText(`(${CAPTURE.lab.touch.x}, ${CAPTURE.lab.touch.y})`, SLOW);
  expect(failedOnce.size).toEqual(2);
});

test("the gate's two files are served as they stand in the repository", async ({ page, site }) => {
  for (const f of ['phone/windows.py', 'phone/rules.py']) {
    const served = await (await page.request.get(site + f)).text();
    expect(served).toEqual(read('..', f));
  }
});

test('the deploy copies exactly the files the page runs, and runs again when they change', async () => {
  const files = JSON.parse(/^const SOURCE = (\[.*\]);$/m.exec(read('gate.js'))[1].replace(/'/g, '"'));
  const pages = read('..', '.github', 'workflows', 'pages.yml');
  expect(files.length).toBeGreaterThan(0);
  expect(pages).toContain(`- run: mkdir -p web/phone && cp ${files.join(' ')} web/phone/`);
  expect(files.filter((f) => !pages.includes(`'${f}'`))).toEqual([]); // each is in the push paths
  const served = new RegExp(/^const SOURCE = \/(.*)\/;$/m.exec(read('tests', 'site.js'))[1]); // and the test server serves each
  expect(files.filter((f) => !served.test(f))).toEqual([]);
});

test('nothing of the gate is fetched before the first tap', async ({ page, site }) => {
  const urls = [];
  page.on('request', (r) => urls.push(new URL(r.url()).pathname));
  await page.goto(site);
  await expect(page.locator('header video')).toHaveJSProperty('videoWidth', 720);
  await expect(page.locator('#try .screen')).toHaveCount(2);
  expect(urls.filter((u) => /vendor\/|captures\/|phone\//.test(u))).toEqual([]);
});
