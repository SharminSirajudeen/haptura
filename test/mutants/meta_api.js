// The API edge: encode_mp4, post_json, cached, sam_track and muse_turn. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_meta_api.py';
const T = 'tests/test_meta_api.py';
const SENDS = 'test_muse_turn_sends_the_whole_conversation_as_input_items';
const m = (from, file, find, replace, test) => ({ from, file, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
module.exports = [
  m('post_json: key read from META_API_KEY', 'gate/meta_api.py', 'os.environ["META_API_KEY"]', 'os.environ.get("META_API_KEY", os.environ.get("MODEL_API_KEY", ""))', 'test_the_key_comes_from_meta_api_key'),
  m('post_json: the Meta base URL', 'gate/meta_api.py', 'BASE_URL = "https://api.meta.ai/v1"', 'BASE_URL = "https://api.meta.ai"', 'test_posts_the_body_to_the_meta_url_with_the_key'),
  m('post_json: streamed events parsed in order', 'gate/meta_api.py', 'return (cast(dict[str, Any], e) for e in events)', 'return (cast(dict[str, Any], e) for e in reversed(list(events)))', 'test_stream_yields_each_event_in_order_and_stops_at_done'),
  m('cache: a hit is read from disk', 'gate/meta_api.py', '    if path.exists():\n        return json.loads(path.read_text())\n', '', 'test_cache_hit_returns_the_file_without_calling_fn'),
  m('cache: REPLAY makes a miss an error', 'gate/meta_api.py', '    if os.environ.get("REPLAY") == "1":\n        raise LookupError(f"REPLAY=1 and no cached response for {key}")\n', '', 'test_replay_makes_a_miss_an_error'),
  m('cache: a miss is stored', 'gate/meta_api.py', '    path.write_text(json.dumps(value))\n', '', 'test_cache_miss_calls_fn_once_and_stores_it'),
  m('cache: parts are length-prefixed', 'gate/meta_api.py', '        h.update(f"{len(b)}:".encode())\n', '', 'test_cache_key_separates_the_parts'),
  m('sam_track: frame index from the marker', 'gate/meta_api.py', '        frame = int(marker.group(1))\n', '        frame = lines.index(line)\n', 'test_parse_tracks_reads_the_frame_marker_and_leaves_nan_gaps'),
  m('sam_track: absent frames are NaN', 'gate/meta_api.py', 'np.full((n_frames, 2), np.nan)', 'np.zeros((n_frames, 2))', 'test_parse_tracks_reads_the_frame_marker_and_leaves_nan_gaps'),
  m('sam_track: the box centre, not its corner', 'gate/meta_api.py', 'track[frame] = ((int(x1) + int(x2)) / 2, (int(y1) + int(y2)) / 2)', 'track[frame] = (int(x1), int(y1))', 'test_sam_track_replays_the_recorded_red_objects'),
  m('sam_track: a line without a marker is a defect', 'gate/meta_api.py', '        if marker is None:\n            raise ValueError(f"SAM line without a frame marker: {line[:60]!r}")\n', '        if marker is None:\n            continue\n', 'test_parse_tracks_rejects_a_line_without_a_frame_marker'),
  m('muse_turn: the whole conversation is sent as the input items', 'gate/meta_api.py', '        "input": input,\n', '        "input": input[-1:],\n', SENDS),
  m('muse_turn: no previous_response_id is sent', 'gate/meta_api.py', '        "tools": tools,\n', '        "tools": tools,\n        "previous_response_id": "resp_x",\n', SENDS),
  m('muse_turn: the arena\'s agent is Muse Wonder', 'gate/meta_api.py', 'MUSE_MODEL = "muse-wonder-1.0"', 'MUSE_MODEL = "muse-spark-1.3"', SENDS),
  m('muse_turn: the output cap is 2000 tokens', 'gate/constants.py', 'MUSE_MAX_OUTPUT_TOKENS = 2000', 'MUSE_MAX_OUTPUT_TOKENS = 400', SENDS),
  m('muse_turn: a reply hands back its items but not the reasoning', 'gate/meta_api.py', 'if o["type"] != "reasoning")', 'if True)', 'test_muse_turn_replays_the_recorded_first_turn'),
  m('muse_turn: tool arguments decoded from JSON', 'gate/meta_api.py', 'ToolCall(o["name"], _arguments(o["arguments"]), o["call_id"])', 'ToolCall(o["name"], {"raw": o["arguments"]}, o["call_id"])', 'test_muse_turn_replays_the_recorded_first_turn'),
  m('video: H.264, the codec SAM accepts', 'gate/video.py', 'libx264', 'mpeg4', 'test_encode_mp4_gives_h264_at_the_frame_size_and_rate'),
];
