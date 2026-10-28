const { test, panes, ready, showFrame, FRAME } = require('./site');

// The first draw and every redraw after a seek must not depend on a frame callback or a resize notice: a frame can be
// shown before either is registered. Both are switched off here; `late` is the file that arrives after the page has
// been set up (the clip: the log is read first) or before it is (the log: the clip is fully loaded by then).
for (const late of ['clip', 'log']) {
  test(`a pane draws with no frame callback or resize notice when the ${late} arrives last`, async ({ page, viewer }) => {
    await page.addInitScript(() => {
      HTMLVideoElement.prototype.requestVideoFrameCallback = () => 0;
      window.ResizeObserver = class { observe() {} };
    });
    await page.route(`**/fixtures/${late === 'clip' ? 'clip.mp4' : 'episode.json'}`, async (route) => {
      await new Promise((done) => setTimeout(done, 1000));
      await route.continue();
    });
    await page.goto(viewer);
    await ready(page);
    await showFrame(panes(page).first(), FRAME.act, 'block 3 of 3, act');
  });
}
