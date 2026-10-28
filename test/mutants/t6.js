// T6: the demo page (web/). One entry per guarded line, in the kit's format for another runner (see the header of
// docs/project-kit/test/mutants.list.js): `cmd` runs the spec with Playwright's dot reporter, which prints nothing for a
// passing test, and `expect` is the failing test's own header line as that reporter prints it (file:line:column › title).
// Moving a test in a spec moves its entry's `expect` in the same change.
const PW = 'npx playwright test -c web/playwright.config.js --reporter=dot --workers=1';
const m = (from, file, find, replace, spec, at, title) => ({
  from, file, find, replace, mustFail: `web/tests/${spec}`, cmd: `${PW} web/tests/${spec}`, expect: `web/tests/${spec}:${at} › ${title}`,
});
const ORIGIN = 'the page makes no request to another origin', SUBPATH = 'the page runs under a sub-path because every path in it is relative';
const OVERLAY = 'the overlay draws and the caption names the eyes swap', LAYOUT = 'the panes sit side by side on a desktop and stack on a phone';
const FOLLOW = 'the labels follow the time', BOUNDARY = 'the block changes on the frame the log starts it, at the rate in gate/constants.py';
const BOOT = 'a pane draws with no frame callback or resize notice when the ', LAST = ' arrives last';
const JS = 'web/app.js', HTML = 'web/index.html';
const LINK = '<link rel="stylesheet" href="style.css">\n';
module.exports = [
  m('origin: an outside stylesheet (a fonts host)', HTML, LINK, LINK + '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter&display=swap">\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside script', HTML, LINK, LINK + '<script src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"></script>\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside image', HTML, LINK, LINK + '<img src="https://example.com/pixel.gif" alt="">\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside fetch', JS, "  const log = await (await fetch(logUrl)).json();\n", "  fetch('https://example.com/ping');\n  const log = await (await fetch(logUrl)).json();\n", 'origin.spec.js', '5:1', ORIGIN),
  m('paths: the script is found only at the site root', HTML, '<script src="app.js"></script>', '<script src="/app.js"></script>', 'origin.spec.js', '22:1', SUBPATH),
  m('label: eyes_swapped says the body line', JS, "eyes_swapped: 'my eyes swapped two objects, corrected',", "eyes_swapped: 'my controls changed, relearning',", 'overlay.spec.js', '15:1', OVERLAY),
  m('label: boxes are drawn on the elements that are visible', JS, 'items.filter((it) => it.pt[0] !== null)', 'items.filter((it) => it.pt[0] === null)', 'overlay.spec.js', '15:1', OVERLAY),
  m('label: boxes are scaled to the canvas', JS, '  const px = x * k;\n', '  const px = x;\n', 'overlay.spec.js', '15:1', OVERLAY),
  m('label: body_changed says the target line', JS, "body_changed: 'my controls changed, relearning',", "body_changed: 'control moved, re-probing',", 'labels.spec.js', '43:3', 'a body_changed block says "my controls changed, relearning"'),
  m('label: target_lost says the eyes line', JS, "target_lost: 'control moved, re-probing',", "target_lost: 'my eyes swapped two objects, corrected',", 'labels.spec.js', '43:3', 'a target_lost block says "control moved, re-probing"'),
  m('label: a decline says it', JS, `const DECLINE = "I can't do this, declining";`, `const DECLINE = 'I cannot do this';`, 'labels.spec.js', '43:3', `a decline block says "I can't do this, declining"`),
  m('time: a probe that has not shown mine is still checking', JS, "blocks[b].phase === 'probe'", "blocks[b].phase === 'act'", 'labels.spec.js', '6:1', FOLLOW),
  m('time: an act block keeps the evidence of the probes before it', JS, 'blocks.slice(0, b + 1).reverse()', 'blocks.slice(b, b + 1).reverse()', 'labels.spec.js', '6:1', FOLLOW),
  m('time: a block starts on its first frame', JS, 'starts.findLastIndex((s) => s <= frame)', 'starts.findLastIndex((s) => s < frame)', 'labels.spec.js', '24:1', BOUNDARY),
  m('time: the page runs at the project frame rate', JS, 'const FPS = 10;', 'const FPS = 12;', 'labels.spec.js', '24:1', BOUNDARY),
  m('draw: a clip that arrives after the page is set up is drawn', JS, "['loadeddata', 'seeked']", "['seeked']", 'boot.spec.js', '7:3', BOOT + 'clip' + LAST),
  m('draw: a clip that arrived before the page was set up is drawn', JS, '  new ResizeObserver(render).observe(video);\n  render();\n', '  new ResizeObserver(render).observe(video);\n', 'boot.spec.js', '7:3', BOOT + 'log' + LAST),
  m('draw: a seek redraws the pane', JS, "['loadeddata', 'seeked']", "['loadeddata']", 'boot.spec.js', '7:3', BOOT + 'clip' + LAST),
  m('layout: the panes stack on a phone', 'web/style.css', 'grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));', 'grid-template-columns: 1fr 1fr;', 'layout.spec.js', '5:1', LAYOUT),
];
