// Every other check here reads the code as it now stands, so a test can be weakened without one of them noticing: delete
// a test file and nothing runs it, lower a done(N) to match a population that already shrank and check.js agrees, drop an
// entry from mutants.list.js and the runner never misses it. This one reads the DIFF instead, and only ever reports a
// change that LOWERS the bar — tightening is silent, loosening is loud. A diff it could not compute exits 2, never 0.
// Run: node test/floorguard.js [--base <ref>] — part of `npm run gate`.
'use strict';
const { execFileSync } = require('child_process');
const fs = require('fs');

const git = (args) => {
  try { return execFileSync('git', args, { encoding:'utf8', stdio:['ignore','pipe','pipe'] }); }
  catch (e){ return null; }
};
const bail = (why) => {
  console.log('FAIL floorguard could not read the diff: ' + why + ' — a diff that did not run is not a pass');
  process.exit(2);
};

/* The patterns below occur literally in this file, in its own test, which carries one fixture per pattern, and in
   mutants.list.js, which stores the text it breaks. Scanning any of the three reports the guard as its own violation,
   so all three are exempt by path — stated here, where the reason is readable, rather than inline. */
const EXEMPT = /test\/floorguard(\.test)?\.js$|test\/mutants(\.list\.js|\/[^/]+\.js)$|\.md$/;

const LOOSENING = [
  { rule:'a test skipped or narrowed', re:/\b(?:it|test|describe)\.(?:skip|only)\b|\bx(?:it|describe)\(|pytest\.mark\.skip|\bpytest\.skip\(/ },
  { rule:'a known defect left non-strict', re:/\bxfail\((?![^\n]*strict\s*=\s*True)/ },
  { rule:'a checker silenced', re:/eslint-disable|@ts-(?:ignore|nocheck)|jscpd:ignore|istanbul ignore|#\s*noqa|#\s*type:\s*ignore|nosemgrep|pragma:\s*no cover/ },
  { rule:'an empty catch', re:/catch\s*(?:\([^)]*\))?\s*\{\s*\}/ },
  { rule:'a TODO with no issue reference', re:/\bTODO\b(?![^\n]*#\d)/ }
];
const NUMBERS = [
  { rule:'a lint limit raised', re:/max-(?:complexity|nested-blocks|statements)\s*=\s*(\d+)/, worse:(now, was) => now > was }
];

// origin/main when there is one to compare against, else the previous commit. Neither means there is no earlier state,
// and nothing can have been lowered relative to it — that is a clean run, not an unreadable one.
function resolveBase(){
  const i = process.argv.indexOf('--base');
  if (i > -1) return process.argv[i + 1];
  if (git(['rev-parse', '--verify', '-q', 'origin/main'])) return 'origin/main';
  if (git(['rev-parse', '--verify', '-q', 'HEAD^'])) return 'HEAD^';
  return null;
}

// Added and removed lines, plus the files the change deletes outright. Untracked files count as all-added: a new file
// carrying a suppression comment is the same move as adding one to a tracked file.
function readDiff(base){
  const mb = git(['merge-base', base, 'HEAD']);
  if (!mb) bail('no merge base against ' + base);
  const text = git(['diff', '--unified=0', mb.trim(), '--']);
  if (text === null) bail('could not diff against ' + base);
  const list = git(['ls-files', '--others', '--exclude-standard']);
  if (list === null) bail('could not list untracked files');
  const d = { added:[], removed:[], deleted:[] };
  walk(text, d);
  for (const f of list.split('\n').filter(Boolean)) addFile(f, d);
  return d;
}

function addFile(f, d){
  let body = '';
  try { body = fs.readFileSync(f, 'utf8'); } catch (e){ return; }   // a file that vanished mid-run is not a finding
  for (const text of body.split('\n')) d.added.push({ file:f, text });
}

/* `---` and `+++` name a file only between a `diff` line and that file's first `@@` hunk; inside a hunk they are content,
   so an added `+++i` is a change, not a header. A deletion's new name is /dev/null, so the old name is kept. */
function walk(text, d){
  let file = '', old = '', header = false;
  for (const line of text.split('\n')){
    if (line.startsWith('diff ')) header = true;
    else if (line.startsWith('@@')) header = false;
    else if (header) [file, old] = heading(line, file, old, d);
    else if (line.startsWith('+')) d.added.push({ file, text:line.slice(1) });
    else if (line.startsWith('-')) d.removed.push({ file, text:line.slice(1) });
  }
}

function heading(line, file, old, d){
  const name = (s) => s.replace(/^[ab]\//, '');
  if (line.startsWith('--- ')) return [file, name(line.slice(4))];
  if (!line.startsWith('+++ ')) return [file, old];
  const next = name(line.slice(4));
  if (next !== '/dev/null') return [next, old];
  d.deleted.push(old);
  return [old, old];
}

const nums = (lines, re) => lines.map(l => l.text.match(re)).filter(Boolean).map(m => Number(m[1]));

// A number only counts as lowered when the same file shows the old value leaving and the new value arriving.
function numberFindings(d, out){
  for (const { rule, re, worse } of NUMBERS){
    for (const file of new Set(d.added.map(a => a.file))){
      const was = nums(d.removed.filter(r => r.file === file), re);
      const now = nums(d.added.filter(a => a.file === file), re);
      if (was.length && now.length && worse(Math.min(...now), Math.min(...was)))
        out.push(rule + ' in ' + file + ': ' + Math.min(...was) + ' -> ' + Math.min(...now));
    }
  }
}

/* A line in mutants.list.js changes whenever the entry is reformatted or its `find` text moves, and the old line then
   shows up as removed while the entry is still there. Only a `from:` name that left and did not come back is a removal. */
function mutantsGone(d){
  const names = (lines) => new Set(lines
    .filter(l => /test\/mutants\/[^/]+\.js$/.test(l.file))
    .map(l => l.text.match(/\bfrom:\s*'([^']+)'/))
    .filter(Boolean).map(m => m[1]));
  const kept = names(d.added);
  return [...names(d.removed)].filter(n => !kept.has(n));
}

function scan(d){
  const out = [];
  for (const { file, text } of d.added){
    if (EXEMPT.test(file)) continue;
    for (const { rule, re } of LOOSENING) if (re.test(text)) out.push(rule + ' in ' + file + ': ' + text.trim().slice(0, 90));
  }
  for (const f of d.deleted) if (/\.test\.js$|\.spec\.js$|\/test_[^/]+\.py$|_test\.py$/.test(f)) out.push('a test file deleted: ' + f);
  for (const name of mutantsGone(d)) out.push('a mutant removed from the list: ' + name);
  numberFindings(d, out);
  return out;
}

/* The scan runs on a real diff here and on hand-written diffs in test/floorguard.test.js, which is the second caller
   the export exists for: a guard whose own detection is never asserted is a guard nobody has seen go red. */
module.exports = { walk, scan };

if (require.main === module){
  const base = resolveBase();
  if (!base){ console.log('floorguard: no earlier commit to compare against, nothing could have been lowered'); process.exit(0); }
  const findings = scan(readDiff(base));
  for (const f of findings) console.log('FAIL ' + f);
  console.log(findings.length
    ? findings.length + ' floor violation(s) against ' + base + ': raise the bar back, or say in the change why it moved'
    : 'floorguard: nothing in this change lowers the bar (base ' + base + ')');
  process.exit(findings.length ? 1 : 0);
}
