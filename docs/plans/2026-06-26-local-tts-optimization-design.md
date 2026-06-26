# Local TTS Optimization Design

Date: 2026-06-26

## Goal

Improve audiobook generation speed on the local RTX 4070 Super machine before considering Google Cloud GPU deployment.

The optimization should preserve the existing product flow and backend architecture. This is an algorithm pass, not an infrastructure migration.

## Non-Goals

- No Google Cloud setup yet.
- No browser WebGPU migration.
- No Redis, Celery, or worker split in this pass.
- No dynamic batching across users.
- No default FP16 change.
- No UI changes.
- No destructive database changes.

## Current Generation Path

The current path is:

```text
source file/url/text
  -> source loader extracts chapters
  -> normalize and clean chapter text
  -> chunk_text() splits text into sentence-ish chunks
  -> synth_chapter() calls Kokoro once per chunk
  -> audio streams to a temporary WAV
  -> ffmpeg transcodes WAV to chapter MP3
  -> cues and metadata are written
```

This is memory-efficient because audio streams to disk. The main likely speed issue is that sentence-level chunks cause many small Kokoro calls. Each call has overhead, so the GPU may not get enough work per invocation.

## Recommended Approach

Use a benchmark-first, chunk-packing optimization.

1. Add benchmark instrumentation so we can measure the current baseline on the local PC.
2. Change `chunk_text()` to pack nearby sentences into larger blocks.
3. Keep a rollback flag that restores sentence-only chunking.
4. Compare real-time factor before and after using the same input, voice, speed, and hardware.

## Chunk Packing Design

The new chunker should still split text at sentence boundaries first, then group sentences into blocks.

Proposed defaults:

```text
mode: packed
TARGET_CHARS: 800
MAX_CHARS: 1200
MIN_CHARS: 120
```

Rules:

- Preserve sentence order.
- Prefer ending chunks at sentence boundaries.
- Pack short sentences together until near `TARGET_CHARS`.
- Flush a chunk before exceeding `MAX_CHARS`.
- If one sentence is longer than `MAX_CHARS`, split it on softer boundaries such as commas, semicolons, colons, or whitespace.
- Remove empty chunks.
- Keep behavior deterministic.

Rollback behavior:

```text
AUDIOBOOK_CHUNK_MODE=sentence
```

Optimized behavior:

```text
AUDIOBOOK_CHUNK_MODE=packed
```

The default can remain `packed` after tests pass because it preserves public behavior and only changes how we feed Kokoro internally.

## Benchmark Design

Add a lightweight benchmark script that can run locally without the web UI.

Input options:

- a provided file path
- optional generated text for repeatable smoke tests

Metrics:

```text
input_path
voice
speed
chunk_mode
chunk_count
generation_seconds
audio_seconds
real_time_factor
output_bytes
cuda_available
cuda_device_name
cuda_memory_allocated_mb
cuda_memory_reserved_mb
```

The benchmark should call the same production generation path where practical. That keeps results meaningful.

## Expected Result

A good result would be:

```text
fewer chunks
lower wall time
lower RTF
same chapter MP3/cues behavior
no major memory increase
```

We should not claim a speedup until the local benchmark proves it.

## Risks

1. Larger text chunks may change cue granularity.
   Kokoro still internally yields generated segments, so cues should remain useful, but they may differ from sentence-only mode.

2. Oversized chunks may hurt model behavior or memory.
   The hard max and long-sentence splitting limit this.

3. Some abbreviations may split imperfectly.
   This already exists in sentence chunking. The optimization should not try to solve full linguistic parsing in this pass.

4. Benchmark scripts may generate large output.
   Benchmark outputs should write to ignored directories such as `out_bench/`.

## Testing Strategy

Add focused unit tests for `chunk_text()`:

- sentence mode keeps one sentence per chunk
- packed mode combines short sentences
- packed mode respects max chunk size
- long text without punctuation still splits safely
- no empty chunks
- sentence order is preserved

Run existing tests after implementation:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
```

Then run the local benchmark on the RTX 4070 Super with sentence mode and packed mode.

## Rollback

Rollback does not require code revert if the flag exists:

```bash
export AUDIOBOOK_CHUNK_MODE=sentence
```

If needed, revert the optimization commit. There are no DB migrations and no generated data format changes required by this design.
