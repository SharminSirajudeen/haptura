// What the viewer plays is one real pair from the kill test, and it says so. Every name and number below comes from a file
// the page was made from (the two logs, results/table.md), not from a second copy of the page's own words.
const { test, expect, panes, ready, shown, showFrame, endOf, EPISODES, PAIR, WINDOW_SECONDS } = require('./site');

test('the banner names the pair the panes play, the rule that chose it and its place among the kill test', async ({ page, viewer }) => {
  const [baseline, gated] = PAIR.map(({ log }) => log);
  expect(gated.scenario).toEqual(baseline.scenario); // one scenario, run under two conditions
  await page.goto(viewer);
  const banner = page.locator('header .provenance');
  for (const text of [
    'Muse Wonder',
    `${gated.condition} against ${baseline.condition}`,
    `seed ${gated.scenario.seed}, case ${gated.scenario.case}`,
    `one pair of ${EPISODES}, not the result`,
    'the first pair on the list from python -m gate.demo',
    `in the first ${WINDOW_SECONDS} seconds of its clip, the baseline commits to an element it does not control`,
    'the gated run, right by EVAL.md, has not acted yet',
    'EVAL.md\'s verdict on it is Rethink',
  ]) await expect(banner).toContainText(text);
  await expect(banner.getByRole('link', { name: 'README' })).toHaveAttribute('href', 'https://github.com/SharminSirajudeen/haptura#readme');
});

test('each pane plays its own run: named from its log, its clip, and ending where its log ends', async ({ page, viewer }) => {
  await page.goto(viewer);
  await ready(page);
  for (const [i, { name, log }] of PAIR.entries()) {
    const pane = panes(page).nth(i);
    const { frame, where } = endOf(log);
    await expect(pane.locator('h2')).toHaveText(log.condition);
    await expect(pane.locator('.tag')).toHaveText(`kill test, seed ${log.scenario.seed}, ${log.scenario.case}, outcome ${log.outcome}`);
    expect(await pane.locator('video').evaluate((v) => v.currentSrc)).toMatch(new RegExp(`/episodes/${name}\\.mp4$`));
    await showFrame(pane, frame, where);
    await expect(pane.locator('.decision')).toContainText(log.blocks.at(-1).decision.reason);
  }
});

test('the intro says what each agent was shown: the gated one the labels and advice, the baseline one only the means', async ({ page, viewer }) => {
  await page.goto(viewer);
  const intro = page.locator('header .intro-p');
  await expect(intro).toContainText("The gated agent is shown that test's labels and advice.");
  await expect(intro).toContainText("returns only each element's mean displacement per action, with no p, no label and no advice");
});

test("each pane starts on its log's first frame, though its clip's first frame is not at media time 0", async ({ page, viewer }) => {
  await page.goto(viewer);
  await ready(page);
  for (const pane of await panes(page).all()) {
    expect((await shown(pane)).frame).toBe(0);
    await expect(pane.locator('.where')).toHaveText(/^block 1 of \d+, /);
  }
});
