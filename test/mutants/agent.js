// The agent loop and executor. Each break is the one a reviewer would try first on that line.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_agent.py';
const T = 'tests/test_agent.py', A = 'gate/agent.py';
const m = (from, find, replace, test) => ({ from, file:A, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
const REFUSE = 'test_gated_refuses_an_unsupported_act_and_ungated_runs_it';
const TRANSCRIPT = 'test_the_conversation_is_carried_as_the_transcript_of_items';
const EYES = 'test_an_eyes_swap_is_corrected_without_a_muse_turn';
const BODY = 'test_a_body_remap_ends_in_body_changed_with_the_new_map_and_the_goal_reached';
const LOST = 'test_a_control_remap_ends_in_target_lost_with_the_advice_to_reprobe';
const EYES_FIRST = 'test_the_eyes_fix_comes_before_the_goal_check';
const TIE = 'test_a_tie_on_the_last_frame_is_told_apart_along_the_targets_own_track';
const HELD = 'test_a_tie_held_through_the_whole_block_is_not_control';
const SWAPTIE = 'test_after_an_eyes_fix_a_tie_is_walked_along_the_track_the_fix_gave_the_target';
const UNSEEN = 'test_a_target_unseen_on_the_last_frame_is_matched_where_it_was_last_seen';
module.exports = [
  { from:'S15: the goal centre, not its corner (the line Muse is told, and the steering aim)', file:'gate/gate.py', find:'return ((goal[0] + goal[2]) / 2, (goal[1] + goal[3]) / 2)', replace:'return (goal[0], goal[1])', mustFail:T, expect:`FAILED ${T}::${LOST}`, cmd:PYTEST },
  m('tie: a tie is walked back one frame at a time', '        if len(near) == 1:\n            break\n', '        break\n', TIE),
  m('tie: the walk follows the track that ends on the target', 'if _last(t) == pos]', 'if False]', TIE),
  m('tie: the target\'s own track first when two end on its pixel', 'sorted(last.tracks.items(), key=lambda it: it[0] != own)', 'last.tracks.items()', TIE),
  m('tie: after an eyes fix the walk follows the track the diagnosis gave the target', 'own = fix[1 - fix.index(target)] if fix and target in fix else target', 'own = target', SWAPTIE),
  m('tie: an unseen frame is skipped, not matched', '        if not np.isnan(seen).any():\n', '        if True:\n', UNSEEN),
  m('tie: the walk is not capped', '(ends[0] if ends else np.array([pos]))[::-1]', '(ends[0] if ends else np.array([pos]))[::-1][:2]', TIE),
  m('tie: a tie that lasts the block is not control', 'return near == {arena._at(arena.scenario.binding_schedule)}', 'return arena._at(arena.scenario.binding_schedule) in near', HELD),
  m('agent: a gated act goes through check_act', 'check_act(run.evidence, object_id) if run.gated else', 'Decision("act", object_id, said) if run.gated else', REFUSE),
  m('agent: an ungated act skips check_act', 'if run.gated else Decision("act", object_id, said)', 'if True else Decision("act", object_id, said)', REFUSE),
  m('agent: an ungated act runs no diagnosis', 'found = run.diagnose(body, actions, tracks, target, None) if run.gated else None', 'found = run.diagnose(body, actions, tracks, target, None)', LOST),
  m('agent: the ungated table has no p0 or label', 'test = f" {e.p0:.2g} {e.label}" if gated else ""', 'test = f" {e.p0:.2g} {e.label}"', REFUSE),
  m('agent: the gated table ends with the advice line', 'tail = [] if advice is None else [_say(advice)]', 'tail: list[str] = []', LOST),
  m('agent: Muse\'s first call after a block is the one logged', 'if run.blocks and run.blocks[-1].phase == "probe" and run.blocks[-1].decision is None:', 'if run.blocks and run.blocks[-1].phase == "probe":', REFUSE),
  m('agent: n is clamped to BLOCK_STEPS', 'min(n, BLOCK_STEPS)', 'n', REFUSE),
  m('agent: model arguments are checked', ' or not all(d in DIRS for d in dirs)', '', 'test_bad_arguments_are_answered_and_run_nothing'),
  m('agent: nested arguments are answered, not raised', ' or not all(d in DIRS for d in dirs)', ' or not set(dirs) <= set(DIRS)', 'test_nested_direction_arguments_are_answered_not_raised'),
  m('agent: the conversation is carried as the transcript', 'transcript = [*transcript, *reply.items, *_answer(run, reply)]', 'transcript = [*reply.items, *_answer(run, reply)]', TRANSCRIPT),
  m('agent: a reply\'s items are carried back', 'transcript = [*transcript, *reply.items, *_answer(run, reply)]', 'transcript = [*transcript, *_answer(run, reply)]', TRANSCRIPT),
  m('agent: the task opens the conversation as a user message', 'transcript = [_user(_task(scenario.goal))]', 'transcript = [_user("")]', TRANSCRIPT),
  m('agent: a user message is an input_text item', '"content": [{"type": "input_text", "text": text}]', '"content": [{"type": "text", "text": text}]', TRANSCRIPT),
  m('agent: a reply with no tool call is nudged', 'return [_user(NUDGE)]', 'return []', 'test_a_reply_with_no_tool_call_is_nudged_with_a_user_message'),
  m('agent: every call of a reply is answered', '    return outputs\n', '    return outputs[:1]\n', 'test_a_reply_with_two_calls_is_answered_call_by_call_in_order'),
  m('agent: usage adds every turn', 'total["input_tokens"] += usage.get("input_tokens", 0)', 'total["input_tokens"] = usage.get("input_tokens", 0)', REFUSE),
  m('agent: MAX_MUSE_CALLS turns, not one more', 'for _ in range(MAX_MUSE_CALLS):', 'for _ in range(MAX_MUSE_CALLS + 1):', 'test_muse_turns_stop_at_max_muse_calls'),
  m('agent: MAX_FRAMES is reachable, not a bar below it', 'if run.frames + len(actions) + 1 > MAX_FRAMES:', 'if run.frames + len(actions) + 1 >= MAX_FRAMES:', 'test_frames_stop_at_max_frames'),
  m('agent: act blocks run on the acting clock', 'run.tracker, phase == "act", clip)', 'run.tracker, False, clip)', BODY),
  m('agent: the eyes fix swaps the ids back', '            run.reference[a], run.reference[b] = run.reference[b], run.reference[a]\n', '', EYES),
  m('agent: the eyes fix takes no Muse turn', 'elif _act_block(run, target, body, live) == "stale":', 'elif _act_block(run, target, body, live) in ("stale", "eyes_swapped"):', EYES),
  m('agent: a stale block runs the diagnostic probe', '            return _probe(run, target, body)\n', '            return "stale"\n', BODY),
  m('agent: the pool restarts at the diagnosis', '    run.pool = [(actions, tracks)]\n', '    run.pool.append((actions, tracks))\n', LOST),
  m('agent: body_changed advises acting, target_lost probing',
    '    if found.kind == "body_changed":\n        advice = Decision("act", target, found.fix)\n    else:\n        advice = Decision("probe", None, found.fix)\n',
    '    if found.kind == "body_changed":\n        advice = Decision("probe", None, found.fix)\n    else:\n        advice = Decision("act", target, found.fix)\n', BODY),
  m('agent: the probe has as many no-ops as each direction', '1 / (len(DIRS) + 1)', '0.3', BODY),
  m('agent: a false act is judged at every act block', '        if not _controls(run, target):\n', '        if run.blocks[-1].phase != "act" and not _controls(run, target):\n', LOST),
  m('agent: a tracked success must be the true one', '        if not _controls(run, target):\n            run.outcome = "false_act"\n        elif _in_goal(run.reference[target], goal):\n            run.outcome = "success"\n', '        if _in_goal(run.reference[target], goal):\n            run.outcome = "success"\n        elif not _controls(run, target):\n            run.outcome = "false_act"\n', 'test_a_success_the_tracker_fakes_is_scored_false_act'),
  m('agent: a target already in the goal is judged before it is steered', '        elif _in_goal(run.reference[target], goal):\n            run.outcome = "success"\n        elif not live:', '        elif not live:', 'test_an_act_on_a_target_already_in_the_goal_is_a_success_with_no_act_block'),
  m('agent: steering takes the nearest predicted position', 'a = min(live, key=', 'a = max(live, key=', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('agent: a dead action is not steered with', 'if v is not None and math.hypot(*v) >= EFFECT_MIN}', 'if v is not None}', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('agent: an id a block missed keeps its last position', '    for i, pos in tracks.items():\n        last = _last(pos)\n', '    run.reference.clear()\n    for i, pos in tracks.items():\n        last = _last(pos)\n', 'test_a_target_the_tracker_loses_is_probed_and_handed_back'),
  m('agent: block k\'s clip is clips/kk.mp4', 'f"{len(run.blocks):02d}.mp4"', 'f"{len(run.blocks)}.mp4"', 'test_each_block_saves_its_clip_under_the_name_the_episode_passed'),
  m('agent: no clips directory records no clip', 'path = "" if clip is None else str(clip)', 'path = str(clip)', REFUSE),
  m('agent: the eyes fix comes before the goal check', '    if found is not None:\n        if found.swap is not None:\n', '    if _in_goal(run.reference[target], run.arena.scenario.goal):\n        run.outcome = "success" if _controls(run, target) else "false_act"\n    if found is not None:\n        if found.swap is not None:\n', EYES_FIRST),
  m('agent: the rule policy is given the mine element\'s tracked position', 'pos = run.reference[mine[0].object_id] if len(mine) == 1 else centre(goal)', 'pos = centre(goal)', EYES_FIRST),
  m('agent: the probe table is the diagnosis\' own control test', 'evidence = _look(run, actions, tracks, PROBE_SEED)', 'evidence = _look(run, actions, tracks, PROBE_SEED + 1)', BODY),
  m('agent: each look is seeded by its block index', 'seed = run.arena.scenario.seed * SEED_STRIDE + len(run.blocks) - 1', 'seed = run.arena.scenario.seed * SEED_STRIDE', LOST),
  m('agent: a block takes its N+1 frames from MAX_FRAMES', 'if run.frames + len(actions) + 1 > MAX_FRAMES:', 'if run.frames + len(actions) > MAX_FRAMES:', 'test_frames_stop_at_max_frames'),
  m('agent: cached tokens come from input_tokens_details', '.get("input_tokens_details", {}).get("cached_tokens", 0)', '.get("cached_tokens", 0)', REFUSE),
  m('agent: an effect of exactly EFFECT_MIN is alive', 'math.hypot(*v) >= EFFECT_MIN}', 'math.hypot(*v) > EFFECT_MIN}', 'test_steer_takes_the_live_action_nearest_the_goal_and_skips_a_dead_one'),
  m('agent: an ungated act logs what Muse said', 'Decision("act", object_id, said)', 'Decision("act", object_id, "")', REFUSE),
  m('agent: the prompt stays within the 300-token proxy', '"soon as the evidence is clear. Call one tool per turn."', '"soon as the evidence is clear. Call one tool per turn." + " " * 400', REFUSE),
  m('agent: the shared frame is kept once', 't.get(i, g)[min(k, 1) :]', 't.get(i, g)', 'test_pool_joins_blocks_on_their_shared_frame'),
];
const RULES = 'test_rules_turn_answers_the_advice_line_of_the_last_answer';
module.exports.push(
  m('rules: the last answer decides', 'str(transcript[-1].get("output", ""))', 'str(transcript[0].get("output", ""))', RULES),
  m('rules: no advice is a probe', 'advice.groups() if advice else ("probe", "", "")', 'advice.groups() if advice else ("act", "0", "")', RULES),
  m('rules: act advice becomes an act', '    if kind == "act":\n', '    if kind == "acts":\n', RULES),
  m('rules: decline advice becomes a decline', '    elif kind == "decline":\n', '    elif kind == "declines":\n', RULES),
  m('rules: the probe is a full block', 'RULES_PROBE = {"n": BLOCK_STEPS,', 'RULES_PROBE = {"n": PROBE_STEPS,', RULES),
);
module.exports.push(
  m('rules: a decision carries the rule policy\'s sentence', '    return MuseReply(reason or "no advice yet", (call,), (), {})', '    return MuseReply("rules", (call,), (), {})',
    'test_rules_only_declines_when_nothing_obeys'),
);
