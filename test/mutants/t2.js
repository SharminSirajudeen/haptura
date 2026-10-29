// T2: S4 to S8, the API edge. Each break is the one a reviewer would try first.
const PYTEST = 'uv run --locked python -m pytest -q tests/test_meta_api.py';
const T = 'tests/test_meta_api.py';
const m = (from, file, find, replace, test) => ({ from, file, find, replace, mustFail:T, expect:`FAILED ${T}::${test}`, cmd:PYTEST });
module.exports = [
  m('S5: key read from META_API_KEY', 'gate/meta_api.py', 'os.environ["META_API_KEY"]', 'os.environ.get("META_API_KEY", os.environ.get("MODEL_API_KEY", ""))', 'test_the_key_comes_from_meta_api_key'),
  m('S5: the Meta base URL', 'gate/meta_api.py', 'BASE_URL = "https://api.meta.ai/v1"', 'BASE_URL = "https://api.meta.ai"', 'test_posts_the_body_to_the_meta_url_with_the_key'),
  m('S5: streamed events parsed in order', 'gate/meta_api.py', 'return (cast(dict[str, Any], e) for e in events)', 'return (cast(dict[str, Any], e) for e in reversed(list(events)))', 'test_stream_yields_each_event_in_order_and_stops_at_done'),
  m('S6: a hit is read from disk', 'gate/meta_api.py', '    if path.exists():\n        return json.loads(path.read_text())\n', '', 'test_cache_hit_returns_the_file_without_calling_fn'),
  m('S6: REPLAY makes a miss an error', 'gate/meta_api.py', '    if os.environ.get("REPLAY") == "1":\n        raise LookupError(f"REPLAY=1 and no cached response for {key}")\n', '', 'test_replay_makes_a_miss_an_error'),
  m('S6: a miss is stored', 'gate/meta_api.py', '    path.write_text(json.dumps(value))\n', '', 'test_cache_miss_calls_fn_once_and_stores_it'),
  m('S6: parts are length-prefixed', 'gate/meta_api.py', '        h.update(f"{len(b)}:".encode())\n', '', 'test_cache_key_separates_the_parts'),
  m('S7: frame index from the marker', 'gate/meta_api.py', '        frame = int(marker.group(1))\n', '        frame = lines.index(line)\n', 'test_parse_tracks_reads_the_frame_marker_and_leaves_nan_gaps'),
  m('S7: absent frames are NaN', 'gate/meta_api.py', 'np.full((n_frames, 2), np.nan)', 'np.zeros((n_frames, 2))', 'test_parse_tracks_reads_the_frame_marker_and_leaves_nan_gaps'),
  m('S7: the box centre, not its corner', 'gate/meta_api.py', 'track[frame] = ((int(x1) + int(x2)) / 2, (int(y1) + int(y2)) / 2)', 'track[frame] = (int(x1), int(y1))', 'test_sam_track_replays_the_recorded_red_objects'),
  m('S7: a line without a marker is a defect', 'gate/meta_api.py', '        if marker is None:\n            raise ValueError(f"SAM line without a frame marker: {line[:60]!r}")\n', '        if marker is None:\n            continue\n', 'test_parse_tracks_rejects_a_line_without_a_frame_marker'),
  m('S8: previous_response_id sent', 'gate/meta_api.py', '    if previous_response_id is not None:\n        body["previous_response_id"] = previous_response_id\n', '', 'test_muse_turn_sends_the_follow_up_with_previous_response_id'),
  m('S8: tool arguments decoded from JSON', 'gate/meta_api.py', 'ToolCall(o["name"], _arguments(o["arguments"]), o["call_id"])', 'ToolCall(o["name"], {"raw": o["arguments"]}, o["call_id"])', 'test_muse_turn_replays_the_recorded_first_turn'),
  m('S4: H.264, the codec SAM accepts', 'gate/video.py', 'libx264', 'mpeg4', 'test_encode_mp4_gives_h264_at_the_frame_size_and_rate'),
];
