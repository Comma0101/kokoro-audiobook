# Coding Agent Instructions — Kokoro Audiobook CLI (Phase 1)

Build a local, offline CLI that converts **PDF / EPUB / TXT** into a chaptered audiobook
(`.mp3` per chapter) plus a matching `.srt` subtitle file per chapter, using the
**Kokoro-82M** TTS engine that is already working in this repo.

This is **Phase 1 = CLI only**. Do not build a web UI yet. Keep the design clean so a
web player can be added later by reading the same SRT/VTT output.

---

## 0. Ground truth about this environment (verified — do not re-litigate)

- Repo: `/home/comma/Documents/kokoro_test`
- Python venv: `.venv` (Python **3.11**), managed by **`uv`**. There is **no `pip`** in the venv
  — install with `uv pip install <pkg>` (or `uv add` if a `pyproject.toml` exists).
- Already installed and proven working: `kokoro==0.9.4`, `misaki==0.9.4`,
  `phonemizer-fork`, `torch==2.12.1`, `soundfile`, `numpy`, `num2words`, `spacy` (unused — ignore it).
- **GPU is available**: NVIDIA RTX 4070 SUPER, `torch.cuda.is_available() == True`. Use it.
- `ffmpeg` is installed system-wide. **`espeak-ng` is NOT installed and is NOT required**
  for English (misaki has its own G2P). Do not add it as a hard dependency.
- Working reference scripts already exist: `test_english_kokoro.py` (English, voice `af_heart`)
  and `test_kokoro.py` (Chinese, `lang_code='z'`). Read them first — reuse their proven call pattern.

### Dependencies to add (only these)
```
uv pip install PyMuPDF EbookLib beautifulsoup4
```
- `PyMuPDF` (`import fitz`) → PDF text extraction
- `EbookLib` + `beautifulsoup4` → EPUB chapter extraction
- **Do NOT install** `pydub` (can't write M4B chapters, redundant — we already have numpy audio + ffmpeg)
  or `spacy` models (overkill; we split with regex / Kokoro's own chunking).

---

## 1. Architecture

Single installable package `audiobook/` invoked as a CLI. Modules:

```
audiobook/
  __init__.py
  cli.py            # argparse entrypoint
  parsers.py        # PDF / EPUB / TXT -> list[Chapter]
  chunker.py        # Chapter text -> list[str] sentence-ish chunks
  tts.py            # one shared KPipeline; generate audio + real durations
  assemble.py       # write per-chapter WAV->MP3 via ffmpeg + build SRT
  models.py         # dataclasses: Chapter, Cue
```

Data model (`models.py`):
```python
@dataclass
class Chapter:
    index: int          # 1-based
    title: str          # e.g. "Chapter 1" or EPUB heading; fallback "Part_{index}"
    text: str           # cleaned plain text

@dataclass
class Cue:               # one SRT subtitle entry
    start: float         # seconds, absolute within the chapter
    end: float
    text: str            # the graphemes Kokoro actually spoke for this segment
```

---

## 2. Parsing layer (`parsers.py`)

`parse(path: str) -> list[Chapter]` dispatching on extension.

- **TXT**: read UTF-8, return a single `Chapter(1, <filename stem>, text)`.
  Optionally split on form-feeds or `\n\n\n+` if present, else one chapter.
- **EPUB** (`EbookLib` + `bs4`): iterate `book.get_items_of_type(ebooklib.ITEM_DOCUMENT)`
  in spine order. For each HTML doc, `BeautifulSoup(..., "html.parser")`, drop
  `<script>/<style>`, extract text with `get_text(separator=" ")`. Use the first
  `<h1>/<h2>/<h3>` as the title; fallback `Part_{index}`. Skip empty/nav docs.
- **PDF** (`fitz`): open, iterate pages, `page.get_text("text")`. Apply light cleaning
  (see §2.1). PDFs rarely have reliable chapter structure — for Phase 1, treat the whole
  PDF as **one chapter** unless a TOC is trivially available via `doc.get_toc()`; if
  `get_toc()` returns entries, split by those page ranges. Don't over-engineer.

### 2.1 Text cleaning (shared helper)
- Collapse runaway whitespace: `" ".join(text.split())` (this is what the working script does).
- For PDF only, strip page numbers / repeated headers-footers with conservative regex
  (e.g. lines that are just digits, or a header string repeated on >50% of pages).
  **Be conservative** — never delete real prose. If unsure, leave it.
- Normalize unicode quotes/dashes to ASCII-ish where it helps TTS, but keep it minimal.

---

## 3. Chunking layer (`chunker.py`)

`chunk_text(text: str) -> list[str]`:
- Split into sentence-ish pieces with the **same regex the working script uses**:
  `re.split(r'(?<=[.!?])\s+', text)`, dropping empties/whitespace.
- This is only a *coarse* feed into Kokoro. **Do not rely on these strings for SRT text.**
  Kokoro re-chunks internally and tells us what it actually spoke (see §4). No spaCy.

---

## 4. TTS layer (`tts.py`) — the part that must be correct

Initialize **one** pipeline and reuse it for the whole run (loading is expensive):
```python
from kokoro import KPipeline
pipeline = KPipeline(lang_code='a')   # 'a' = American English
```
Ensure it runs on GPU. KPipeline generally auto-detects CUDA via torch; verify by logging
`torch.cuda.is_available()` at startup and warn if False. Default voice `af_heart`, speed `1.0`.

**Critical — timestamping.** The generator yields tuples `(gs, ps, audio)` **per internal
segment**, where `gs` is the grapheme text Kokoro actually spoke and `audio` is a numpy
float array at **24000 Hz**. A single input sentence may yield multiple segments. Build the
SRT from what Kokoro returns, NOT from your pre-split sentences, or timing will drift.

```python
SAMPLE_RATE = 24000

def synth_chapter(pipeline, chunks) -> tuple[np.ndarray, list[Cue]]:
    audio_parts, cues = [], []
    t = 0.0
    for chunk in chunks:
        for gs, ps, audio in pipeline(chunk, voice='af_heart', speed=1.0,
                                      split_pattern=r'(?<=[.!?])\s+'):
            if audio is None:
                continue
            dur = len(audio) / SAMPLE_RATE
            cues.append(Cue(start=t, end=t + dur, text=gs.strip()))
            t += dur
            audio_parts.append(audio)
    full = np.concatenate(audio_parts) if audio_parts else np.zeros(0, dtype='float32')
    return full, cues
```
(You can pass either the whole chapter text or pre-split chunks to `pipeline(...)`; either way
trust the yielded `gs`/`audio`. Passing the whole chapter text and letting `split_pattern` do
the work is simplest — measure and pick whichever is cleaner.)

### Memory / scalability — required, not optional
Books are hours long; do **not** hold the whole book's audio in RAM. Process **one chapter at
a time**: synth → write that chapter's WAV to disk → free the arrays → move on. Never
accumulate all chapters' audio in a list.

---

## 5. Assembly layer (`assemble.py`)

Per chapter:
1. Write chapter audio to a temp WAV with `soundfile.write(tmp_wav, audio, 24000)`.
2. Transcode to MP3 with a direct `ffmpeg` subprocess call (no pydub):
   `ffmpeg -y -i tmp.wav -codec:a libmp3lame -qscale:a 2 "Chapter_NN_title.mp3"`.
   Delete the temp WAV after.
3. Write the SRT next to it (`Chapter_NN_title.srt`) from the chapter's `Cue` list.

Output filenames: zero-padded index + sanitized title, e.g. `Chapter_01_Introduction.mp3`.
Write everything into an output dir (default `./out/<book stem>/`).

### SRT writer
Standard SRT format, times as `HH:MM:SS,mmm`, blank line between cues, 1-based indices:
```
1
00:00:00,000 --> 00:00:03,480
The spoken text here.

```
Times are **per-chapter absolute** (each chapter's SRT starts at 0), matching its own MP3.

---

## 6. CLI (`cli.py`)

```
python -m audiobook INPUT [options]
```
Options:
- `INPUT` (positional): path to `.pdf` / `.epub` / `.txt`
- `-o, --output-dir`   default `./out`
- `--voice`            default `af_heart`
- `--speed`            float, default `1.0`
- `--lang`             default `a` (American English)
- `--single-file`      flag: also concatenate all chapter MP3s into one `Audiobook.mp3`
                       via `ffmpeg -f concat` (default OFF — per-chapter is the default)
- `--no-srt`           flag: skip subtitle generation

Behavior:
- Print a startup banner: input, detected type, chapter count, GPU yes/no, voice.
- Per-chapter progress to stderr: `[3/24] Chapter 3: synthesizing… 412 cues, 18.3 min`.
- Use `tqdm` if you want a progress bar (add via `uv pip install tqdm`), otherwise plain prints.
- Be resumable-friendly: if a chapter's MP3 already exists in the output dir, skip it
  (allows recovery after interruption on long books). Add `--force` to override.

---

## 7. Verification (do this, show evidence — don't claim done without it)

1. **Deps import**: `.venv/bin/python -c "import fitz, ebooklib, bs4, kokoro, soundfile; print('ok')"`.
2. **TXT end-to-end** on the existing `trading_psychology.txt`:
   `python -m audiobook trading_psychology.txt -o out_test`
   - Assert: an MP3 is produced and is playable (`ffprobe` shows a valid duration > 0).
   - Assert: an SRT is produced; its **last cue end-time is within ~0.3s of the MP3 duration**
     (this proves alignment). Print both numbers.
3. **EPUB**: run on any small EPUB; assert chapter count > 1 and each chapter has MP3+SRT.
4. **PDF**: run on a small PDF; assert text extracted (non-empty) and MP3 produced.
5. Spot-check by opening one MP3 + SRT in VLC and confirming subtitles track the audio.
6. Report the **RTF** (generation_time / audio_seconds) so we know real throughput on GPU.

If alignment check (#2) fails, fix the `gs`/duration mapping before declaring success —
that is the core correctness requirement.

---

## 8. Out of scope for Phase 1 (note, don't build)
- Web UI / Gradio / browser highlighting (Phase 2 — will reuse the SRT/VTT this phase emits).
- `.m4b` with chapter markers (Phase 2 — needs an ffmpeg metadata/chapters step, not pydub).
- Multi-language auto-detection. English (`lang_code='a'`) is the default; `--lang` exposes the rest.

## 9. Conventions
- Match the existing scripts' style; keep functions small and pure where possible.
- No network calls at runtime (fully offline). Models are already cached locally.
- Fail loudly with clear messages on unsupported file types or empty extraction.
