// What every spec shares: a static server for web/ (Node's http, no dependency) and the waits that make a spec
// deterministic. The server mounts web/ under /control-gate/, as GitHub Pages does, so an absolute path in the
// page 404s here exactly as it would there.
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { test: base, expect } = require('@playwright/test');

const ROOT = path.join(__dirname, '..');
const PREFIX = '/control-gate/';
// the page's FPS must be the project's; a pattern that matches nothing throws here and every spec fails
const FPS = Number(/^FPS = (\d+)$/m.exec(fs.readFileSync(path.join(ROOT, '..', 'gate', 'constants.py'), 'utf8'))[1]);
const LOG = JSON.parse(fs.readFileSync(path.join(ROOT, 'fixtures', 'episode.json'), 'utf8'));
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json',
  '.mp4': 'video/mp4',
  '.png': 'image/png',
};

function serve(req, res) {
  const url = decodeURIComponent(new URL(req.url, 'http://x').pathname);
  const file = path.join(ROOT, url.slice(PREFIX.length) || 'index.html');
  if (!url.startsWith(PREFIX) || !file.startsWith(ROOT + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
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

// Pause the pane's video on video frame `frame` (the middle of its time slot) and wait until the pane shows `where`;
// the canvas is drawn in the same call that writes `.where`.
async function showFrame(pane, frame, where) {
  await pane.locator('video').evaluate(
    (v, at) =>
      new Promise((done) => {
        v.pause();
        v.addEventListener('seeked', done, { once: true });
        v.currentTime = at;
      }),
    (frame + 0.5) / FPS,
  );
  await expect(pane.locator('.where')).toHaveText(where);
}

// Video frames inside each block of the fixture: block 1 starts at frame 0, block 2 at 30, block 3 (act) at 60.
// ACT is block 3's frame 5, where the three elements are far apart (before the occlusion gap at its frames 11 to 13).
const FRAME = { probe1: 10, probe2: 40, act: 65 };

module.exports = { test, expect, panes, ready, showFrame, FRAME, LOG };
