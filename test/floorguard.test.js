// The guard's own detection, asserted on hand-written diffs: one case per move it claims to catch, plus the tightening
// case that must stay silent. A guard nobody has watched go red is a claim, not a check. Run: node test/floorguard.test.js
'use strict';
const { walk, scan } = require('./floorguard.js');
const { check, done } = require('./check.js')();

// A unified diff, written out by hand so the expected finding is derived from the text and not from the guard itself.
const diff = (lines) => { const d = { added:[], removed:[], deleted:[] }; walk(lines.join('\n'), d); return d; };
const hunk = (file, body) => ['diff --git a/' + file + ' b/' + file, '--- a/' + file, '+++ b/' + file, '@@ -1 +1 @@', ...body];
const found = (lines) => scan(diff(lines)).join(' | ');

check(/a test skipped or narrowed/.test(found(hunk('test/a.test.js', ['+it.skip("x", () => {});']))), 'an added it.skip is caught');
check(/a test skipped or narrowed/.test(found(hunk('test/a.test.js', ['+describe.only("x", () => {});']))), 'an added describe.only is caught');
check(/a checker silenced/.test(found(hunk('src/a.js', ['+// eslint-disable-next-line complexity']))), 'an added eslint-disable is caught');
check(/a checker silenced/.test(found(hunk('src/a.ts', ['+// @ts-ignore']))), 'an added @ts-ignore is caught');
check(/an empty catch/.test(found(hunk('src/a.js', ['+try { f(); } catch (e) {}']))), 'an added empty catch is caught');
check(/a TODO with no issue reference/.test(found(hunk('src/a.js', ['+// TODO tidy this up']))), 'a bare TODO is caught');
check(found(hunk('src/a.js', ['+// TODO #412 tidy this up'])) === '', 'a TODO naming an issue is allowed');
check(/a test file deleted/.test(found(['diff --git a/test/a.test.js b/test/a.test.js', '--- a/test/a.test.js', '+++ /dev/null'])), 'a deleted test file is caught');
check(/a test skipped or narrowed/.test(found(hunk('tests/test_a.py', ['+@pytest.mark.skip(reason="later")']))), 'an added pytest skip is caught');
check(/a known defect left non-strict/.test(found(hunk('tests/test_a.py', ['+@pytest.mark.xfail(reason="#12")']))), 'a non-strict xfail is caught');
check(found(hunk('tests/test_a.py', ['+@pytest.mark.xfail(strict=True, reason="#12")'])) === '', 'a strict xfail is allowed');
check(/a checker silenced/.test(found(hunk('gate/a.py', ['+x = f()  # noqa: E501']))), 'an added noqa is caught');
check(/a checker silenced/.test(found(hunk('gate/a.py', ['+x = f()  # type: ignore']))), 'an added type: ignore is caught');
check(/a test file deleted/.test(found(['diff --git a/tests/test_a.py b/tests/test_a.py', '--- a/tests/test_a.py', '+++ /dev/null'])), 'a deleted pytest file is caught');
check(found(['diff --git a/docs/kit/test/a.test.js b/docs/kit/test/a.test.js', '--- a/docs/kit/test/a.test.js', '+++ /dev/null']) === '',
  'a test file deleted outside the project\'s own paths (a template kept elsewhere) is not a finding');
check(/a lint limit raised/.test(found(hunk('pyproject.toml', ['-max-nested-blocks = 3', '+max-nested-blocks = 4']))), 'a raised nesting limit is caught');
check(found(hunk('pyproject.toml', ['-max-nested-blocks = 4', '+max-nested-blocks = 3'])) === '', 'a lowered nesting limit is silent');
check(/a mutant removed from the list/.test(found(hunk('test/mutants/arena.js', ["-  { from:'area: the product', file:'src/area.js' }"]))), 'a removed mutant entry is caught');
check(found(hunk('docs/plan.md', ['+use `# noqa` only with a reason'])) === '', 'prose in a .md file is not a silenced checker');
check(found(hunk('test/floorguard.js', ['+// eslint-disable-next-line complexity'])) === '', 'the guard does not report its own pattern table');
check(found(hunk('test/floorguard.test.js', ['+it.skip("x", () => {});'])) === '', 'the guard does not report its own test fixtures');
check(found(hunk('test/mutants/arena.js', ["-  { from:'a', file:'x' }", "+  { from:'a', file:'x' },"])) === '', 'a reformatted mutant entry is not a removal');

done(22, n => 'floorguard: all ' + n + ' checks passed');
