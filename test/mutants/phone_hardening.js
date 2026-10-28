// Fixes from the 28 Oct security review of the phone gate (Mac session): one entry per guarded line.
const PY = 'uv run --locked python -m pytest -q';
const m = (from, file, find, replace, test) =>
  ({ from, file, find, replace, mustFail:test.split('::')[0], cmd:`${PY} ${test.split('::')[0]}`, expect:`FAILED ${test}` });
module.exports = [
  m('muse: an infinite coordinate is unknown, not a crash', 'phone/muse.py',
    '    except (ValueError, OverflowError):', '    except ValueError:',
    'tests/test_phone_muse.py::test_an_infinite_coordinate_is_unknown_not_a_crash'),
  m('muse: a failed call records its class, never its text', 'phone/muse.py',
    '    return f"{type(e).__name__} {status}" if status else type(e).__name__\n', '    return str(e)\n',
    'tests/test_phone_muse.py::test_an_error_records_its_class_never_its_text'),
  m('ui: an empty or cut dump has no nodes', 'phone/ui.py',
    '    except ET.ParseError:\n        return []\n', '    except ET.ParseError:\n        raise\n',
    'tests/test_phone_ui.py::test_an_empty_or_cut_dump_has_no_nodes'),
];
module.exports.push(
  m('rules: an empty owner never equals an empty task app', 'phone/rules.py',
    '    if owner == task_pkg != "":', '    if owner == task_pkg:',
    'tests/test_phone_rules.py::test_an_unknown_task_app_allows_nothing'),
  m('rules: no allowlisted window without a task app', 'phone/rules.py',
    '    if owner in allow and task_pkg:\n', '    if owner in allow:\n',
    'tests/test_phone_rules.py::test_an_unknown_task_app_allows_nothing'),
);
