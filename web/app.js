'use strict';
// The demo page. Each pane is a <video> with a <canvas> over it. The panes read an EpisodeLog (gate/types.py,
// written by to_json) and, for the frame the video shows, draw every tracked element with what the agent believes.

const FPS = 10; // gate/constants.py FPS; web/tests/labels.spec.js fails when the two differ
const BOX = 12; // overlay box in video pixels; an element is ELEMENT_PX = 8 wide
const EPS = 1e-6; // a time on a frame boundary must not round down to the frame before
const PANES = [
  { title: 'baseline', log: 'fixtures/episode.json', clip: 'fixtures/clip.mp4' },
  { title: 'gated', log: 'fixtures/episode.json', clip: 'fixtures/clip.mp4' },
];

const UNSURE = 'unsure, checking';
const VERDICT = { mine: 'mine', echo: 'not me', not_me: 'not me' }; // by Evidence.label
const FIX = {
  // by Diagnosis.kind; `ok` and `stale` have no line in the plan
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

function mark(ctx, width, k, { pt: [x, y], label }) {
  const half = (BOX * k) / 2;
  const px = x * k;
  const py = y * k;
  ctx.strokeStyle = COLOUR[label];
  ctx.strokeRect(px - half, py - half, 2 * half, 2 * half);
  const w = ctx.measureText(label).width + 8;
  const cx = Math.min(Math.max(px - w / 2, 0), width - w);
  const cy = py - half - 20 >= 0 ? py - half - 20 : py + half + 4;
  ctx.fillStyle = COLOUR[label];
  ctx.fillRect(cx, cy, w, 16);
  ctx.fillStyle = '#111';
  ctx.fillText(label, cx + 4, cy + 12);
}

function draw(canvas, video, items) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = video.clientWidth * dpr; // resizing the canvas also clears it
  canvas.height = video.clientHeight * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.lineWidth = 2;
  ctx.font = '600 12px system-ui, sans-serif';
  const k = video.clientWidth / video.videoWidth; // CSS pixels per video pixel; the clips are square
  items.filter((it) => it.pt[0] !== null).forEach((it) => mark(ctx, video.clientWidth, k, it));
}

function show(pane, log, starts) {
  const video = pane.querySelector('video');
  if (!video.videoWidth) return; // no frame yet
  const frame = Math.floor(video.currentTime * FPS + EPS);
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
  draw(pane.querySelector('canvas'), video, items);
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

async function mount({ title, log: logUrl, clip }) {
  const pane = document.getElementById('pane').content.firstElementChild.cloneNode(true);
  const video = pane.querySelector('video');
  pane.querySelector('h3').textContent = title;
  document.querySelector('.panes').append(pane);
  video.src = clip;
  controls(pane, video);
  const log = await (await fetch(logUrl)).json();
  const starts = startsOf(log.blocks);
  const render = () => show(pane, log, starts);
  const onFrame = () => { render(); video.requestVideoFrameCallback(onFrame); };
  video.requestVideoFrameCallback(onFrame); // every frame shown while it plays
  // A frame can be shown before a callback is registered (under parallel test load a pane was seen never drawing), so
  // the first draw does not wait for one: it happens now if the video has a frame, and when it gets one if it has not.
  ['loadeddata', 'seeked'].forEach((event) => video.addEventListener(event, render));
  new ResizeObserver(render).observe(video);
  render();
}

PANES.forEach(mount);
