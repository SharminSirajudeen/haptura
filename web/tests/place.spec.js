// A label is drawn wholly on the canvas and clear of every label placed before it (tracks in id order); one with no free
// place is left to the list under the pane. The page writes what it drew beside each draw (canvas data-labels, in CSS
// pixels) and these specs read it back at sampled frames: no screenshot is compared.
const { test, expect, panes, ready, seek, shown, playFixture, endOf, LOG, PAIR } = require('./site');

const STEP = 5;
// The frames sampled in a clip: every STEP-th, up to two short of the last. An encoder's frame delay puts a clip's last two
// frames past the length its container declares, so a seek stops short of them.
const sampled = (log) => Array.from({ length: Math.floor((endOf(log).frame - 2) / STEP) + 1 }, (_, i) => i * STEP);
// two rectangles touch unless one lies wholly to a side of the other (sharing an edge is not touching)
const touches = (a, b) => !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
const outside = (r, width, height) => r.x < 0 || r.y < 0 || r.x + r.w > width + 1e-6 || r.y + r.h > height + 1e-6;

// Seven tracks that stay put (video pixels), worked out by hand. 0, 1 and 2 sit 5 apart, so their labels collide: 0 goes
// above its box, 1 below it, 2 finds no free place. 3 and 4 sit on the bottom edge: 3 above, 4 below, which the canvas's
// bottom edge pushes up. 5 and 6 sit on the right and left edges and are pushed in. The same at every width.
const still = (x, y) => Array.from({ length: 91 }, () => [x, y]);
const CROWD = {
  condition: 'a crowd', scenario: { seed: 0, case: 'crowd' }, outcome: 'success',
  blocks: [{
    phase: 'probe', actions: Array(90).fill('noop'), evidence: [], advice: null, decision: null, diagnosis: null,
    tracks: { 0: still(60, 60), 1: still(65, 60), 2: still(70, 60), 3: still(60, 124), 4: still(65, 124), 5: still(124, 30), 6: still(4, 30) },
  }],
};
const SUBJECTS = [
  { name: 'the real pair', logs: PAIR.map(({ log }) => log) },
  { name: 'the synthetic episode', logs: [LOG, LOG], play: playFixture },
  { name: 'a crowd of tracks', logs: [CROWD, CROWD], play: (page) => playFixture(page, CROWD), drawn: [0, 1, 3, 4, 5, 6] },
];

for (const { name, logs, play, drawn } of SUBJECTS) {
  for (const width of [390, 1440]) {
    test(`labels stay on the canvas and clear of each other at ${width} px on ${name}`, async ({ page, viewer }) => {
      await page.setViewportSize({ width, height: 900 });
      if (play) await play(page);
      await page.goto(viewer);
      await ready(page);
      for (const [i, log] of logs.entries()) {
        const pane = panes(page).nth(i);
        const [w, h] = await pane.locator('canvas').evaluate((c) => [c.clientWidth, c.clientHeight]);
        for (const frame of sampled(log)) {
          await seek(pane, frame);
          const { frame: at, rects } = await shown(pane);
          expect(at).toBe(frame);
          rects.forEach((r, j) => {
            expect(outside(r, w, h), `frame ${frame}: label ${r.id} leaves the canvas`).toBe(false);
            rects.slice(j + 1).forEach((q) => expect(touches(r, q), `frame ${frame}: labels ${r.id} and ${q.id} touch`).toBe(false));
          });
          if (drawn) {
            expect(rects.map((r) => r.id)).toEqual(drawn);
            await expect(pane.locator('.labels li')).toHaveCount(Object.keys(log.blocks[0].tracks).length); // every track is listed
          }
        }
      }
    });
  }
}

test('the intro says a label with no free place is left off the picture, and the list names every track', async ({ page, viewer }) => {
  await page.goto(viewer);
  await expect(page.locator('header .intro-p')).toContainText('a label with no free place is left off the picture, and the list under each pane names every track');
});
