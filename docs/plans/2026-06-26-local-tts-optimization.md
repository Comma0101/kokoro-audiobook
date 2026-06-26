# Local TTS Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve local Kokoro audiobook generation speed by benchmarking the current path and packing sentence chunks into larger model inputs.

**Architecture:** Keep the existing server-side generation architecture. Add deterministic chunk-packing in `audiobook/chunker.py`, pass chunk statistics through `audiobook/engine.py`, and add a local benchmark script that compares sentence mode and packed mode on the same machine. The old sentence-only behavior remains available through an environment flag.

**Tech Stack:** Python, Kokoro `KPipeline`, PyTorch/CUDA, SoundFile, ffmpeg, existing FastAPI app, shell-based test scripts.

---

## Task 1: Add Chunker Unit Tests

**Files:**
- Create: `test_chunker.py`
- Modify: none

**Step 1: Write failing tests**

Create `test_chunker.py`:

```python
from audiobook.chunker import chunk_text


def test_sentence_mode_keeps_sentence_sized_chunks():
    text = "One short sentence. Two short sentence. Three short sentence."
    chunks = chunk_text(text, mode="sentence")
    assert chunks == [
        "One short sentence.",
        "Two short sentence.",
        "Three short sentence.",
    ]


def test_packed_mode_combines_short_sentences():
    text = "One short sentence. Two short sentence. Three short sentence."
    chunks = chunk_text(text, mode="packed", target_chars=80, max_chars=120)
    assert chunks == [text]


def test_packed_mode_respects_max_chars():
    sentence = "This is a sentence with enough words to matter."
    text = " ".join([sentence] * 12)
    chunks = chunk_text(text, mode="packed", target_chars=120, max_chars=160)
    assert len(chunks) > 1
    assert all(len(chunk) <= 160 for chunk in chunks)
    assert " ".join(chunks).replace("  ", " ") == text


def test_long_unpunctuated_text_splits_safely():
    text = "word " * 400
    chunks = chunk_text(text, mode="packed", target_chars=120, max_chars=160)
    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 160 for chunk in chunks)


def test_no_empty_chunks_from_messy_spacing():
    text = "  First.   \n\n Second?     Third!  "
    chunks = chunk_text(text, mode="packed", target_chars=80, max_chars=120)
    assert all(chunk for chunk in chunks)
    assert "First." in chunks[0]
    assert "Second?" in chunks[0]
    assert "Third!" in chunks[0]
```

**Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python test_chunker.py
```

Expected: FAIL because `chunk_text()` does not accept `mode`, `target_chars`, or `max_chars` yet.

**Step 3: Commit is not needed yet**

Do not commit failing tests alone unless pausing work.

---

## Task 2: Implement Packed Chunking

**Files:**
- Modify: `audiobook/chunker.py`
- Test: `test_chunker.py`

**Step 1: Replace the simple chunker with configurable chunking**

Implementation requirements:

- Keep `chunk_text(text)` as the public function.
- Add optional keyword args: `mode=None`, `target_chars=None`, `max_chars=None`.
- Read defaults from environment:
  - `AUDIOBOOK_CHUNK_MODE`, default `packed`
  - `AUDIOBOOK_CHUNK_TARGET_CHARS`, default `800`
  - `AUDIOBOOK_CHUNK_MAX_CHARS`, default `1200`
- Support `mode="sentence"` for rollback.
- Support `mode="packed"` for optimized behavior.
- Preserve deterministic order.

Suggested structure:

```python
import os
import re

_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\\s+")
_SOFT_SPLIT_RE = re.compile(r"(?<=[,;:，；：])\\s+|\\s+")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _sentence_chunks(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    return [part.strip() for part in _SENTENCE_RE.split(normalized) if part.strip()]


def _split_long_piece(piece: str, max_chars: int) -> list[str]:
    if len(piece) <= max_chars:
        return [piece]

    parts = [p.strip() for p in _SOFT_SPLIT_RE.split(piece) if p.strip()]
    chunks = []
    current = ""

    for part in parts:
        if not current:
            current = part
        elif len(current) + 1 + len(part) <= max_chars:
            current = f"{current} {part}"
        else:
            chunks.append(current)
            current = part

        while len(current) > max_chars:
            chunks.append(current[:max_chars].strip())
            current = current[max_chars:].strip()

    if current:
        chunks.append(current)
    return chunks


def _pack_chunks(pieces: list[str], target_chars: int, max_chars: int) -> list[str]:
    packed = []
    current = ""

    for piece in pieces:
        for part in _split_long_piece(piece, max_chars):
            if not current:
                current = part
            elif len(current) + 1 + len(part) <= max_chars and len(current) < target_chars:
                current = f"{current} {part}"
            else:
                packed.append(current)
                current = part

    if current:
        packed.append(current)
    return packed


def chunk_text(text: str, *, mode: str | None = None, target_chars: int | None = None, max_chars: int | None = None) -> list[str]:
    mode = (mode or os.getenv("AUDIOBOOK_CHUNK_MODE", "packed")).strip().lower()
    target = target_chars or _env_int("AUDIOBOOK_CHUNK_TARGET_CHARS", 800)
    maximum = max_chars or _env_int("AUDIOBOOK_CHUNK_MAX_CHARS", 1200)
    maximum = max(maximum, 80)
    target = max(40, min(target, maximum))

    pieces = _sentence_chunks(text)
    if mode == "sentence":
        return pieces
    if mode != "packed":
        raise ValueError(f"Unsupported chunk mode: {mode}")
    return _pack_chunks(pieces, target, maximum)
```

**Step 2: Run chunker tests**

Run:

```bash
.venv/bin/python test_chunker.py
```

Expected: PASS.

**Step 3: Run existing lightweight tests**

Run:

```bash
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
```

Expected: PASS / exit 0.

**Step 4: Commit**

Run:

```bash
git add audiobook/chunker.py test_chunker.py
git commit -m "Optimize text chunk packing"
```

---

## Task 3: Surface Chunk Metrics In Generation Progress

**Files:**
- Modify: `audiobook/engine.py`
- Modify: `audiobook/server.py` if needed
- Test: `test_chunker.py` remains enough for algorithm behavior

**Step 1: Add low-risk metadata**

In `audiobook/engine.py`, after chunking, include chunk mode and character stats in `chapter_info` progress metadata.

Add values such as:

```python
chunk_chars = [len(c) for c in chunks]
progress_cb(
    stage="chapter_info",
    index=i,
    total=total_chapters,
    title=chapter.title,
    total_chunks=len(chunks),
    lang=ch_lang,
    voice=ch_voice,
    chunk_chars=sum(chunk_chars),
    max_chunk_chars=max(chunk_chars) if chunk_chars else 0,
)
```

Keep this passive. Do not change UI logic.

**Step 2: Optionally preserve metadata in server progress dict**

In `audiobook/server.py`, when `stage == "chapter_info"`, store:

```python
p["chunk_chars"] = kwargs.get("chunk_chars", 0)
p["max_chunk_chars"] = kwargs.get("max_chunk_chars", 0)
```

**Step 3: Run verification**

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
```

Expected: all pass / exit 0.

**Step 4: Commit**

Run:

```bash
git add audiobook/engine.py audiobook/server.py
git commit -m "Record generation chunk metrics"
```

---

## Task 4: Add Local Benchmark Script

**Files:**
- Create: `scripts/benchmark_tts.py`
- Modify: `.gitignore` if benchmark output path is not already ignored

**Step 1: Create benchmark script**

Create `scripts/benchmark_tts.py` with these behaviors:

- Args:
  - `input`, optional path
  - `--output-dir`, default `out_bench`
  - `--voice`, default `af_heart`
  - `--speed`, default `1.0`
  - `--lang`, default `auto`
  - `--chunk-mode`, choices `sentence` or `packed`
  - `--target-chars`, optional int
  - `--max-chars`, optional int
  - `--repeat-text`, optional int for generated smoke input if no input path is provided
- Set chunk env vars before calling `generate_audiobook()`.
- Force regeneration.
- Print JSON metrics to stdout.
- Write generated output under ignored `out_bench/`.

Metric keys:

```text
input
chunk_mode
target_chars
max_chars
voice
speed
cuda_available
cuda_device_name
generation_seconds
audio_seconds
real_time_factor
chapter_count
output_dir
output_bytes
```

**Step 2: Run benchmark smoke test with generated text**

Run:

```bash
.venv/bin/python scripts/benchmark_tts.py --repeat-text 20 --chunk-mode sentence
.venv/bin/python scripts/benchmark_tts.py --repeat-text 20 --chunk-mode packed
```

Expected:

- both commands exit 0
- both print valid JSON
- `chunk_mode` differs as requested
- output writes under `out_bench/`

This may load Kokoro and use CUDA, so expect it to take longer than unit tests.

**Step 3: Commit**

Run:

```bash
git add scripts/benchmark_tts.py .gitignore
git commit -m "Add local TTS benchmark script"
```

---

## Task 5: Run Local 4070 Benchmark

**Files:**
- No source changes unless benchmark exposes a bug

**Step 1: Choose a local benchmark input**

Use a local file that is intentionally ignored and not committed, for example:

```text
trading_psychology.txt
```

or a new local text file.

**Step 2: Run baseline sentence mode**

Run:

```bash
AUDIOBOOK_CHUNK_MODE=sentence .venv/bin/python scripts/benchmark_tts.py trading_psychology.txt --chunk-mode sentence --output-dir out_bench_sentence
```

Record JSON output.

**Step 3: Run optimized packed mode**

Run:

```bash
AUDIOBOOK_CHUNK_MODE=packed .venv/bin/python scripts/benchmark_tts.py trading_psychology.txt --chunk-mode packed --output-dir out_bench_packed
```

Record JSON output.

**Step 4: Compare**

Compare:

```text
chunk_count
generation_seconds
audio_seconds
real_time_factor
output_bytes
CUDA memory if available
```

Success means packed mode has lower wall time and RTF without errors or obvious audio quality problems.

---

## Task 6: Final Verification And Push

**Files:**
- No source changes unless fixes are needed

**Step 1: Full lightweight verification**

Run:

```bash
.venv/bin/python test_chunker.py
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
```

Expected: all pass / exit 0.

**Step 2: Check Git state**

Run:

```bash
git status --short
git log --oneline --decorate -5
```

Expected: clean working tree after commits.

**Step 3: Push**

Run:

```bash
git push
```

Expected: `main -> main` pushed to `origin`.

## Rollback

Runtime rollback:

```bash
export AUDIOBOOK_CHUNK_MODE=sentence
```

Git rollback:

```bash
git revert <optimization-commit>
```

No database rollback is needed.
