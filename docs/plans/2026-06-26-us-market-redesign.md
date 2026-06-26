# US-Market Audiobook Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the existing app into a minimal premium US-market audiobook creation platform.

**Architecture:** Keep the current single-page Alpine.js app in `audiobook/static/index.html`. Add design tokens, replace the old visual identity, modernize Create and Library markup, and keep backend API contracts unchanged.

**Tech Stack:** Alpine.js CDN, Tailwind CDN, vanilla CSS, existing FastAPI static serving, existing service worker.

---

### Task 1: Add Redesign Regression Tests

**Files:**
- Modify: `test_ui_polish.py`

**Step 1: Write the failing test**

Add tests that assert the redesigned UI contract:

```python
def test_us_market_branding_removed_cjk_identity():
    forbidden = ["font-brush", "Zhi Mang Xing", "Noto Serif SC", "書", "藏", "sealChar", "text-seal"]
    for token in forbidden:
        assert token not in INDEX


def test_create_flow_is_tabbed_and_plain_language():
    for text in [
        "Create an audiobook",
        "Upload a document, paste text, or add an article URL",
        "Article URL",
        "Upload File",
        "Paste Text",
        "Drop a file here or click to browse",
        "Supported: PDF, EPUB, TXT, DOCX",
        "Only upload content you own or have permission to convert.",
    ]:
        assert text in INDEX


def test_narration_settings_are_consumer_friendly():
    for text in [
        "Narration settings",
        "Ava — Warm female voice",
        "Noah — Clear male voice",
        "Read numbers and currency naturally",
        "0.8x",
        "1.0x",
        "1.2x",
        "1.5x",
        "Create Audiobook",
        "Creating audiobook...",
    ]:
        assert text in INDEX


def test_library_is_modern_saas_copy():
    for text in [
        "Your generated audiobooks.",
        "+ New Audiobook",
        "Search audiobooks",
        "No audiobooks yet",
        "Create your first audiobook from a PDF, EPUB, article, or pasted text.",
        "status-badge",
        "audiobook-card",
        "cover-waveform",
    ]:
        assert text in INDEX
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python test_ui_polish.py`

Expected: FAIL because old UI tokens still exist and new redesign markers are missing.

### Task 2: Redesign Static UI

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add design tokens and modern base styles**

Replace old paper/ink/seal styling with CSS variables for the supplied palette. Remove brush/CJK fonts and replace global form overrides with component-scoped controls.

**Step 2: Replace header identity**

Use an inline SVG book/audio mark and clean `Audiobook` wordmark. Keep `Create`, `Library`, and avatar controls.

**Step 3: Redesign Create page**

Add Alpine state for `inputMethod`, `selectedFileName`, `selectedFileSize`, `searchQuery`, and helper methods. Replace stacked `or` sections with tabs and method-specific panels.

**Step 4: Redesign narration controls**

Use friendly voice option labels and speed segmented buttons that write to the existing `jobForm.speed`.

**Step 5: Redesign Library**

Replace old Library heading/copy, add search input, and update cards with modern covers, metadata, status badges, and clear actions.

**Step 6: Remove old cover seal logic**

Delete `sealChar`. Update `coverStyle` comment and palette to modern non-CJK generated covers.

### Task 3: Bump Service Worker Version

**Files:**
- Modify: `audiobook/static/sw.js`

Change `CACHE_NAME` from `audiobook-app-v13` to `audiobook-app-v14`.

### Task 4: Verify

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

- UI tests pass.
- Offline retention tests pass.
- Normalizer tests pass.
- Compile has no output and exits 0.
- Both curl checks return `200`.

