# UI/UX Redundancy Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Delete redundant UI surfaces and simplify duplicate labels without changing backend behavior.

**Architecture:** Keep the single static Alpine page. Remove redundant markup and helpers from `audiobook/static/index.html`, update string-contract tests in `test_ui_polish.py`, and bump the service worker cache.

**Tech Stack:** Static HTML/CSS, Alpine.js CDN, Python string-contract tests.

---

### Task 1: Add Cleanup Contract Tests

**Files:**
- Modify: `test_ui_polish.py`

Add tests that assert these duplicate surfaces are gone:

- `voiceSelectNoScript` and `<noscript>`
- `coverStatusLabel(job)` and `cover-status`
- `Default Playback Speed` and `Preferences`
- saved offline secondary action should say `Remove Offline Copy`
- service worker cache should be `audiobook-app-v24`

Run `.venv/bin/python test_ui_polish.py` and confirm it fails before implementation.

### Task 2: Delete Redundant Create Fallback

**Files:**
- Modify: `audiobook/static/index.html`

Remove the `noscript` narration fallback block. The app requires JavaScript for auth, Alpine, upload, and playback; this fallback is not useful.

### Task 3: Delete Duplicate Cover Status

**Files:**
- Modify: `audiobook/static/index.html`

Remove the `.cover-status` CSS rule, cover status markup, and `coverStatusLabel(job)` helper. Keep the card badge as the only status surface.

### Task 4: Remove Duplicate Profile Speed Preference

**Files:**
- Modify: `audiobook/static/index.html`

Remove the Profile `Preferences` section and `Default Playback Speed` select. Keep speed control in the Player only.

### Task 5: Simplify Offline Secondary Action

**Files:**
- Modify: `audiobook/static/index.html`

Change `bookPrimaryActionLabel(job)` so offline books show `Remove Offline Copy`. Keep the saved/offline status in the badge and metadata.

### Task 6: Bump Service Worker Cache

**Files:**
- Modify: `audiobook/static/sw.js`
- Modify: `test_ui_polish.py`

Bump `audiobook-app-v23` to `audiobook-app-v24`.

### Task 7: Verify

Run:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python -m compileall -q audiobook
xmllint --html --noout audiobook/static/index.html
curl -sS -o /dev/null -w "%{http_code}\n" http://localhost:8000/
curl -sS http://localhost:8000/sw.js
```
