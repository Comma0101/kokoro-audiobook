# Coding Agent Instructions — Phase 1.5

Phase 1 (CLI: PDF/EPUB/TXT → per-chapter MP3+SRT) is **built and working** — Alice EPUB
produced 14 chapters, PDF and TXT both succeeded. This phase has two parts:

- **Part A — fix latent bugs found in code review** (do these first; they're small and real).
- **Part B — open the "everything text → audio" door**: refactor inputs into an **adapter
  pattern**, add a **URL adapter** (read any web article), and add a **narration normalizer**
  (make text sound right when spoken).

Read `AGENT_INSTRUCTIONS.md` for the original spec and the verified environment facts
(uv venv, no pip, GPU present, espeak-ng not needed). Install deps with `uv pip install`.

---

## PART A — Bug fixes (do first, verify each)

### A1. Centralize and harden filename sanitization (real path-safety bug)
Right now `parse_pdf` sanitizes titles (`parsers.py:115`) but `parse_epub` does **not**
(`parsers.py:53`), and `cli.py:53` builds the filename directly from `chapter.title`. A
heading containing `/`, `:`, `?`, `"` or a single-quote will create wrong paths, break the
`--single-file` concat list, or fail outright. Alice only worked because its titles happened
to be clean.

Fix:
- Add one helper `sanitize_filename(name: str) -> str` (put it in `assemble.py` or a small
  `util.py`). Strip/replace anything outside `[A-Za-z0-9 ._-]`, collapse spaces, trim, and
  cap length (e.g. 80 chars). Return a non-empty fallback like `"untitled"` if it reduces to empty.
- **Remove** the ad-hoc sanitization inside `parse_pdf` — parsers should return *raw human
  titles*; sanitization happens once, at filename construction in `cli.py`.
- Keep the raw `chapter.title` for any future display/metadata; only the on-disk `stem` is sanitized.

### A2. Fix `--single-file` concat path & quote escaping
`cli.py:82-94`: the concat list writes `file '<name>'` with single quotes. A filename
containing `'` breaks the demuxer. After A1, names are safer, but still escape properly:
ffmpeg concat requires `'` inside a path to be written as `'\''`. Use a helper that escapes,
or (simpler) write absolute paths and escape. Verify a multi-chapter `--single-file` run.

### A3. Make `--no-srt` not write-then-delete
`cli.py:79` currently lets `assemble_chapter` always write the SRT, then deletes it. Thread a
`write_srt: bool` param into `assemble_chapter` and skip writing entirely when `--no-srt`.
Also: when a chapter is skipped because the MP3 exists, don't touch its SRT.

### A4. Guard against the "one giant chapter" memory case
`synth_chapter` (`tts.py`) accumulates a whole chapter's audio in RAM before concatenating.
That's fine for real chapters, but a **TOC-less PDF or a plain TXT becomes a single chapter =
the entire book in memory** (numpy float32 at 24 kHz ≈ ~5.5 MB/min → a 10-hour book ≈ 3 GB+).
Fix by streaming *within* a chapter:
- Change `synth_chapter` to **append each segment's audio to the open WAV file incrementally**
  (use `soundfile.SoundFile(path, 'w', samplerate=24000, channels=1)` and `.write()` per
  segment) instead of building one big list, then transcode the WAV → MP3 as today.
- Return only the `list[Cue]` (and total duration) from the synth step; assembly reads the WAV.
- This keeps memory flat regardless of book size. Verify RAM stays bounded on the long TXT.

### A5. Add a `.gitignore`
This project dir is currently untracked. Add `.gitignore` covering: `.venv/`, `__pycache__/`,
`*.pyc`, `out*/`, `*.wav`, `*.mp3`, `*.srt`, `*.reapeaks`, model caches. Keep source + the
two sample inputs (`alice.epub`, `test.pdf`, `trading_psychology.txt`) if you want them as fixtures.

---

## PART B — Adapters + URL + narration normalizer

### B1. The adapter pattern (the architectural seam — do this before adding sources)
Every input source must reduce to the **existing `list[Chapter]`** contract. The TTS/assembly
engine must never learn where text came from. Refactor `parsers.py` into a small registry:

```
audiobook/
  sources/
    __init__.py      # get_source(input_str) -> Source ; dispatch by scheme/extension
    base.py          # Source protocol: load(input_str) -> list[Chapter]
    file_source.py   # moves current parse_txt/epub/pdf here, unchanged behavior
    url_source.py    # NEW (B2)
```
- `get_source` dispatch rule: if input starts with `http://` or `https://` → `UrlSource`;
  else treat as a filesystem path and dispatch by extension as today.
- `cli.py` changes only its first step: `chapters = get_source(args.input).load(args.input)`.
  Everything downstream (chunk → synth → assemble) is untouched.
- Keep behavior identical for files — this is a move + thin wrapper, not a rewrite. Re-run the
  Phase 1 verifications afterward to prove no regression.

### B2. URL adapter — "read me this web page"
New dep: `uv pip install trafilatura` (robust readability extraction; falls back gracefully).
- `UrlSource.load(url)`: fetch the page (trafilatura's `fetch_url`), extract main article text
  with `trafilatura.extract(...)` (returns clean text, drops nav/ads/boilerplate). Pull the
  page `<title>` for the chapter title (sanitized via A1).
- Return a **single `Chapter`** (web articles are usually one piece). If extraction yields
  nothing, fail loudly: `"Could not extract readable text from <url>"`.
- Be offline-tolerant about *runtime model loading* (Kokoro is local) but obviously this
  adapter needs network; that's expected and fine — document it.
- CLI: no new flags needed — `python -m audiobook https://example.com/article` just works
  because `get_source` detects the scheme. Output dir stem: derive from the page title or URL slug.

### B3. Narration normalizer — the quality differentiator
Add `audiobook/normalize.py` with `normalize_for_speech(text: str) -> str`, applied to each
chapter's text **before** chunking (insert one line in `cli.py` between parse and chunk).
This is **deterministic, rule-based, verbatim-safe** — it makes text *speakable*, it does not
rewrite meaning. Default ON.

Handle at least:
- **Numbers & currency:** `num2words` (already installed). `$4.2M` → "four point two million
  dollars", `1990s` → "nineteen nineties", `3.14` → "three point one four", percentages, ranges.
  Be careful with years vs plain numbers — keep rules conservative; when ambiguous, prefer the
  plain reading over a wrong one.
- **Common abbreviations:** Dr.→Doctor, Mr./Mrs./Ms., St.→Saint/Street (ambiguous — pick one,
  document it), e.g.→"for example", i.e.→"that is", etc.→"et cetera", vs.→"versus", No.→"number".
- **Symbols:** `&`→"and", `%`→"percent", `#`→"number", `@`→"at", `~`→"about", em/en dashes →
  pause (comma), `/`→"slash" only when between words.
- **Noise to strip:** URLs (replace with "link" or drop), footnote markers like `[12]`,
  Markdown artifacts (`**`, `##`, backticks), repeated punctuation.
- **Sentence-boundary safety:** don't let abbreviation periods (`Dr.`) be mistaken for sentence
  ends downstream — normalize *before* `chunk_text` splits on `.!?`.

Structure it as an ordered list of small regex/callable rules so adapters can extend it. Add a
`--no-normalize` CLI flag to bypass (purist/verbatim mode).

> **LLM rewrite pass — design the seam, leave it OFF.** Add an optional hook
> `normalize_for_speech(text, llm=None)` where an injected callable could later do a
> "rewrite this for natural narration" pass (e.g. via the Claude API). **Do not implement or
> wire any LLM now** — just leave the parameter and a `# Phase 4` comment so it's a one-line
> addition later. Rule-based stays the default so output is reproducible and offline.

---

## Verification (show evidence, don't just assert)

Re-run Phase 1 gates from `AGENT_INSTRUCTIONS.md` §7 first (no regression), then:

1. **Filenames (A1):** run on an input whose chapter title contains `:` or `/` (fake one) and
   confirm a valid file is produced, not a crash or stray subdirectory.
2. **Memory (A4):** generate the long TXT and confirm peak RSS stays roughly flat (e.g. watch
   with `/usr/bin/time -v` "Maximum resident set size") versus the old accumulate-in-list build.
3. **Adapter refactor (B1):** `python -m audiobook trading_psychology.txt` and the Alice EPUB
   still produce identical chapter counts and aligned SRT (last cue end within ~0.3s of MP3 dur).
4. **URL (B2):** `python -m audiobook <a real article URL>` → one MP3 + SRT of clean article
   prose (no nav/menu junk in the audio). Spot-check the first 20s.
5. **Normalizer (B3):** unit-test `normalize_for_speech` on a fixture string containing
   `Dr. Smith spent $4.2M in the 1990s (see e.g. [3]).` and assert the output is fully spoken
   words with no stray symbols. Then confirm a normalized vs `--no-normalize` run differ.

## Out of scope (note, don't build)
- Web player / highlighting, RSS auto-podcast, `.m4b` chapters, OCR for scanned PDFs, the LLM
  rewrite pass. Those are later phases. Keep the adapter and normalizer seams clean so each is
  an additive change, not a refactor.

## Conventions
- Match existing code style. Small, pure functions. Fail loudly with clear messages.
- After each Part, run its verification before moving on. If the SRT-alignment check ever
  fails, stop and fix the `gs`/duration mapping — that's the core correctness invariant.
