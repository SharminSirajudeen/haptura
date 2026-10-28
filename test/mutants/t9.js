// T9: the block runner.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_episode.py';
const T = 'tests/test_episode.py';
const m = (from, find, replace, test) => ({ from, file:'gate/episode.py', find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
module.exports = [
  m('T9: a block opens on the arena as it stands', '    frames = [render(arena)]\n', '    frames = []\n', 'test_two_blocks_of_30_give_62_frames_and_a_61_frame_join'),
  m('T9: the join drops each shared frame once', '*(b[1:] for b in blocks[1:])', '*blocks[1:]', 'test_two_blocks_of_30_give_62_frames_and_a_61_frame_join'),
  m('T9: acting reaches every step', '        arena.step(action, acting)\n', '        arena.step(action, False)\n', 'test_acting_steps_reach_the_schedules'),
  m('T9: the truth slice is the block, not the whole history', 'arena.history[-len(clip) :]', 'arena.history', 'test_truth_slice_tracks_exactly_the_block_frames'),
  m('T9: the clip is written when asked', '        clip_path.write_bytes(encode_mp4(clip))\n', '', 'test_the_clip_is_saved_with_one_frame_per_step'),
];
