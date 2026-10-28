const { test, expect, panes, ready, showFrame, FRAME, LOG } = require('./site');

const EYES_SWAPPED = 'my eyes swapped two objects, corrected';
const legend = (pane) => pane.locator('.labels li');

test('the labels follow the time', async ({ page, site }) => {
  await page.goto(site);
  await ready(page);
  for (const pane of await panes(page).all()) {
    await showFrame(pane, FRAME.act, 'block 3 of 3, act'); // later first: going back in time must undo what it showed
    await expect(legend(pane)).toHaveText(['track 1: mine', 'track 2: not me', 'track 3: not me']);
    await expect(pane.locator('.caption')).toContainText(EYES_SWAPPED);

    await showFrame(pane, FRAME.probe1, 'block 1 of 3, probe');
    await expect(legend(pane)).toHaveText(['track 1: unsure, checking', 'track 2: unsure, checking', 'track 3: not me']);
    await expect(pane.locator('.caption')).not.toContainText(EYES_SWAPPED);

    await showFrame(pane, FRAME.probe2, 'block 2 of 3, probe');
    await expect(legend(pane)).toHaveText(['track 1: mine', 'track 2: unsure, checking', 'track 3: not me']);
    await expect(pane.locator('.caption')).not.toContainText(EYES_SWAPPED);
  }
});

test('the block changes on the frame the log starts it, at the rate in gate/constants.py', async ({ page, site }) => {
  await page.goto(site);
  await ready(page);
  const pane = panes(page).first();
  const total = LOG.blocks.reduce((n, b) => n + b.actions.length, 0); // the last video frame
  await showFrame(pane, 29, 'block 1 of 3, probe');
  await showFrame(pane, 30, 'block 2 of 3, probe');
  await showFrame(pane, 59, 'block 2 of 3, probe');
  await showFrame(pane, 60, 'block 3 of 3, act');
  await showFrame(pane, total, 'block 3 of 3, act'); // the last frame is the last block's frame BLOCK_STEPS
});

const BODY = { up: [0, -2], down: [0, 2], left: [-2, 0], right: [2, 0] };
const LINES = [
  ['body_changed', { diagnosis: { kind: 'body_changed', fix: 'x', swap: null, body: BODY } }, 'my controls changed, relearning'],
  ['target_lost', { diagnosis: { kind: 'target_lost', fix: 'x', swap: null, body: null } }, 'control moved, re-probing'],
  ['decline', { diagnosis: null, decision: { kind: 'decline', object_id: null, reason: 'x' } }, "I can't do this, declining"],
];
for (const [name, change, line] of LINES) {
  test(`a ${name} block says "${line}"`, async ({ page, site }) => {
    const log = structuredClone(LOG);
    Object.assign(log.blocks[2], change);
    await page.route('**/fixtures/episode.json', (route) => route.fulfill({ json: log }));
    await page.goto(site);
    await ready(page);
    await showFrame(panes(page).first(), FRAME.act, 'block 3 of 3, act');
    await expect(panes(page).first().locator('.fix')).toHaveText(line);
  });
}
