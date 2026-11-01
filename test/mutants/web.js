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
const LABELS = 'the viewer stays off the landing page, and says on its link, its page and each pane that it plays one pair from the kill test, not the result';
const CLIP = 'the demo clip waits for the visitor: its own controls, no autoplay, loaded from this site';
const GUTTER = (page, w) => `every band on the ${page} keeps the gutter on both edges at ${w} px`;
const AA = (page, scheme) => `every piece of text on the ${page} meets WCAG AA contrast in the ${scheme} scheme`;
const LINK = '<link rel="stylesheet" href="style.css">\n';
const BANNER = 'the banner names the pair the panes play, the rule that chose it and its place among the kill test';
const OWN = 'each pane plays its own run: named from its log, its clip, and ending where its log ends';
const SHOWN = 'the intro says what each agent was shown: the gated one the labels and advice, the baseline one only the means';
const PANE = (log, clip) => `{ log: 'episodes/${log}.json', clip: 'episodes/${clip}.mp4' }`;
const PLACE = (width, on) => `labels stay on the canvas and clear of each other at ${width} px on ${on}`;
const INTRO = 'the intro says a label with no free place is left off the picture, and the list names every track';
const FIRST = "each pane starts on its log's first frame, though its clip's first frame is not at media time 0";
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
  m('label: body_changed says the target line', JS, "body_changed: 'my controls changed, relearning',", "body_changed: 'control moved, re-probing',", 'labels.spec.js', '45:3', 'a body_changed block says "my controls changed, relearning"'),
  m('label: target_lost says the eyes line', JS, "target_lost: 'control moved, re-probing',", "target_lost: 'my eyes swapped two objects, corrected',", 'labels.spec.js', '45:3', 'a target_lost block says "control moved, re-probing"'),
  m('label: a decline says it', JS, `const DECLINE = "I can't do this, declining";`, `const DECLINE = 'I cannot do this';`, 'labels.spec.js', '45:3', `a decline block says "I can't do this, declining"`),
  m('time: a probe that has not shown mine is still checking', JS, "blocks[b].phase === 'probe'", "blocks[b].phase === 'act'", 'labels.spec.js', '6:1', FOLLOW),
  m('time: an act block keeps the evidence of the probes before it', JS, 'blocks.slice(0, b + 1).reverse()', 'blocks.slice(b, b + 1).reverse()', 'labels.spec.js', '6:1', FOLLOW),
  m('time: a block starts on its first frame', JS, 'starts.findLastIndex((s) => s <= frame)', 'starts.findLastIndex((s) => s < frame)', 'labels.spec.js', '25:1', BOUNDARY),
  m('time: the page runs at the project frame rate', JS, 'const FPS = 10;', 'const FPS = 12;', 'labels.spec.js', '25:1', BOUNDARY),
  m('draw: a clip that arrives after the page is set up is drawn', JS, "['loadeddata', 'seeked']", "['seeked']", 'boot.spec.js', '8:3', BOOT + 'clip' + LAST),
  m('draw: a clip that arrived before the page was set up is drawn', JS, '  new ResizeObserver(render).observe(video);\n  render();\n', '  new ResizeObserver(render).observe(video);\n', 'boot.spec.js', '8:3', BOOT + 'log' + LAST),
  m('draw: a seek redraws the pane', JS, "['loadeddata', 'seeked']", "['loadeddata']", 'boot.spec.js', '8:3', BOOT + 'clip' + LAST),
  m('layout: the panes stack on a phone', 'web/style.css', 'grid-template-columns: repeat(auto-fit, minmax(min(100%, 20rem), 1fr));', 'grid-template-columns: 1fr 1fr;', 'layout.spec.js', '5:1', LAYOUT),
  // The landing page (web/index.html) and the arena viewer's own page (web/arena.html).
  m('landing: a quoted sentence edited', HTML, 'the gate decides whether a proposed tap may run.', 'the gate decides whether any tap may run.', 'landing.spec.js', '13:1', SOURCED),
  m('arena page: a quoted sentence edited', ARENA, 'did not hold on these seeds.</span>', 'held on these seeds.</span>', 'landing.spec.js', '13:1', SOURCED),
  m('landing: a results-table cell edited', HTML, '<td>0 of 18</td>', '<td>0 of 19</td>', 'landing.spec.js', '24:1', 'the results table is the README table, its runs shown as columns'),
  m('landing: the viewer link loses its pair label', HTML, 'Arena viewer (one kill-test pair of 114, picked by a fixed rule, not the result)', 'Arena viewer', 'landing.spec.js', '33:1', LABELS),
  m('landing: the viewer link names another count', HTML, 'one kill-test pair of 114,', 'one kill-test pair of 115,', 'landing.spec.js', '33:1', LABELS),
  m('arena page: the pair banner removed', ARENA, '<p class="provenance"><strong class="tag">One pair from the kill test</strong>', '<p class="provenance"><strong class="tag">Demo</strong>', 'landing.spec.js', '33:1', LABELS),
  m('arena page: a pane without its pair label', ARENA, '<div class="pane-head"><h2></h2><p class="tag"></p></div>', '<div class="pane-head"><h2></h2></div>', 'landing.spec.js', '33:1', LABELS),
  m('landing: the viewer back on the landing page', HTML, '<main id="main">', '<main id="main"><div class="stage"></div>', 'landing.spec.js', '33:1', LABELS),
  m('landing: the clip plays by itself', HTML, '<video controls playsinline preload="metadata"', '<video controls autoplay muted playsinline preload="metadata"', 'landing.spec.js', '43:1', CLIP),
  m('landing: the clip without its controls', HTML, '<video controls playsinline preload="metadata"', '<video playsinline preload="metadata"', 'landing.spec.js', '43:1', CLIP),
  m('landing: the clip found only at the site root', HTML, '<source src="media/case26-dialog.mp4"', '<source src="/media/case26-dialog.mp4"', 'landing.spec.js', '43:1', CLIP),
  m('look: a band with twice the gutter', CSS, '.band { padding: clamp(64px, 9vw, 144px) var(--gutter); }', '.band { padding: clamp(64px, 9vw, 144px) calc(2 * var(--gutter)); }', 'look.spec.js', '52:5', GUTTER('landing page', 1440)),
  m('look: the bar with a fixed side padding', CSS, '  padding: 0 var(--gutter);\n  background:', '  padding: 0 24px;\n  background:', 'look.spec.js', '52:5', GUTTER('arena viewer', 1440)),
  m('look: a wider gutter cap than the test reads', CSS, '--gutter: clamp(16px, 5vw, 96px);', '--gutter: clamp(16px, 5vw, 120px);', 'look.spec.js', '52:5', GUTTER('landing page', 2560)),
  m('look: secondary text too light in the light scheme', CSS, '  --fg-2: #6e6e73;', '  --fg-2: #8e8e93;', 'look.spec.js', '63:5', AA('landing page', 'light')),
  m('look: secondary text too dark in the dark scheme', CSS, '    --fg-2: #a1a1a6;', '    --fg-2: #636366;', 'look.spec.js', '63:5', AA('arena viewer', 'dark')),
  // The pair the viewer plays (web/episodes/, from gate.demo): the banner's names and numbers are checked against the logs and
  // results/table.md, and each pane against its own log and clip.
  m('pair: the banner names another agent', ARENA, 'Muse Wonder, gated+SAM', 'Muse Spark, gated+SAM', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner swaps the conditions', ARENA, 'gated+SAM against no-gate+SAM', 'no-gate+SAM against gated+SAM', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner names another seed', ARENA, 'seed 1003,', 'seed 1004,', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner names another case', ARENA, 'case blocked.', 'case feasible.', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner names another count', ARENA, 'one pair of 114, not the result', 'one pair of 115, not the result', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner drops the rule that chose the pair', ARENA, 'the first pair on the list from <code>python -m gate.demo</code>', 'a pair from <code>python -m gate.demo</code>', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner names another window', ARENA, 'in the first 20 seconds of its clip', 'in the first 30 seconds of its clip', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner drops the baseline half of the rule', ARENA, 'the baseline commits to an element it does not control', 'the baseline commits to an element', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner drops the gated half of the rule', ARENA, 'while the gated run, right by EVAL.md, has not acted yet', 'while the gated run is right', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner drops the verdict', ARENA, `<span data-source="README.md">EVAL.md's verdict on it is Rethink: the arena's claim did not hold on these seeds.</span> `, '', 'pair.spec.js', '5:1', BANNER),
  m('pair: the banner drops the link to the table', ARENA, '<a href="https://github.com/SharminSirajudeen/control-gate#readme">README</a>', 'README', 'pair.spec.js', '5:1', BANNER),
  m('pair: the intro drops what the gated agent was shown', ARENA, "The gated agent is shown that test's labels and advice. ", '', 'pair.spec.js', '37:1', SHOWN),
  m('pair: the intro drops what the baseline agent was shown', ARENA, `<span data-source="README.md">returns only each element's mean displacement per action, with no p, no label and no advice</span>`, 'returns the control test\'s labels', 'pair.spec.js', '37:1', SHOWN),
  m('pair: the baseline pane plays the gated log', JS, PANE('baseline', 'baseline'), PANE('gated', 'baseline'), 'pair.spec.js', '23:1', OWN),
  m('pair: the gated pane plays the baseline clip', JS, PANE('gated', 'gated'), PANE('gated', 'baseline'), 'pair.spec.js', '23:1', OWN),
  m('pair: a pane is named from its log', JS, "pane.querySelector('h2').textContent = log.condition;", "pane.querySelector('h2').textContent = log.outcome;", 'pair.spec.js', '23:1', OWN),
  m('pair: a pane names its seed', JS, 'seed ${log.scenario.seed}', 'seed ${log.scenario.case}', 'pair.spec.js', '23:1', OWN),
  m('pair: a pane names its case', JS, '${log.scenario.case}, outcome', '${log.scenario.seed}, outcome', 'pair.spec.js', '23:1', OWN),
  m('pair: a pane names how its run ended', JS, 'outcome ${log.outcome}', 'outcome ${log.condition}', 'pair.spec.js', '23:1', OWN),
  m("clip: the frame counts from the clip's first frame", JS, '(video.currentTime - t0) * FPS', 'video.currentTime * FPS', 'pair.spec.js', '44:1', FIRST),
  m("clip: the first frame's time is read once the clip has loaded", JS, 't0 = video.currentTime;', 't0 = 0;', 'pair.spec.js', '44:1', FIRST),
  // Label placement (web/tests/place.spec.js): on the real pair, the synthetic episode and a hand-built crowd, at two widths.
  m('labels: a label is pushed in from the sides of the canvas', JS, 'x: inside(px - w / 2, w, width)', 'x: px - w / 2', 'place.spec.js', '33:5', PLACE(390, 'the real pair')),
  m('labels: a label is pushed up from the bottom of the canvas', JS, 'y: inside(cy, LABEL_H, height)', 'y: cy', 'place.spec.js', '33:5', PLACE(390, 'a crowd of tracks')),
  m('labels: a label that would touch another goes below its box', JS, 'above >= 0 ? [above, below] : [below]', 'above >= 0 ? [above] : [below]', 'place.spec.js', '33:5', PLACE(390, 'a crowd of tracks')),
  m('labels: a label with no free place is drawn anyway', JS, '.find((r) => !placed.some((p) => touches(p, r)));', '.find((r) => !placed.some((p) => touches(p, r))) ?? at(below);', 'place.spec.js', '33:5', PLACE(390, 'the real pair')),
  m('labels: placed in track order', JS, '.sort((a, b) => a.id - b.id)', '.sort((a, b) => b.id - a.id)', 'place.spec.js', '33:5', PLACE(390, 'a crowd of tracks')),
  m('labels: the intro drops what happens to a label with no place', ARENA, '; a label with no free place is left off the picture, and the list under each pane names every track', '', 'place.spec.js', '59:1', INTRO),
];
