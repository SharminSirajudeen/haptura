// Issue #58's lab records (phone/lab.py, results/phone/lab): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const T = 'tests/test_phone_lab.py';
const m = (from, find, replace, test) =>
  ({ from, file:'phone/lab.py', find, replace, mustFail:T, cmd:`${PY} ${T}`, expect:`FAILED ${T}::${test}` });
module.exports = [
  m('lab: the allowlist is empty', 'NONE: frozenset[str] = frozenset()', 'NONE: frozenset[str] = frozenset({KEYBOARD})',
    'test_every_verdict_recomputes_from_its_saved_dump'),
  m('lab: a field showing its hint reads empty', 'return "" if text == el.get("hint") else text', 'return text',
    'test_the_field_reads_empty_when_it_shows_its_hint'),
];
