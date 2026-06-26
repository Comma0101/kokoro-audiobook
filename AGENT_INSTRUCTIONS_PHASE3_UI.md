# Coding Agent Instructions — Phase 3: Web UI (phone-first, offline-capable)

Add a small **web app** over the existing `audiobook` engine so the user can submit text
and listen with synced highlighting from **phone or PC**, one codebase. Generation always
happens on the Arch GPU box; phone/PC are browser clients.

**Decisions already made (do not re-litigate):**
- **Access:** public reachability, **no auth implemented now** — but build the token seam (see §6).
- **Primary device:** phone, often offline → **PWA + offline caching is a priority**, touch-first player.
- Kokoro needs the GPU → the box runs the server; one job at a time (shared `KPipeline` singleton).
- Reuse the engine and the `list[Chapter]` adapter contract from Phases 1–1.5. The CLI stays.

Prereqs: Phases 1 and 1.5 (adapters, URL source, normalizer) should be in place. New deps:
`uv pip install fastapi "uvicorn[standard]" python-multipart`.

---

## 1. Refactor: extract a shared engine function (do first)
Today the generation loop lives in `cli.py:51-94`. Pull the core into a reusable function the
CLI **and** server both call, so there's one code path:

```python
# audiobook/engine.py
def generate_audiobook(source_input, out_dir, *, voice, speed, lang,
                       normalize=True, write_srt=True, single_file=False,
                       progress_cb=None) -> BookResult:
    chapters = get_source(source_input).load(source_input)
    pipeline = init_pipeline(lang)            # caller may pass a shared one (see §3)
    for i, ch in enumerate(chapters, 1):
        if progress_cb: progress_cb(stage="chapter_start", index=i, total=len(chapters), title=ch.title)
        text = normalize_for_speech(ch.text) if normalize else ch.text
        cues = synth_chapter_streaming(pipeline, chunk_text(text), out_wav=..., voice=voice, speed=speed)
        assemble_chapter(...); write cues.json (see §4)
        if progress_cb: progress_cb(stage="chapter_done", index=i, total=len(chapters), seconds=...)
    return BookResult(book_id, title, out_dir, chapters_meta)
```
- `cli.py` becomes a thin wrapper that calls `generate_audiobook(progress_cb=print_progress)`.
- Allow passing an **already-initialized `pipeline`** in so the server loads Kokoro once and reuses it.

---

## 2. Backend API (FastAPI)
Serve JSON under `/api`, media as static files, and the PWA frontend as static files.

Endpoints:
- `POST /api/jobs` — accept **one of**: multipart file upload, `{"url": "..."}`, or `{"text": "..."}`,
  plus `voice`, `speed`, `lang`, `normalize`. Validate (size cap on uploads, allowed extensions).
  Create a job, enqueue it, return `{job_id, status}`. Do **not** block on generation.
- `GET /api/jobs` — list all jobs/books (the Library), newest first.
- `GET /api/jobs/{id}` — full status: `queued|running|done|error`, progress
  (`chapters_done/total`, current title, approx %), error message, and when done the chapter
  list with media URLs (`mp3`, `cues`).
- `DELETE /api/jobs/{id}` — delete job + its output dir.
- `GET /media/{book}/{file}` — serve MP3 / cues.json (or mount `out/` via `StaticFiles`).
- `GET /healthz` — liveness + `cuda_available`.

---

## 3. Job queue & worker (keep it simple — no Celery/Redis)
- The GPU serializes work: run **one worker** consuming an in-process queue
  (`asyncio.Queue` + a single background task, or a `threading.Thread`). One job at a time.
- Load `KPipeline` **once** in the worker and reuse across all jobs (loading is the slow part).
- Update the job record on each `progress_cb` so `GET /api/jobs/{id}` reflects live progress.
- **Persistence across restarts:** write a `manifest.json` into each book's output dir
  (id, title, source, voice, status, chapters). On startup, scan `out/` and rebuild the
  in-memory library from manifests. No database server.

---

## 4. Cue data for the player
The browser player needs timing. Don't parse SRT in JS — have the engine **also emit
`cues.json` per chapter** (it already has the `Cue` list in memory): a JSON array of
`{start, end, text}`. Keep writing `.srt` too (for VLC). VTT optional.

---

## 5. Frontend (PWA, vanilla — no build step)
Plain HTML/CSS/JS (a sprinkle of Alpine.js or htmx is fine). Served as static files by FastAPI.
Three views (single-page, responsive, **touch-first**):

**Submit** — file picker / URL field / paste-text box; voice + speed controls; submit → shows
in Library with a progress indicator.

**Library** — cards for each book: title, source, status/progress, and per book a
**"Download for offline"** button (see §5.1) and delete.

**Player** (the payoff):
- `<audio>` element + chapter selector. Fetch that chapter's `cues.json`.
- On `timeupdate`, binary-search the active cue, highlight it, and **auto-scroll** to keep it
  centered. **Tap any sentence to seek** to its `start`. Big tap targets, readable type, dark mode.
- **Media Session API** (required for phone): set `navigator.mediaSession.metadata` (book/chapter
  title) and action handlers (play/pause/seek/next-prev chapter) so **lock-screen and background
  audio work on iOS/Android**. Without this, audio stops when the phone locks.

### 5.1 Offline (the priority for this user)
- Add `manifest.webmanifest` + a **service worker**. Cache the app shell (HTML/CSS/JS) for
  offline launch ("add to home screen").
- **"Download for offline"** per book: fetch all chapter MP3s + `cues.json` into the **Cache
  Storage API** (or IndexedDB for the audio blobs). The player checks the cache first, falls
  back to network. This is what lets the user listen on the subway with no signal.
- Show a per-book "available offline ✓" state and allow removing the cached copy to free space.

> **HTTPS is mandatory** for service workers, the Media Session API, and "add to home screen".
> Localhost is exempt for dev, but the public deployment must be HTTPS — see §7.

---

## 6. Auth seam (build it, leave it OFF)
Per the user's choice, no auth now. But:
- Read an optional `AUDIOBOOK_TOKEN` env var. If **set**, require it (header `X-Token` or
  `?token=`) on all `/api/*` and `/media/*` routes; if **unset**, allow everything (current default).
- This is ~10 lines of FastAPI dependency. It means the day the public URL leaks, the user sets
  one env var and is protected — no code change. Document this in the README.
- Keep the upload endpoint hardened regardless: enforce a **max upload size**, an **allowed-extension
  whitelist**, and write uploads to a temp path under the output tree (never execute them).

---

## 7. Deployment / access (document, provide a runbook)
- Run: `uvicorn audiobook.server:app --host 0.0.0.0 --port 8000`.
- **Public HTTPS:** recommend **Cloudflare Tunnel** (`cloudflared tunnel --url http://localhost:8000`)
  — gives a public HTTPS URL with valid TLS, no ports opened on the box, satisfies the PWA/HTTPS
  requirement for free. (Tailscale Funnel or a Caddy reverse proxy with TLS are alternatives.)
- Put the exact commands in a short `RUNBOOK.md` so the user can start server + tunnel in two steps.

---

## 8. Verification (show evidence)
1. **Engine parity:** `generate_audiobook` produces byte-for-byte the same chapter MP3s/SRT as
   the current CLI on `trading_psychology.txt` and Alice EPUB (no regression from the refactor).
2. **Job lifecycle:** POST a TXT job → poll `GET /api/jobs/{id}` and observe
   `queued→running→done` with progress incrementing per chapter; media URLs resolve and play.
3. **URL job:** POST `{"url": "<real article>"}` → playable result, clean prose (no nav junk).
4. **Player sync:** in a desktop browser, confirm the highlighted sentence tracks the audio and
   tapping a sentence seeks correctly. Last cue end within ~0.3s of audio duration.
5. **PWA/offline:** Lighthouse PWA check passes; "Download for offline" then **kill the network
   (DevTools offline)** and confirm the book still plays from cache.
6. **Mobile:** on a real phone over the HTTPS tunnel — add to home screen, lock the phone, confirm
   audio keeps playing and lock-screen controls (play/pause/seek) work (Media Session).
7. **Auth seam:** with `AUDIOBOOK_TOKEN` unset everything works; with it set, requests without the
   token get 401 and with it get 200.

## 9. Out of scope (note, don't build)
- Multi-user accounts, real login/OAuth, RSS auto-podcast, `.m4b` chapters, the LLM rewrite pass.
- Multi-GPU / parallel jobs (one worker is correct for a single GPU).

## Conventions
- One engine code path (CLI + server share `generate_audiobook`). Small, pure functions.
- No npm/build step for the frontend. Fail loudly with clear messages. Keep the auth and offline
  seams clean so each future phase is additive.
