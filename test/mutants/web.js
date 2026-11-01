// The demo page (web/). One entry per guarded line, in the format for another runner (`cmd` and `expect` instead of
// `mustFail`, as test/mutants.js reads them): `cmd` runs the spec with Playwright's dot reporter, which prints nothing for a
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
const JS = 'web/app.js', HTML = 'web/index.html', ARENA = 'web/arena.html', CSS = 'web/style.css';
const SOURCED = 'every passage marked with a source is in that file word for word';
const PLACEHOLDER = 'the viewer stays off the landing page, and says it plays a placeholder on its link, its page and each pane';
const CLIP = 'the demo clip waits for the visitor: its own controls, no autoplay, loaded from this site';
const GUTTER = (page, w) => `every band on the ${page} keeps the gutter on both edges at ${w} px`;
const AA = (page, scheme) => `every piece of text on the ${page} meets WCAG AA contrast in the ${scheme} scheme`;
const LINK = '<link rel="stylesheet" href="style.css">\n';
module.exports = [
  m('web: the layout fills the screen', 'web/style.css', 'header p { max-width: 70ch; }', 'header, main { max-width: 64rem; margin: 0 auto; } header p { max-width: 70ch; }',
    'fill.spec.js', '6:3', 'the layout fills a 1440 px screen minus the gutter'),
  m('web: no native controls over the clip', ARENA, '<video muted playsinline preload="auto">', '<video muted playsinline controls preload="auto">',
    'fill.spec.js', '15:1', 'nothing the browser draws covers the clip, and the scrubber moves the video'),
  m('web: the scrubber moves the video', 'web/app.js', "  scrub.addEventListener('input', () => { video.currentTime = Number(scrub.value); });\n", '',
    'fill.spec.js', '15:1', 'nothing the browser draws covers the clip, and the scrubber moves the video'),
  m('origin: an outside stylesheet (a fonts host)', HTML, LINK, LINK + '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter&display=swap">\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside script', HTML, LINK, LINK + '<script src="https://cdn.jsdelivr.net/npm/lodash@4.17.21/lodash.min.js"></script>\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside image', HTML, LINK, LINK + '<img src="https://example.com/pixel.gif" alt="">\n', 'origin.spec.js', '5:1', ORIGIN),
  m('origin: an outside fetch', JS, "  const log = await (await fetch(logUrl)).json();\n", "  fetch('https://example.com/ping');\n  const log = await (await fetch(logUrl)).json();\n", 'origin.spec.js', '5:1', ORIGIN),
  m('paths: the script is found only at the site root', ARENA, '<script src="app.js"></script>', '<script src="/app.js"></script>', 'origin.spec.js', '22:1', SUBPATH),
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
  // The landing page (web/index.html) and the arena viewer's own page (web/arena.html).
  m('landing: a quoted sentence edited', HTML, 'the gate decides whether a proposed tap may run.', 'the gate decides whether any tap may run.', 'landing.spec.js', '13:1', SOURCED),
  m('arena page: a quoted sentence edited', ARENA, 'did not hold on these seeds.</span>', 'held on these seeds.</span>', 'landing.spec.js', '13:1', SOURCED),
  m('landing: a results-table cell edited', HTML, '<td>0 of 18</td>', '<td>0 of 19</td>', 'landing.spec.js', '24:1', 'the results table is the README table, its runs shown as columns'),
  m('landing: the viewer link loses its placeholder label', HTML, 'Arena viewer (a placeholder episode, not a result)', 'Arena viewer', 'landing.spec.js', '33:1', PLACEHOLDER),
  m('arena page: the placeholder banner removed', ARENA, '<p class="placeholder"><strong class="tag">Placeholder data</strong>', '<p class="placeholder"><strong class="tag">Demo</strong>', 'landing.spec.js', '33:1', PLACEHOLDER),
  m('arena page: a pane without its placeholder label', ARENA, '<div class="pane-head"><h2></h2><p class="tag">Placeholder data</p></div>', '<div class="pane-head"><h2></h2></div>', 'landing.spec.js', '33:1', PLACEHOLDER),
  m('landing: the viewer back on the landing page', HTML, '<main id="main">', '<main id="main"><div class="stage"></div>', 'landing.spec.js', '33:1', PLACEHOLDER),
  m('landing: the clip plays by itself', HTML, '<video controls playsinline preload="metadata"', '<video controls autoplay muted playsinline preload="metadata"', 'landing.spec.js', '43:1', CLIP),
  m('landing: the clip without its controls', HTML, '<video controls playsinline preload="metadata"', '<video playsinline preload="metadata"', 'landing.spec.js', '43:1', CLIP),
  m('landing: the clip found only at the site root', HTML, '<source src="media/case26-dialog.mp4"', '<source src="/media/case26-dialog.mp4"', 'landing.spec.js', '43:1', CLIP),
  m('look: a band with twice the gutter', CSS, '.band { padding: clamp(64px, 9vw, 144px) var(--gutter); }', '.band { padding: clamp(64px, 9vw, 144px) calc(2 * var(--gutter)); }', 'look.spec.js', '52:5', GUTTER('landing page', 1440)),
  m('look: the bar with a fixed side padding', CSS, '  padding: 0 var(--gutter);\n  background:', '  padding: 0 24px;\n  background:', 'look.spec.js', '52:5', GUTTER('arena viewer', 1440)),
  m('look: a wider gutter cap than the test reads', CSS, '--gutter: clamp(16px, 5vw, 96px);', '--gutter: clamp(16px, 5vw, 120px);', 'look.spec.js', '52:5', GUTTER('landing page', 2560)),
  m('look: secondary text too light in the light scheme', CSS, '  --fg-2: #6e6e73;', '  --fg-2: #8e8e93;', 'look.spec.js', '63:5', AA('landing page', 'light')),
  m('look: secondary text too dark in the dark scheme', CSS, '    --fg-2: #a1a1a6;', '    --fg-2: #636366;', 'look.spec.js', '63:5', AA('arena viewer', 'dark')),
];
