# Accurate Local Resume Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve local `Continue Listening` accuracy without backend changes or player rewrites.

**Architecture:** Extend the existing Alpine app in `audiobook/static/index.html`. Store a versioned localStorage resume object keyed by user/book, save on additional browser/player events, restore by chapter file with a small rewind, and show a concise Library resume label.

**Tech Stack:** Alpine.js CDN, native HTML audio, browser `localStorage`, existing Python string-contract tests.

---

### Task 1: Add UI Contract Tests

**Files:**
- Modify: `test_ui_polish.py`

**Step 1: Write the failing tests**

Add two tests:

```python
def test_resume_saves_on_player_lifecycle_events():
    for text in [
        '@pause="savePlaybackPosition()"',
        '@seeked="savePlaybackPosition()"',
        '@canplay="restorePlaybackPosition()"',
        "window.addEventListener('pagehide'",
        "document.addEventListener('visibilitychange'",
    ]:
        assert text in INDEX


def test_resume_restores_with_context_and_rewind():
    for text in [
        "resumeRewindSeconds: 3",
        "chapterFile",
        "resolvePlaybackChapterIdx(job, pos)",
        "restorePlaybackPosition()",
        "positionSummary(job)",
        "Continue from",
    ]:
        assert text in INDEX
```

**Step 2: Run the failing test**

Run:

```bash
.venv/bin/python test_ui_polish.py
```

Expected: FAIL because these lifecycle hooks and helpers do not exist yet.

### Task 2: Save Position More Reliably

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add app state**

Add:

```js
resumeRewindSeconds: 3,
pendingResumePosition: null,
resumeAppliedForSrc: '',
```

**Step 2: Store richer resume payload**

Update `savePlaybackPosition()` to write:

```js
{
  version: 2,
  chapterIdx,
  chapterFile: chapter?.mp3 || '',
  currentTime,
  updatedAt: Date.now()
}
```

Ignore invalid values and very short starts.

**Step 3: Add lifecycle listeners**

During `init()`, add:

```js
window.addEventListener('pagehide', () => this.savePlaybackPosition());
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') this.savePlaybackPosition();
});
```

### Task 3: Restore by Chapter File and Rewind

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add `resolvePlaybackChapterIdx(job, pos)`**

Match `pos.chapterFile` against `job.progress.chapters[].mp3`. If no match, use a valid `pos.chapterIdx`. Otherwise return `0`.

**Step 2: Add `restorePlaybackPosition()`**

Use `pendingResumePosition`. If it matches the active chapter, seek to:

```js
Math.max(0, pos.currentTime - this.resumeRewindSeconds)
```

Make it safe to call from both `loadedmetadata` and `canplay`.

**Step 3: Wire restore into player load**

In `openPlayer(job)`, set `pendingResumePosition` and choose the chapter via `resolvePlaybackChapterIdx`.

In `loadChapter()`, reset `resumeAppliedForSrc`, set `audioEl.onloadedmetadata`, and call `restorePlaybackPosition()`.

In the `<audio>` element, add:

```html
@pause="savePlaybackPosition()"
@seeked="savePlaybackPosition()"
@canplay="restorePlaybackPosition()"
```

### Task 4: Improve Library Resume Copy

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add `formatClock(seconds)`**

Return `m:ss` for short values and `h:mm:ss` for long values.

**Step 2: Add `positionSummary(job)`**

Return:

```text
Continue from Chapter 4 · 12:31
```

Use chapter `index` when available, otherwise `chapterIdx + 1`.

**Step 3: Show summary on Library cards**

Prefer `positionSummary(job)` over the generic percent label when resume exists.

### Task 5: Verify

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/
curl -sS http://localhost:8000/sw.js
```

Expected:

- UI polish tests pass.
- Offline retention tests pass.
- Compile and HTML checks pass.
- App returns `200`.
- Served service worker remains current.
