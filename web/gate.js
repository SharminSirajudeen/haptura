'use strict';
// Try the gate (index.html#try). A tap on a recorded screen is judged here, in the browser: phone/windows.py and
// phone/rules.py, fetched from this site as the phone runs them, run through Pyodide (web/vendor/pyodide/, from this
// site, loaded on the first tap) on the `dumpsys input` that screen's touch was judged with and that run's uid map
// (web/captures/*.json, built by phone/captures.py). Beside the screen: the verdict, the window the touch reaches, and
// what a check of the focused window would have said instead.

const SOURCE = ['phone/windows.py', 'phone/rules.py'];
// The runner's own calls (phone/ghostei.py::tap_gated: windows.owner_at, windows.focus_owner, rules.check_tap) on one dump.
const JUDGE = `
import json
from phone import rules, windows

def judge(args):
    a = json.loads(args)
    uids, allow, task = windows.packages_by_uid(a["uids"]), frozenset(a["allow"]), a["task"]
    w, owner = windows.owner_at(a["dump"], uids, allow, task, a["x"], a["y"])
    focus = windows.focus_owner(a["dump"], uids, allow, task)
    return json.dumps({
        "receiver": [w.uid, w.name] if w else None,
        "verdict": rules.check_tap(owner, task, allow).__dict__,
        "focus": {"owner": focus, "kind": rules.check_tap(focus, task, allow).kind},
    })
`;

const PROMPT = document.querySelector('#try .status')?.textContent ?? ''; // the lead-in to the buttons, restored after a verdict
const sayAll = (s) => document.querySelectorAll('#try .status').forEach((el) => { el.textContent = s; });
const fetched = (url) => fetch(url).then((r) => (r.ok ? r : Promise.reject(new Error(`${url}: ${r.status}`))));
const failed = (forget) => (e) => { forget(); return { error: e }; }; // a load that failed is forgotten, so the next tap tries again

async function load() {
  sayAll('Loading the gate: Python in your browser, 13.5 MB, once.');
  const [{ loadPyodide }, ...files] = await Promise.all([import('./vendor/pyodide/pyodide.mjs'), ...SOURCE.map((f) => fetched(f).then((r) => r.text()))]);
  const py = await loadPyodide({ indexURL: new URL('vendor/pyodide/', document.baseURI).href });
  py.FS.mkdir('/home/pyodide/phone');
  py.FS.writeFile('/home/pyodide/phone/__init__.py', '');
  SOURCE.forEach((f, i) => py.FS.writeFile(`/home/pyodide/${f}`, files[i]));
  py.runPython('import sys; sys.path.insert(0, "/home/pyodide")');
  py.runPython(JUDGE);
  return { judge: py.globals.get('judge') };
}

let loading; // the one runtime, shared by both screens, started on the first tap
function gate() {
  loading ??= load().catch(failed(() => { loading = undefined; }));
  return loading;
}

const captures = {}; // by file, fetched on a screen's first tap
function capture(fig) {
  const k = fig.dataset.capture;
  return (captures[k] ??= fetched(k).then((r) => r.json()).catch(failed(() => { delete captures[k]; })));
}
const recorded = (cap) => [cap.touch.x, cap.touch.y];

function show(fig, cap, [x, y], r) {
  const out = fig.querySelector('.verdict');
  const mark = fig.querySelector('.mark');
  mark.hidden = false;
  mark.style.left = `${(100 * x) / cap.screen[0]}%`;
  mark.style.top = `${(100 * y) / cap.screen[1]}%`;
  out.hidden = false;
  out.dataset.kind = r.verdict.kind;
  out.querySelector('.kind').textContent = r.verdict.kind === 'allow' ? 'Allowed' : 'Blocked';
  out.querySelector('.reason').textContent = r.verdict.reason;
  out.querySelector('.hit').textContent = r.receiver
    ? `The window under (${x}, ${y}): uid ${r.receiver[0]}, ${r.receiver[1]}.`
    : `No window takes a touch at (${x}, ${y}).`;
  out.querySelector('.focus').textContent = `A check of the focused window would say ${r.focus.kind === 'allow' ? 'allowed' : 'blocked'}: that window belongs to ${r.focus.owner || 'no known package'}.`;
}

// Judge one touch on a screen; `at` gives the display point once the capture, with its screen size, is known.
async function tap(fig, at) {
  const [cap, py] = await Promise.all([capture(fig), gate()]);
  sayAll(PROMPT);
  const status = fig.querySelector('.status');
  const error = cap.error || py.error;
  if (error) {
    status.textContent = `The gate could not load (${error.message}); tap again.`;
    return;
  }
  try {
    const [x, y] = at(cap);
    const r = JSON.parse(py.judge(JSON.stringify({ dump: cap.dump, uids: cap.uids, task: cap.task, allow: cap.allow, x, y })));
    show(fig, cap, [x, y], r);
  } catch (e) {
    status.textContent = `The gate could not run (${e.message}).`;
  }
}

for (const fig of document.querySelectorAll('#try figure[data-capture]')) {
  const screen = fig.querySelector('.screen');
  screen.addEventListener('click', (e) => {
    const box = screen.getBoundingClientRect(); // the image fills the button
    const fx = (e.clientX - box.left) / box.width;
    const fy = (e.clientY - box.top) / box.height;
    // a keyboard activation has no point: it taps where the recording did
    tap(fig, (cap) => (e.detail ? [Math.round(fx * cap.screen[0]), Math.round(fy * cap.screen[1])] : recorded(cap)));
  });
  fig.querySelector('.recorded').addEventListener('click', () => tap(fig, recorded));
}
