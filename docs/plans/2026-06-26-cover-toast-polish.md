# Cover and Offline Toast Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve generated book covers and replace the offline-save success alert with a non-blocking in-app confirmation.

**Architecture:** Keep all changes inside the static Alpine app. Covers remain CSS generated from title. Offline save still writes MP3 and cue files to Cache Storage, but normal success uses a toast instead of `alert()`.

**Tech Stack:** Alpine.js, Tailwind CDN, static HTML/CSS/JS, browser Cache Storage API, service worker.

---

### Task 1: Extend UI Regression Checks

**Files:**
- Modify: `test_ui_polish.py`

**Step 1: Add tests for toast and cover polish**

Add assertions that `audiobook/static/index.html` contains:

```python
assert "toast: null" in INDEX
assert "showToast(" in INDEX
assert "Stored on this device" in INDEX
assert "All audio and cues verified." in INDEX
assert "coverStatusLabel(job)" in INDEX
assert "book-spine" in INDEX
```

Add assertion that `audiobook/static/sw.js` contains:

```python
assert "audiobook-app-v13" in SW
```

**Step 2: Run the test before implementation**

Run:

```bash
.venv/bin/python test_ui_polish.py
```

Expected: fail until the UI and service worker changes are implemented.

---

### Task 2: Add In-App Toast

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add toast state**

Inside `appData()`, add:

```js
toast: null,
toastTimer: null,
```

**Step 2: Add toast markup**

Near the end of `<main>`, before the closing `</main>`, add a fixed toast:

```html
<div x-show="toast" x-transition class="fixed left-4 right-4 bottom-6 z-[80] mx-auto max-w-sm border border-ink/10 bg-paper shadow-xl px-4 py-3">
  <div class="text-sm font-bold text-ink" x-text="toast?.title"></div>
  <div class="mt-1 text-xs text-inkLight" x-text="toast?.detail"></div>
  <div class="mt-1 text-[10px] font-bold uppercase tracking-widest text-accent" x-text="toast?.meta"></div>
</div>
```

**Step 3: Add helper**

Add:

```js
showToast(title, detail='', meta='') {
  this.toast = { title, detail, meta };
  clearTimeout(this.toastTimer);
  this.toastTimer = setTimeout(() => { this.toast = null; }, 4200);
},
```

**Step 4: Replace success alert**

In `downloadOffline(job)`, replace:

```js
alert("Saved for offline listening.");
```

with:

```js
this.showToast('Stored on this device', `${this.formatDuration(job.duration_seconds)} saved locally`, 'All audio and cues verified.');
```

Keep error alerts unchanged.

---

### Task 3: Improve Generated Cover Styling

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Update cover markup**

Inside `.book-cover`, add:

```html
<div class="book-spine"></div>
<div class="cover-status" x-text="coverStatusLabel(job)"></div>
```

**Step 2: Add cover status helper**

Add:

```js
coverStatusLabel(job) {
  if (!job) return '';
  if (job.is_offline) return 'LOCAL';
  if (job.device_state === 'Server Copy Expired') return 'EXPIRED';
  if (job.status === 'ready') return 'READY';
  if (job.status === 'processing') return 'MAKING';
  if (job.status === 'queued') return 'QUEUED';
  if (job.status === 'failed') return 'FAILED';
  return '';
},
```

**Step 3: Tune CSS**

Update the existing cover classes:

- Make `.book-cover` slightly cleaner and less muddy.
- Add `.book-spine`.
- Add `.cover-status`.
- Reduce `.seal` dominance.
- Improve title wrapping and readability.

Use existing palette variables and do not introduce a new dominant color family.

---

### Task 4: Bump Service Worker Version

**Files:**
- Modify: `audiobook/static/sw.js`

**Step 1: Update cache version**

Change:

```js
const CACHE_NAME = 'audiobook-app-v12';
```

to:

```js
const CACHE_NAME = 'audiobook-app-v13';
```

---

### Task 5: Verification

**Files:**
- No code files.

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/sw.js
```

Expected:

- All Python checks pass.
- Compile command has no output and exit code 0.
- Both curl commands return `200`.
