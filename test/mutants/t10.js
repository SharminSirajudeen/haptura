// T10: the agent loop and executor. Each break is the one a reviewer would try first on that line.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_agent.py';
const T = 'tests/test_agent.py', A = 'gate/agent.py';
const m = (from, find, replace, test) => ({ from, file:A, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
const REFUSE = 'test_gated_refuses_an_unsupported_act_and_ungated_runs_it';
const EYES = 'test_an_eyes_swap_is_corrected_without_a_muse_turn';
const BODY = 'test_a_body_remap_ends_in_body_changed_with_the_new_map_and_the_goal_reached';
const LOST = 'test_a_control_remap_ends_in_target_lost_with_the_advice_to_reprobe';
const EYES_FIRST = 'test_the_eyes_fix_comes_before_the_goal_check';
module.exports = [
  m('T10: a gated act goes through S13', 'check_act(run.evidence, object_id) if run.gated else', 'Decision("act", object_id, said) if run.gated else', REFUSE),
  m('T10: an ungated act skips S13', 'if run.gated else Decision("act", object_id, said)', 'if True else Decision("act", object_id, said)', REFUSE),
  m('T10: an ungated act runs no S14', 'found = run.diagnose(body, actions, tracks, target, None) if run.gated else None', 'found = run.diagnose(body, actions, tracks, target, None)', LOST),
  m('T10: the ungated table has no p0 or label', 'test = f" {e.p0:.2g} {e.label}" if gated else ""', 'test = f" {e.p0:.2g} {e.label}"', REFUSE),
  m('T10: the gated table ends with the advice line', 'tail = [] if advice is None else [_say(advice)]', 'tail: list[str] = []', LOST),
  m('T10: Muse\'s first call after a block is the one logged', 'if run.blocks and run.blocks[-1].phase == "probe" and run.blocks[-1].decision is None:', 'if run.blocks and run.blocks[-1].phase == "probe":', REFUSE),
  m('T10: n is clamped to BLOCK_STEPS', 'min(n, BLOCK_STEPS)', 'n', REFUSE),
  m('T10: model arguments are checked', ' or not set(dirs) <= set(DIRS)', '', 'test_bad_arguments_are_answered_and_run_nothing'),
  m('T10: the conversation is carried by previous_response_id', 'previous = reply.response_id', 'previous = None', REFUSE),
  m('T10: usage adds every turn', 'total["input_tokens"] += usage.get("input_tokens", 0)', 'total["input_tokens"] = usage.get("input_tokens", 0)', REFUSE),
  m('T10: MAX_MUSE_CALLS turns, not one more', 'for _ in range(MAX_MUSE_CALLS):', 'for _ in range(MAX_MUSE_CALLS + 1):', 'test_muse_turns_stop_at_max_muse_calls'),
  m('T10: MAX_FRAMES is reachable, not a bar below it', 'if run.frames + len(actions) + 1 > MAX_FRAMES:', 'if run.frames + len(actions) + 1 >= MAX_FRAMES:', 'test_frames_stop_at_max_frames'),
  m('T10: act blocks run on the acting clock', 'run.tracker, phase == "act", clip)', 'run.tracker, False, clip)', BODY),
  m('T10: the eyes fix swaps the ids back', '            run.reference[a], run.reference[b] = run.reference[b], run.reference[a]\n', '', EYES),
  m('T10: the eyes fix takes no Muse turn', 'if run.outcome is None and kind == "stale":', 'if run.outcome is None and kind in ("stale", "eyes_swapped"):', EYES),
  m('T10: a stale block runs the diagnostic probe', '            return _probe(run, target, body)\n', '            return "stale"\n', BODY),
  m('T10: the pool restarts at the diagnosis', '    run.pool = [(actions, tracks)]\n', '    run.pool.append((actions, tracks))\n', LOST),
  m('T10: body_changed advises acting, target_lost probing',
    '    if found.kind == "body_changed":\n        advice = Decision("act", target, found.fix)\n    else:\n        advice = Decision("probe", None, found.fix)\n',
    '    if found.kind == "body_changed":\n        advice = Decision("probe", None, found.fix)\n    else:\n        advice = Decision("act", target, found.fix)\n', BODY),
  m('T10: the probe has as many no-ops as each direction', '1 / (len(DIRS) + 1)', '0.3', BODY),
  m('T10: a false act is judged at every act block', '        if not _controls(run, target):\n', '        if run.blocks[-1].phase != "act" and not _controls(run, target):\n', LOST),
  m('T10: a tracked success must be the true one', 'run.outcome = "success" if _controls(run, target) else "false_act"', 'run.outcome = "success"', 'test_a_success_the_tracker_fakes_is_scored_false_act'),
  m('T10: steering takes the nearest predicted position', 'a = min(live, key=', 'a = max(live, key=', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('T10: a dead action is not steered with', 'if v is not None and math.hypot(*v) >= EFFECT_MIN}', 'if v is not None}', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('T10: an id a block missed keeps its last position', '    for i, pos in tracks.items():\n        last = _last(pos)\n', '    run.reference.clear()\n    for i, pos in tracks.items():\n        last = _last(pos)\n', 'test_a_target_the_tracker_loses_is_probed_and_handed_back'),
  m('T10: block k\'s clip is clips/kk.mp4', 'f"{len(run.blocks):02d}.mp4"', 'f"{len(run.blocks)}.mp4"', 'test_each_block_saves_its_clip_under_the_name_the_episode_passed'),
  m('T10: no clips directory records no clip', 'path = "" if clip is None else str(clip)', 'path = str(clip)', REFUSE),
  m('T10: the eyes fix comes before the goal check',
    '    if found is not None:\n        if found.swap is not None:\n            a, b = found.swap\n            run.reference[a], run.reference[b] = run.reference[b], run.reference[a]\n        run.blocks[-1] = replace(run.blocks[-1], diagnosis=found)\n    if _in_goal(run.reference[target], goal):\n        run.outcome = "success" if _controls(run, target) else "false_act"\n',
    '    if _in_goal(run.reference[target], goal):\n        run.outcome = "success" if _controls(run, target) else "false_act"\n    if found is not None:\n        if found.swap is not None:\n            a, b = found.swap\n            run.reference[a], run.reference[b] = run.reference[b], run.reference[a]\n        run.blocks[-1] = replace(run.blocks[-1], diagnosis=found)\n',
    EYES_FIRST),
  m('T10: S15 is given the mine element\'s tracked position', 'pos = run.reference[mine[0].object_id] if len(mine) == 1 else centre(goal)', 'pos = centre(goal)', EYES_FIRST),
  m('T10: the probe table is S14\'s own S10 call', 'evidence = _look(run, actions, tracks, PROBE_SEED)', 'evidence = _look(run, actions, tracks, PROBE_SEED + 1)', BODY),
  m('T10: each look is seeded by its block index', 'seed = run.arena.scenario.seed * SEED_STRIDE + len(run.blocks) - 1', 'seed = run.arena.scenario.seed * SEED_STRIDE', LOST),
  m('T10: a block takes its N+1 frames from MAX_FRAMES', 'if run.frames + len(actions) + 1 > MAX_FRAMES:', 'if run.frames + len(actions) > MAX_FRAMES:', 'test_frames_stop_at_max_frames'),
  m('T10: cached tokens come from input_tokens_details', '.get("input_tokens_details", {}).get("cached_tokens", 0)', '.get("cached_tokens", 0)', REFUSE),
  m('T10: an effect of exactly EFFECT_MIN is alive', 'math.hypot(*v) >= EFFECT_MIN}', 'math.hypot(*v) > EFFECT_MIN}', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('T10: an ungated act logs what Muse said', 'Decision("act", object_id, said)', 'Decision("act", object_id, "")', REFUSE),
  m('T10: the prompt stays within the 300-token proxy', '"soon as the evidence is clear. Call one tool per turn."', '"soon as the evidence is clear. Call one tool per turn." + " " * 400', REFUSE),
  m('T10: the shared frame is kept once', 't.get(i, g)[min(k, 1) :]', 't.get(i, g)', 'test_pool_joins_blocks_on_their_shared_frame'),
];
