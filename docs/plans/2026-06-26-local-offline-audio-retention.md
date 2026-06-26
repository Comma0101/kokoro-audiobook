# Local Offline Audio Retention Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep generated audiobook files local on the user's device after **Save Offline**, then expire the server copy faster.

**Architecture:** Keep MP3 and cues storage in browser Cache Storage. Improve the existing Alpine UI flow to guide users to save offline, verify the cache after download, and preserve local playback even after the server copy expires. Update the existing FastAPI endpoint to shorten server retention to 1 hour after verified local save.

**Tech Stack:** FastAPI, SQLite, vanilla Alpine.js, browser Cache Storage API, service worker.

---

### Task 1: Shorten Server Retention After Local Save

**Files:**
- Modify: `audiobook/server.py`

**Step 1: Inspect the current endpoint**

Find `mark_local_saved()` in `audiobook/server.py`.

Expected current behavior:

```python
expires_at = now_ts + (24 * 60 * 60) # 24 hr grace
```

**Step 2: Change retention to 1 hour**

Replace the 24-hour grace period with:

```python
expires_at = now_ts + (60 * 60) # 1 hour grace after verified local save
```

**Step 3: Verify with a syntax check**

Run:

```bash
.venv/bin/python -m compileall -q audiobook
```

Expected: no output and exit code 0.

---

### Task 2: Add Clear Save Offline Guidance

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add simple state fields**

Inside `appData()`, add:

```js
offlineSavingId: null,
offlineSavingDone: 0,
offlineSavingTotal: 0,
```

**Step 2: Improve Library action text**

When a ready book is not saved and server copy exists, show a prominent `Save Offline` action. While saving, show:

```text
Saving {offlineSavingDone}/{offlineSavingTotal}
```

When complete, keep showing:

```text
Saved on This Device
```

**Step 3: Add Player prompt**

In the Player controls, if the active book is ready but not offline and the server copy exists, show a small button:

```text
Save Offline
```

Clicking it calls `downloadOffline(activeJob)`.

---

### Task 3: Verify Cache Completeness Before Marking Saved

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Update `downloadOffline(job)` progress**

Before downloads:

```js
this.offlineSavingId = job.id;
this.offlineSavingDone = 0;
this.offlineSavingTotal = job.progress.chapters.length * 2;
```

After each successful `cache.put(...)`, increment `offlineSavingDone`.

**Step 2: Verify all files exist**

After downloads complete, loop over every expected URL and call:

```js
const match = await cache.match(url);
if (!match) throw new Error(`Cache verification failed for ${url}`);
```

Only after this verification should the client call:

```js
await fetch(`/api/books/${job.id}/local-saved`, reqOpt('POST'));
```

**Step 3: Reset progress in a `finally` block**

Ensure saving state returns to idle even if a download fails:

```js
finally {
  this.offlineSavingId = null;
  this.offlineSavingDone = 0;
  this.offlineSavingTotal = 0;
}
```

---

### Task 4: Keep Expired Server Books Playable If Cached

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Relax `openPlayer(job)`**

Current behavior blocks all `Server Copy Expired` books. Change it so it only blocks when the book is both expired and not cached:

```js
if (job.device_state === 'Server Copy Expired' && !job.is_offline) {
  alert("The audio files have expired from the server and are not saved on this device. Please delete and regenerate this volume.");
  return;
}
```

**Step 2: Verify offline fetch path still matches the service worker**

The player should continue appending `?u={user_id}` to media URLs. The service worker strips the query and checks Cache Storage by pathname, which matches the offline cache keys.

---

### Task 5: Manual Verification

**Files:**
- No code files.

**Step 1: Compile**

Run:

```bash
.venv/bin/python -m compileall -q audiobook
```

Expected: pass.

**Step 2: HTTP smoke check**

Run with server active:

```bash
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -sS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/sw.js
```

Expected: both return `200`.

**Step 3: Browser check**

In the PWA:

- Generate or use a ready book.
- Confirm `Save Offline` is visible.
- Tap `Save Offline`.
- Confirm progress increments.
- Confirm final state is `Saved on This Device`.
- Confirm the book still opens and plays.

**Step 4: Database retention check**

After saving offline, verify `server_expires_at` is roughly 1 hour from current time for that book.
