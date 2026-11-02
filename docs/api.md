# Meta Model API facts, measured 28 Oct 2026, and for Muse Wonder 1 Nov. Every line is from a named page fetched
# that day, or from a call made that day; the probes' raw replies are under `results/api/`.

## Models (`GET /v1/models`, 1.5 s)
`muse-wonder-1.0`, `sam-3.1`, `muse-spark-1.3`, `muse-spark-1.3-contributor`, `muse-spark-1.2`, `muse-spark-1.2-contributor`,
`muse-spark-1.1`, `muse-voice-transcribe-1.0`, `muse-image-1.0`. The SAM id in API calls is **`sam-3.1`** (the model page's
`sam-3-1` is its URL slug).

## Prices and limits (dev.meta.ai/docs/pricing-rate-limits)
| Model | Cached input | Input | Output | RPM | TPM |
|---|---|---|---|---|---|
| `muse-spark-1.3` | $0.15 /M | $1.25 /M | $4.25 /M | 3,000 | 4,000,000 |
| `muse-spark-1.3-contributor` ("used to improve our products") | $0.002 /M | $0.10 /M | $0.20 /M | 150 | 3,000,000 |
| `muse-wonder-1.0` ("in preview", Standard mode only; read 1 Nov) | $0.20 /M | $4.00 /M | $20.00 /M | not recorded | not recorded |
| `sam-3.1` | | $2.50 per 1k images; **$0.20 per 1k video frames, 50-frame minimum per video request** | | 3,000 | none |

Reasoning tokens are billed as output tokens (docs/reasoning). Rate limits are per team.

## SAM 3.1 video (docs/sam/segmenting, docs/sam/reading-segmentation, docs/video-understanding, docs/file-handling)
- `POST /v1/responses`, `model: "sam-3.1"`, `input: [{type: "message", role: "user", content: [{type: "input_text",
  text: "<noun phrase>"}, {type: "input_video", video_url: "<public or base64 data URL>"}]}]`, or
  `{type: "input_video", file_id: "file-..."}` after `POST /v1/files` with `purpose=user_data` (video/mp4; 50 MB inline,
  1 GiB upload). `stream: true` recommended.
- **One concept per request.** "A second `input_text` part segments only one of the concepts." One prompt for all
  shapes works only if one noun phrase matches every shape (probe `sam-2-shape-128` below).
- `metadata: {"mask_encoding": "one_bit"}` (compact, `!` marker) or `lossless` (default, `~`); `include_confidence: "true"`.
- Formats: MP4/MOV with H.264/H.265/MPEG-4; no VP9/WebM. Up to 15,000 frames and **16 tracked objects per frame**.
- **Output:** one `response.output_text.delta` per frame, each one line: a frame marker `<Nf>` (N zero-indexed, **not
  necessarily contiguous or ascending**; frames with no match produce no line), then comma-separated records of
  `object_id <|box;x1=;y1=;x2=;y2=;w=;h=[;c=]|> <|mask;x=0;y=0[;c=];data=H,W,<enc><payload>|>` with a base85 payload.
  Ids are bare integers, stable for an object within a response, possibly sparse. `response.completed` ends the stream.
- **For centroids the box is enough** (the box centre of a circle, square or triangle): `sam_track` parses `<Nf>` and the box
  tokens and skips the mask payload. `meta-sam-parser` (PyPI 0.1.0, 2026-10-06) exists for masks, under Meta's own
  "SAM License" (redistribution under the same terms, a litigation clause): **not used**; box parsing is about 20 lines.

## Muse Spark on the Responses API (docs/tool-calling, docs/reasoning, docs/prompt-caching; probes below)
- Tools are flat: `{type: "function", name, description, parameters}`. A call comes back as an output item
  `{type: "function_call", name, arguments (JSON string), call_id, status}`. The result goes back as
  `input: [{type: "function_call_output", call_id, output}]` with **`previous_response_id`** set (Spark, 28 Oct; Wonder lost
  such a response on 1 Nov, below). `tool_choice` accepts only `"auto"`.
- `reasoning: {effort: "minimal" | "low" | "medium" | "high" | "xhigh" | "max"}` (`"none"` is a 400 for Muse);
  reasoning tokens are in `usage.output_tokens_details.reasoning_tokens`.
- Prompt caching is automatic on the stable token prefix; cached tokens are in `usage.input_tokens_details.cached_tokens`.
- Workshop code (meta-models/legal-agent-workshop) also uses `text={"format":{"type":"json_object"}}` for JSON mode.

## Probe results (2026-10-28; raw JSON in `results/api/`)
### Muse Spark, three calls, about $0.005 in total (2,454 input + 469 output tokens at the prices above)
| Call | Latency | Result | Usage |
|---|---|---|---|
| `muse-1-first-turn`: `instructions` + 3 tools + `temperature: 0` + `reasoning: {effort: "low"}` + `max_output_tokens: 400` | 1.6 s | output items `reasoning, message, function_call`; `run_experiment({"dirs":["up","down","left","right"],"n":40,"p_noop":0.2})` | input 741 (cached 0), output 155 (reasoning 41) |
| `muse-2-follow-up`: `previous_response_id` + `function_call_output` holding a 4-line evidence table with the advice line | 12.2 s | `reasoning, function_call`; `act({"object_id":3})`, following the advice | input 972 (cached 0), output 159 (reasoning 110) |
| `muse-3-repeat-first`: byte-identical repeat of call 1, 10 s later | 1.3 s | the same tool call with the same arguments | input 741, **cached 0** |

So: all four optional parameters are accepted; `temperature: 0` gave identical arguments on the repeat (one sample);
`previous_response_id` carries the state; **no cache hit at 741 input tokens** (the minimum cacheable prefix is not
documented; the 300-token system prompt will not hit either, so no prompt-cache saving is available at these
prompt sizes, and `cached_tokens` stays in the usage report as a check).

### SAM 3.1 video, three calls on the arena-like clip (30 frames, 10 fps, red circle and red square crossing with a
2-frame occlusion, a blue triangle elsewhere), $0.03 in total
| Call | Transport | Result |
|---|---|---|
| `sam-1-circle-128`: 128×128, prompt "circle" | base64 `data:video/mp4` URL, accepted | `response.completed`, **no `output_text.delta` at all: zero matches**; `usage.video_frames_processed: 50` |
| `sam-2-shape-128`: 128×128, prompt "shape" | same | zero matches, 50 frames billed |
| `sam-3-circle-512`: 512×512 (×4 nearest), prompt "circle" | same | zero matches, 50 frames billed |

So the data-URL transport works (3,684-byte MP4, H.264, yuv420p, 2.2–2.5 s per call), **the 50-frame minimum is real
(`video_frames_processed: 50` for a 30-frame clip)**, and SAM found nothing to call a circle or a shape in flat-colour
geometry at either size. The image sweeps below found the phrases SAM does match; the renderer needs no change.

### SAM 3.1 image prompt sweeps on frame 5 of the clip (23 images, $0.06): which noun phrase matches flat shapes?
| Prompt | 512 px | 128 px |
|---|---|---|
| circle, red circle, ball, red ball, dot, red dot, triangle, shape, object | 0 boxes | (red ball: 0) |
| square / red square | 1 box, the square, c=0.62 / 0.86 | |
| **red object** | 2 boxes: the square and the circle, c=0.89 | 2 boxes, c=0.86 |
| **colored object** | | **3 boxes: circle, square and the blue triangle, c≈0.8** |
| coloured shape | | 3 boxes, c≈0.6 |
| red or blue object | | 3 boxes, c≈0.8 |
| blue object | | 1 box, the triangle, c=0.88 |
| small object, bright object, blob, marker, game piece | | 0 |

So SAM 3.1 answers **colour-plus-"object"** phrases on flat geometry and ignores shape nouns except "square". Boxes land
exactly on the drawn shapes (the 8-px circle at frame 5 is x 31–39, y 60–68; its centre was drawn at (35, 64)).

### SAM 3.1 video with a matching prompt (`sam-4`, `sam-5`, $0.02): identity through the occlusion
| Call | Result |
|---|---|
| `sam-4-redobject-128`: 128×128, "red object" | 30 frame lines (0..29, none skipped), ids {0, 1} on every frame. id0 moves 108 → 20 and id1 20 → 107, **both monotone through the overlap at frames 14–15** (f14: id0 (64,64), id1 (60,64); f15: id0 (64,64), id1 (67,66)). 2.6 s. |
| `sam-5-redobject-512`: ×4 upscale, "red object" | the same: 30 frames, ids {0, 1}, both monotone. 3.1 s. |

**So the identities survive a 2-frame full-overlap crossing at 128 px**, confidence 0.85–0.89 on every frame, and
the box centre is within 0.5 px of the drawn centre. 128×128 is enough; no upscaling.

| `sam-6-coloredobject-128`: 128×128, **"colored object"** ($0.01) | 30 frame lines, **ids {0, 1, 2} on every frame**: the square (108 → 20), the circle (20 → 107) and the triangle (x = 100, y 20 → 107), all monotone through the overlap at frames 14–15 (f14: id0 (66,64), id1 (62,64); f15: id0 (64,64), id1 (67,65)); confidence 0.75–0.77. 2.6 s. |

**So one SAM call per block with `SAM_PROMPT = "colored object"` tracks every element.** These measurements' paid calls: 3 Muse turns
≈ $0.005, 6 video requests × $0.01, 23 images × $0.0025 ≈ $0.06: **about $0.13 in all.**

## Muse Wonder on the Responses API (1 Nov 2026; docs/pilot-runs.md, runs 42–46; raw replies `results/api/wonder-*`)
Same endpoint, tools, `temperature: 0`, `reasoning.effort` and `max_output_tokens` as Spark. In all 41 Wonder replies read
(runs 42–46), `cached_tokens` is part of `input_tokens` and reasoning tokens are part of `output_tokens`; the arena
prices a reply as (input − cached) × $4/M + cached × $0.20/M + output × $20/M.
- **The output cap.** At `max_output_tokens: 400`, 6 of 11 replies came back `status: incomplete` with
  `incomplete_details.reason: max_output_tokens`, reasoning up to 398 of the 400 tokens, and 4 of the 6 held a reasoning
  item and nothing else (run 42). At 2,000, 0 of the pilot's 17 replies were incomplete and the longest was 763 output
  tokens, 636 of them reasoning (run 45).
- **A cut-off reply is safe to echo.** In all 9 cut-off replies seen (6 in run 42, 3 in run 46) the output held a
  `reasoning` item and sometimes a completed `message`, and never a `function_call`. Sent back as the task, that
  `message` and the nudge, or as the task and the nudge alone when only reasoning came back, the next turn was
  accepted and made the call the full reply makes (run 46).
- **A stored response can be lost.** With `previous_response_id`, call 3 of an episode at a 1,500-token cap failed with
  `400 {'error': {'code': None, 'message': 'referenced response not found or expired', 'param': None, 'type':
  'invalid_request_error'}}`, seconds after call 2's response was created (measured in a scratch run), and every response
  had `store: true`. A rerun (calls 1–2 from a scratch cache) failed the same way at call 3, in a script that, by its
  code and its traceback, retried a failed call twice, 3 s apart (run 43; the lines are in
  `results/api/wonder-probes-1-nov.txt`). The 11-call chain at a 400-token cap had no such failure, so it did not happen
  on every chain; the cause is not known.
- **The conversation can be sent as input items instead.** A turn 2 with no `previous_response_id` and `input` = the
  turn-1 user message (`{type: "message", role: "user", content: [{type: "input_text", text}]}`), the turn-1 output
  items as returned (`reasoning`, `message`, `function_call`) and the `function_call_output` was accepted: `completed`,
  an `act` call citing the table (run 44). So was the same input without the `reasoning` item. Input tokens were 1,407
  with the item and 1,401 without (cached 0 and 884); the item has `summary: []` and no other text, so the arena does
  not carry it.
- **Prefix caching** varies by request: 0 to 2,932 cached tokens in one request; 21,288 of the pilot's 35,830 input
  tokens (59%) and 20,500 of run 42's 27,043 (76%) were cached.
- **Latency.** The pilot's Muse requests took 2.24–7.34 s, mean 3.44 s over 17; its SAM requests mean 3.15 s over 20,
  longest 3.87 s. The probes of run 42, at a 400-token cap with `previous_response_id`, took 2.5–16.4 s a call, mostly
  11–14 s (measured in a scratch run). What made the difference was not isolated.

## Repeatability: the same request, different replies (the kill test, 1 Nov 2026; docs/pilot-runs.md, runs 54–57)
A cache file is named by the SHA-256 of its request (for SAM, of the model, the prompt and the frames), so a name that
two conditions' caches both hold is a request they sent alike. For SAM that means the same frames: the clip sent also
carries the encoder's version strings, and no run recorded its ffmpeg build. Counted by `results/kill-cache/count.py`
from the kill test's three archives: 813, 905 and 405 files, 1,888 distinct names, 178 in two or more caches. Of
those 178, **175 hold replies that differ byte for byte** and 3 the same; `git merge-tree` of the two SAM conditions'
result branches reported the same 175 names as add/add conflicts.
- **SAM 3.1:** the two SAM conditions sent 121 requests alike; 118 got different replies. Read with `sam_track`'s own
  patterns (a box for each frame and object id), the boxes differ in 80 of the 118; the largest difference in any box
  coordinate, per request, is 1 px at the median and 82 px at most.
- **Muse Wonder:** all three conditions sent 57 requests alike, and `temperature: 0.0` is echoed in all 171 replies.
  They can only be first turns: a later turn carries the ids of the replies before it. Every reply carries its own
  ids and timestamps, so all 57 differ byte for byte; what was generated (the message text, the tool calls, the
  output and reasoning token counts) differs in 51, and the tool call (name and arguments) in 9.

A cache folder holds one reply per request name, so it can hold only one of the replies the conditions got. The kill
test keeps one archive per condition, and a replay of each rebuilds its logs byte for byte (run 57).

## What follows for the arena
1. **A 31-frame block is billed as 50 frames** (`video_frames_processed: 50`). A 49-step block would cost the same,
   but the arena cannot build a scenario with it (`docs/pilot-runs.md`, run 30), so blocks stay at 30 steps.
2. **One SAM call per block with the prompt "colored object"** (`sam-6` confirmed it on video): $0.01 per block.
   The kill test on Muse Wonder (114 episodes a condition, seeds 1001–1019) is projected at $21.22 from the rule policy's
   block counts (`docs/pilot-runs.md`, run 48); the runner counted $28.93 for it (runs 54–56).
3. Muse Spark per turn (28 Oct): ~1k input + ~160 output tokens, ~8 turns ≈ $0.016 per episode; latency 1.3–12 s per
   turn. Muse Wonder per turn (the pilot, run 45): 1,629 input tokens (968 cached) + 271 output, $0.0083, 3.44 s, and
   one Muse turn per block (22 turns, 22 blocks).
4. **The kill test's numbers are one sample of two services that do not reliably repeat themselves.** A replay of a
   condition's own archive reproduces its logs; a second paid run would not be expected to.
