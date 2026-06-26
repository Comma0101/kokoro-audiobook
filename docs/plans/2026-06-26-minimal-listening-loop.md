# Minimal Listening Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the minimal audiobook loop by polishing Library actions, Player behavior, local resume listening, generation status, and failure recovery.

**Architecture:** Keep the current Alpine/Tailwind single-page app in `audiobook/static/index.html`. Store resume progress in `localStorage` per user/book, avoid backend schema changes, and keep service worker media caching unchanged except for a cache-version bump when the app shell changes.

**Tech Stack:** Alpine.js CDN, Tailwind CDN, vanilla CSS, FastAPI static app, browser `localStorage`, existing audio/cues APIs.

---

### Task 1: Add UI Contract Tests

**Files:**
- Modify: `test_ui_polish.py`

**Step 1: Write failing tests**

Add tests for the minimal listening loop markers:

```python
def test_resume_listening_ui_contract():
    for text in [
        "savePlaybackPosition",
        "getPlaybackPosition",
        "clearPlaybackPosition",
        "Continue Listening",
        "Start Listening",
        "progressLabel(job)",
    ]:
        assert text in INDEX


def test_player_has_minimal_audiobook_controls():
    for text in [
        "Rewind 15 seconds",
        "Forward 30 seconds",
        "Chapter",
        "Save Offline to This Device",
    ]:
        assert text in INDEX


def test_failure_recovery_copy_exists():
    for text in [
        "We couldn’t create this audiobook",
        "Try a TXT, DOCX, or paste the text.",
        "Try again",
        "Paste text instead",
    ]:
        assert text in INDEX
```

**Step 2: Run the test**

Run:

```bash
.venv/bin/python test_ui_polish.py
```

Expected: FAIL because resume helpers and failure recovery copy are not implemented yet.

### Task 2: Add Local Resume State

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add helper methods**

Add Alpine helpers:

```js
playbackKey(jobId) {
  const user = this.currentUser?.id || this.currentUser?.email || 'anonymous';
  return `audiobook-position-${user}-${jobId}`;
},

getPlaybackPosition(job) {
  if (!job) return null;
  try {
    return JSON.parse(localStorage.getItem(this.playbackKey(job.id)) || 'null');
  } catch (e) {
    return null;
  }
},

savePlaybackPosition() {
  if (!this.activeJob) return;
  const audioEl = document.getElementById('audioEl');
  if (!audioEl || !Number.isFinite(audioEl.currentTime)) return;
  localStorage.setItem(this.playbackKey(this.activeJob.id), JSON.stringify({
    chapterIdx: this.activeChapterIdx,
    currentTime: audioEl.currentTime,
    updatedAt: Date.now()
  }));
},

clearPlaybackPosition(job) {
  if (job) localStorage.removeItem(this.playbackKey(job.id));
}
```

**Step 2: Save progress during playback**

Call `savePlaybackPosition()` from `onTimeUpdate()` after cue sync logic. Throttle if needed only if testing shows performance issues; otherwise keep it simple.

**Step 3: Restore progress in `openPlayer(job)`**

When opening a ready job, read `getPlaybackPosition(job)` and set `activeChapterIdx` before `loadChapter()`.

**Step 4: Seek after metadata loads**

In `loadChapter()`, after assigning `audioEl.src`, if the saved position matches `activeChapterIdx`, set `audioEl.currentTime`.

### Task 3: Update Library Card Actions

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add labels**

Update `bookCardActionLabel(job)`:

```js
if (job.status === 'failed') return 'Try again';
if (job.status === 'queued' || job.status === 'processing') return 'View status';
if (this.getPlaybackPosition(job)) return 'Continue Listening';
return 'Start Listening';
```

**Step 2: Add `progressLabel(job)`**

Use duration and saved current time when available:

```js
progressLabel(job) {
  const pos = this.getPlaybackPosition(job);
  if (!pos || !job.duration_seconds) return '';
  const pct = Math.min(99, Math.max(1, Math.round((pos.currentTime / job.duration_seconds) * 100)));
  return `${pct}% complete`;
}
```

Keep this device-local and honest. If chapter-level duration makes total progress inaccurate, show `In progress` instead.

**Step 3: Show progress on card**

Under metadata, show `progressLabel(job)` when present.

### Task 4: Improve Player Controls

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add skip buttons**

Add two small buttons near the player controls:

```html
<button @click="skipBy(-15)" aria-label="Rewind 15 seconds">15s</button>
<button @click="skipBy(30)" aria-label="Forward 30 seconds">30s</button>
```

**Step 2: Add helper**

```js
skipBy(seconds) {
  const audioEl = document.getElementById('audioEl');
  if (!audioEl) return;
  audioEl.currentTime = Math.max(0, Math.min(audioEl.duration || Infinity, audioEl.currentTime + seconds));
  this.savePlaybackPosition();
}
```

### Task 5: Add Failure Recovery Copy

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add helper**

```js
failureDetail(job) {
  if (!job || job.status !== 'failed') return '';
  return 'We couldn’t create this audiobook. Try a TXT, DOCX, or paste the text.';
}
```

**Step 2: Show recovery actions**

On failed cards, show:

- `Try again` button that switches to Create.
- `Paste text instead` secondary button that sets `inputMethod = 'text'` and switches to Create.

No retry backend endpoint is needed for this milestone.

### Task 6: Bump Service Worker Cache

**Files:**
- Modify: `audiobook/static/sw.js`
- Modify: `test_ui_polish.py`

Increment the app shell cache version, for example from `audiobook-app-v19` to `audiobook-app-v20`, and update the test.

### Task 7: Verify

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/
curl -sS http://localhost:8000/sw.js | head -n 1
```

Expected:

- All Python test scripts pass.
- Compileall and HTML structure checks exit 0.
- App returns `200`.
- Service worker reports the new cache version.

