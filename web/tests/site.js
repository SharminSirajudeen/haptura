// What every spec shares: a static server for web/ (Node's http, no dependency) and the waits that make a spec
// deterministic. The server mounts web/ under /haptura/, as GitHub Pages does, so an absolute path in the
// page 404s here exactly as it would there.
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { test: base, expect } = require('@playwright/test');

const ROOT = path.join(__dirname, '..');
const PREFIX = '/haptura/';
// the page's FPS must be the project's; a pattern that matches nothing throws here and every spec fails
const FPS = Number(/^FPS = (\d+)$/m.exec(fs.readFileSync(path.join(ROOT, '..', 'gate', 'constants.py'), 'utf8'))[1]);
const readJson = (...parts) => JSON.parse(fs.readFileSync(path.join(ROOT, ...parts), 'utf8'));
const LOG = readJson('fixtures', 'episode.json'); // the synthetic episode: it draws every label the real pair does not
// the seconds of a clip gate.demo looks in: FIRST_FRAMES = <seconds> * FPS in gate/demo.py
const WINDOW_SECONDS = Number(/^FIRST_FRAMES = (\d+) \* FPS/m.exec(fs.readFileSync(path.join(ROOT, '..', 'gate', 'demo.py'), 'utf8'))[1]);
// the pairs the page's pair is one of: the episodes per condition in results/table.md, which gate.eval writes
const EPISODES = Number(/^\| episodes \| (\d+) \|/m.exec(fs.readFileSync(path.join(ROOT, '..', 'results', 'table.md'), 'utf8'))[1]);
const PAIR = ['baseline', 'gated'].map((name) => ({ name, log: readJson('episodes', `${name}.json`) })); // the panes' order
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.mp4': 'video/mp4',
  '.png': 'image/png',
  '.mjs': 'text/javascript; charset=utf-8',
  '.wasm': 'application/wasm',
  '.zip': 'application/zip',
  '.py': 'text/x-python; charset=utf-8',
};
// The gate's own two files, which the page runs, are served from the repository: .github/workflows/pages.yml copies
// them under the site the same way.
const SOURCE = /^phone\/(windows|rules)\.py$/;

function serve(req, res) {
  const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const rel = url.slice(PREFIX.length) || 'index.html';
  const base = SOURCE.test(rel) ? path.join(ROOT, '..') : ROOT;
  const file = path.join(base, rel);
  if (!url.startsWith(PREFIX) || !file.startsWith(base + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end('not found');
    return;
  }
  const size = fs.statSync(file).size;
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || ''); // video seeking needs byte ranges
  const start = range ? (range[1] === '' ? size - Number(range[2]) : Number(range[1])) : 0;
  const end = range && range[1] !== '' && range[2] !== '' ? Math.min(Number(range[2]), size - 1) : size - 1;
  res.writeHead(range ? 206 : 200, {
    'content-type': TYPES[path.extname(file)] || 'application/octet-stream',
    'accept-ranges': 'bytes',
    'content-length': end - start + 1,
    ...(range && { 'content-range': `bytes ${start}-${end}/${size}` }),
  });
  fs.createReadStream(file, { start, end }).pipe(res);
}

const test = base.extend({
  site: [
    async ({}, use) => {
      const server = http.createServer(serve);
      await new Promise((done) => server.listen(0, '127.0.0.1', done));
      await use(`http://127.0.0.1:${server.address().port}${PREFIX}`);
      await new Promise((done) => server.close(done));
    },
    { scope: 'worker' },
  ],
  viewer: [async ({ site }, use) => use(`${site}arena.html`), { scope: 'worker' }], // the arena viewer's page
});

const panes = (page) => page.locator('.pane');

// Both panes have drawn their first frame.
const ready = (page) => expect(page.locator('.pane[data-ready]')).toHaveCount(2);

// What the pane last drew (the page writes it beside every draw): the video frame it was for, the media time of the clip's
// first frame, and the label rectangles in CSS pixels.
const shown = async (pane) => JSON.parse(await pane.locator('canvas').getAttribute('data-labels'));

// Pause the pane's video on video frame `frame` (the middle of its time slot, counted from the clip's first frame, which
// an encoder's frame delay can put after media time 0) and wait for the seek; the page draws on it.
async function seek(pane, frame) {
  const { start } = await shown(pane);
  await pane.locator('video').evaluate(
    (v, at) =>
      new Promise((done) => {
        v.pause();
        v.addEventListener('seeked', done, { once: true });
        v.currentTime = at;
      }),
    start + (frame + 0.5) / FPS,
  );
}

// ... and wait until the pane shows `where`; the canvas is drawn in the same call that writes `.where`.
async function showFrame(pane, frame, where) {
  await seek(pane, frame);
  await expect(pane.locator('.where')).toHaveText(where);
}

// Both panes play the synthetic episode in place of the real pair: the page asks for episodes/*.json and *.mp4, and `log`
// (the fixture's, unless a spec changes it) and fixtures/clip.mp4 answer. A redirect, not a copy, so the server's byte
// ranges still serve the clip.
async function playFixture(page, log = LOG) {
  await page.route('**/episodes/*.json', (route) => route.fulfill({ json: log }));
  await page.route('**/episodes/*.mp4', (route) => route.continue({ url: route.request().url().replace(/episodes\/\w+\.mp4$/, 'fixtures/clip.mp4') }));
}

// The last video frame of a log's clip, and what a pane says there: its last block.
const endOf = (log) => ({
  frame: log.blocks.reduce((n, b) => n + b.actions.length, 0),
  where: `block ${log.blocks.length} of ${log.blocks.length}, ${log.blocks.at(-1).phase}`,
});

// Video frames inside each block of the fixture: block 1 starts at frame 0, block 2 at 30, block 3 (act) at 60.
// ACT is block 3's frame 5, where the three elements are far apart (before the occlusion gap at its frames 11 to 13).
const FRAME = { probe1: 10, probe2: 40, act: 65 };

module.exports = { test, expect, panes, ready, seek, shown, showFrame, playFixture, endOf, FRAME, LOG, PAIR, EPISODES, WINDOW_SECONDS };
