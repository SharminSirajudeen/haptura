'use strict';
// The demo page. Each pane is a <video> with a <canvas> over it. The panes read an EpisodeLog (gate/types.py,
// written by to_json) and, for the frame the video shows, draw every tracked element with what the agent believes.

const FPS = 10; // gate/constants.py FPS; web/tests/labels.spec.js fails when the two differ
const BOX = 12; // overlay box in video pixels; an element is ELEMENT_PX = 8 wide
const EPS = 1e-6; // a time on a frame boundary must not round down to the frame before
// The kill-test pair gate.demo wrote to web/episodes/: the baseline run, then the gated run. Each pane is named from its log.
const PANES = [
  { log: 'episodes/baseline.json', clip: 'episodes/baseline.mp4' },
  { log: 'episodes/gated.json', clip: 'episodes/gated.mp4' },
];

const UNSURE = 'unsure, checking';
const VERDICT = { mine: 'mine', echo: 'not me', not_me: 'not me' }; // by Evidence.label
const FIX = {
  // by Diagnosis.kind; `ok` and `stale` have no line
  body_changed: 'my controls changed, relearning',
  eyes_swapped: 'my eyes swapped two objects, corrected',
  target_lost: 'control moved, re-probing',
};
const DECLINE = "I can't do this, declining";
const COLOUR = { [UNSURE]: '#e0a100', mine: '#1fa856', 'not me': '#e04b4b' };

// Block k starts where the actions of the blocks before it end. The clip is the block clips joined on their shared
// frame, so one step is one frame and block k's first frame is video frame starts[k].
const startsOf = (blocks) => blocks.map((_, k) => blocks.slice(0, k).reduce((s, b) => s + b.actions.length, 0));

// What the agent knows about element `id` while block `b` plays: the latest evidence at or before the block. A probe
// that has not shown the element to be mine is still checking; an act block has decided.
function labelFor(blocks, b, id) {
  const ev = blocks.slice(0, b + 1).reverse().flatMap((k) => k.evidence).find((e) => e.object_id === id);
  if (!ev || (blocks[b].phase === 'probe' && ev.label === 'not_me')) return UNSURE;
  return VERDICT[ev.label];
}

const status = (block) =>
  [FIX[block.diagnosis?.kind], block.decision?.kind === 'decline' && DECLINE].filter(Boolean).join(' · ');

const say = (name, d) => (d ? `${name}: ${d.kind}${d.object_id === null ? '' : ` ${d.object_id}`}, ${d.reason}` : '');

function itemsAt(blocks, starts, frame) {
  const b = Math.max(0, starts.findLastIndex((s) => s <= frame));
  const i = frame - starts[b];
  const items = Object.entries(blocks[b].tracks).map(([key, pts]) => ({
    id: Number(key),
    pt: pts[Math.min(i, pts.length - 1)],
    label: labelFor(blocks, b, Number(key)),
  }));
  return { b, items };
}

const LABEL_H = 16; // a label is this tall, in CSS pixels, and its text's width plus 8 wide
const inside = (v, size, limit) => Math.min(Math.max(v, 0), limit - size); // v, moved so that `size` fits wholly in [0, limit]
const touches = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

// An element's box, then its label, in track order. The label goes above the box (below it where there is no room above),
// is moved below when above would touch a label already placed, and is left off the picture when below would too: the list
// under the pane names every track. A label is always wholly on the canvas. `placed` gathers the rectangles drawn.
function mark(ctx, [width, height], k, { id, pt: [x, y], label }, placed) {
  const half = (BOX * k) / 2;
  const px = x * k;
  const py = y * k;
  ctx.strokeStyle = COLOUR[label];
  ctx.strokeRect(px - half, py - half, 2 * half, 2 * half);
  const w = ctx.measureText(label).width + 8;
  const at = (cy) => ({ id, x: inside(px - w / 2, w, width), y: inside(cy, LABEL_H, height), w, h: LABEL_H });
  const above = py - half - 20;
  const below = py + half + 4;
  const spot = (above >= 0 ? [above, below] : [below]).map(at).find((r) => !placed.some((p) => touches(p, r)));
  if (!spot) return;
  placed.push(spot);
  ctx.fillStyle = COLOUR[label];
  ctx.fillRect(spot.x, spot.y, w, LABEL_H);
  ctx.fillStyle = '#111';
  ctx.fillText(label, spot.x + 4, spot.y + 12);
}

function draw(canvas, video, items) {
  const dpr = window.devicePixelRatio || 1;
  const { clientWidth: width, clientHeight: height } = video;
  canvas.width = width * dpr; // resizing the canvas also clears it
  canvas.height = height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.lineWidth = 2;
  ctx.font = '600 12px system-ui, sans-serif';
  const k = width / video.videoWidth; // CSS pixels per video pixel; the clips are square
  const placed = [];
  items.filter((it) => it.pt[0] !== null).sort((a, b) => a.id - b.id).forEach((it) => mark(ctx, [width, height], k, it, placed));
  return placed;
}

function show(pane, log, starts, t0) {
  const video = pane.querySelector('video');
  if (!video.videoWidth) return; // no frame yet
  const frame = Math.floor((video.currentTime - t0) * FPS + EPS);
  const { b, items } = itemsAt(log.blocks, starts, frame);
  const block = log.blocks[b];
  const put = (sel, text) => { pane.querySelector(sel).textContent = text; };
  put('.where', `block ${b + 1} of ${log.blocks.length}, ${block.phase}`);
  put('.fix', status(block));
  put('.advice', say('gate advice', block.advice));
  put('.decision', say('decision', block.decision));
  pane.querySelector('.labels').replaceChildren(
    ...items.map(({ id, label }) => Object.assign(document.createElement('li'), { textContent: `track ${id}: ${label}` })),
  );
  const canvas = pane.querySelector('canvas');
  canvas.dataset.labels = JSON.stringify({ frame, start: t0, rects: draw(canvas, video, items) }); // what was drawn, for the specs
  pane.dataset.ready = '';
}

// The controls sit below the clip, so nothing the browser draws covers the labels at its bottom edge.
function controls(pane, video) {
  const play = pane.querySelector('.play'), scrub = pane.querySelector('.scrub');
  play.addEventListener('click', () => (video.paused ? video.play() : video.pause()));
  video.addEventListener('play', () => { play.textContent = 'Pause'; });
  video.addEventListener('pause', () => { play.textContent = 'Play'; });
  video.addEventListener('loadedmetadata', () => { scrub.max = String(video.duration); });
  video.addEventListener('timeupdate', () => { scrub.value = String(video.currentTime); });
  scrub.addEventListener('input', () => { video.currentTime = Number(scrub.value); });
}

async function mount({ log: logUrl, clip }) {
  const pane = document.getElementById('pane').content.firstElementChild.cloneNode(true);
  const video = pane.querySelector('video');
  document.querySelector('main').append(pane);
  // The media time of the clip's first frame, where the browser starts it: an encoder that reorders frames puts it after 0.
  let t0 = 0;
  video.addEventListener('loadeddata', () => { t0 = video.currentTime; }, { once: true });
  video.src = clip;
  controls(pane, video);
  const log = await (await fetch(logUrl)).json();
  pane.querySelector('h2').textContent = log.condition;
  pane.querySelector('.tag').textContent = `kill test, seed ${log.scenario.seed}, ${log.scenario.case}, outcome ${log.outcome}`;
  const starts = startsOf(log.blocks);
  const render = () => show(pane, log, starts, t0);
  const onFrame = () => { render(); video.requestVideoFrameCallback(onFrame); };
  video.requestVideoFrameCallback(onFrame); // every frame shown while it plays
  // A frame can be shown before a callback is registered (under parallel test load a pane was seen never drawing), so
  // the first draw does not wait for one: it happens now if the video has a frame, and when it gets one if it has not.
  ['loadeddata', 'seeked'].forEach((event) => video.addEventListener(event, render));
  new ResizeObserver(render).observe(video);
  render();
}

PANES.forEach(mount);
