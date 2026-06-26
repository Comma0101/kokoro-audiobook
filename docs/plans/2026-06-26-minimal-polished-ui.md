# Minimal Polished UI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Polish the current Alpine/Tailwind audiobook PWA without adding a frontend build system or larger framework.

**Architecture:** Keep `audiobook/static/index.html` as the single static app and preserve existing Alpine state methods. Make focused markup/style changes for clearer Library, Player, and offline states, then bump the service-worker cache version so users receive the new UI.

**Tech Stack:** FastAPI static files, Alpine.js, Tailwind CDN, vanilla service worker, Cache Storage API.

---

### Task 1: Add UI Regression Checks

**Files:**
- Create: `test_ui_polish.py`
- Read: `audiobook/static/index.html`
- Read: `audiobook/static/sw.js`

**Step 1: Write the failing test**

Create `test_ui_polish.py`:

```python
from pathlib import Path

ROOT = Path(__file__).parent
INDEX = (ROOT / "audiobook" / "static" / "index.html").read_text(encoding="utf-8")
SW = (ROOT / "audiobook" / "static" / "sw.js").read_text(encoding="utf-8")


def test_offline_copy_is_device_specific():
    assert "Save Offline to This Device" in INDEX
    assert "Stored on this device" in INDEX


def test_library_uses_clear_ready_state():
    assert "Ready to Save" in INDEX
    assert "Saved on This Device" in INDEX
    assert "Server Copy Expired" in INDEX


def test_player_has_offline_status_surface():
    assert "activeJobOfflineLabel" in INDEX
    assert "Save this audiobook on this device" in INDEX


def test_service_worker_cache_version_bumped():
    assert "audiobook-app-v12" in SW


if __name__ == "__main__":
    for test in [
        test_offline_copy_is_device_specific,
        test_library_uses_clear_ready_state,
        test_player_has_offline_status_surface,
        test_service_worker_cache_version_bumped,
    ]:
        test()
    print("ui polish tests passed")
```

**Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python test_ui_polish.py
```

Expected: fail before UI copy/version updates.

---

### Task 2: Clarify Library Status and Offline Action

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add helper labels inside `appData()`**

Add methods near `formatDuration()`:

```js
bookStatusLabel(job) {
  if (!job) return '';
  if (this.offlineSavingId === job.id) return `Saving ${this.offlineSavingDone}/${this.offlineSavingTotal}`;
  if (job.status === 'queued') return 'Queued';
  if (job.status === 'processing') return 'Generating';
  if (job.status === 'failed') return 'Failed';
  if (job.is_offline) return 'Stored on this device';
  if (job.device_state === 'Server Copy Expired') return 'Expired';
  if (job.status === 'ready') return 'Ready to Save';
  return job.status || '';
},

bookPrimaryActionLabel(job) {
  if (!job) return '';
  if (this.offlineSavingId === job.id) return `Saving ${this.offlineSavingDone}/${this.offlineSavingTotal}`;
  if (job.is_offline) return 'Stored on this device';
  return 'Save Offline to This Device';
},
```

**Step 2: Use the helper in Library cards**

Replace ad hoc status/action text with `bookStatusLabel(job)` and `bookPrimaryActionLabel(job)`.

**Step 3: Keep behavior unchanged**

Do not change `downloadOffline(job)` behavior except labels.

---

### Task 3: Polish Player Offline Surface

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add active player label helper**

Add:

```js
activeJobOfflineLabel() {
  if (!this.activeJob) return '';
  if (this.activeJob.is_offline) return 'Stored on this device';
  if (this.activeJob.device_state === 'Server Copy Expired') return 'Server copy expired';
  return 'Not stored on this device';
},
```

**Step 2: Show status near Player title**

Under the active book title or chapter selector, show:

```html
<div class="mt-2 text-[11px] font-bold uppercase tracking-widest text-inkLight" x-text="activeJobOfflineLabel()"></div>
```

**Step 3: Update player save prompt copy**

Use:

```text
Save this audiobook on this device for offline listening.
Save Offline to This Device
```

---

### Task 4: Calm the Visual Style Without Rewriting Layout

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Reduce decorative emphasis**

Keep the generated cover but make metadata/action text clearer than decorative seal elements. Avoid adding new images or a landing page.

**Step 2: Improve touch targets**

Ensure Library offline buttons and Player offline button have enough vertical padding:

```html
class="... py-2 ..."
```

**Step 3: Keep palette restrained**

Use existing `paper`, `ink`, `inkLight`, and `accent` colors. Do not introduce a new dominant color theme.

---

### Task 5: Bump Service Worker Cache Version

**Files:**
- Modify: `audiobook/static/sw.js`

**Step 1: Update cache version**

Change:

```js
const CACHE_NAME = 'audiobook-app-v11';
```

to:

```js
const CACHE_NAME = 'audiobook-app-v12';
```

**Step 2: Run tests**

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python -m compileall -q audiobook
```

Expected: all pass.

---

### Task 6: Browser Smoke Check

**Files:**
- No code files.

**Step 1: Check static routes**

Run:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/sw.js
```

Expected: both return `200`.

**Step 2: Manual UI check**

In the browser:

- Library shows clearer status labels.
- Ready books show `Save Offline to This Device`.
- Saved books show `Stored on this device`.
- Player shows the offline state under the book/chapter area.
- Save prompt remains visible only when the active book is not saved and server copy exists.
