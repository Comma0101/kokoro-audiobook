# Mobile Create Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign the Create page for mobile users while preserving the existing desktop workflow and backend behavior.

**Architecture:** Keep the single Alpine/Tailwind HTML app in `audiobook/static/index.html`. Add CSS class hooks for mobile-specific layout, use the existing `inputMethod` and `jobForm` state, add one local boolean for expanding narration settings, and keep submit behavior unchanged.

**Tech Stack:** Static HTML, CSS, Alpine.js CDN, existing Python UI contract tests.

---

### Task 1: Add UI Contract Tests

**Files:**
- Modify: `test_ui_polish.py`

**Step 1: Write failing tests**

Add tests for the mobile Create contract:

```python
def test_create_page_has_mobile_first_structure():
    for text in [
        "create-shell",
        "create-copy-mobile",
        "mobile-sticky-create",
        "Upload",
        "Paste",
        "URL",
    ]:
        assert text in INDEX


def test_narration_settings_collapse_on_mobile():
    for text in [
        "settingsCollapsed",
        "settings-summary",
        "Narration",
        "voiceLabel(jobForm.voice)",
        "x-show=\"!settingsCollapsed\"",
    ]:
        assert text in INDEX


def test_mobile_create_css_contract():
    for text in [
        "@media (max-width: 720px)",
        ".create-shell",
        ".mobile-sticky-create",
        "position: fixed",
        "padding-bottom: calc",
    ]:
        assert text in INDEX
```

**Step 2: Run failing test**

Run:

```bash
.venv/bin/python test_ui_polish.py
```

Expected: FAIL because mobile-specific hooks are not implemented yet.

### Task 2: Update Create Markup

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add wrapper classes**

Add classes to the Create section and form:

```html
<section class="page-container create-container create-shell">
<form ... class="create-form space-y-6">
```

**Step 2: Tighten copy and mobile label**

Use shorter mobile copy with class hooks:

```html
<p class="create-copy-mobile ...">Upload, paste, or add a link.</p>
```

Keep the existing fuller copy visible on desktop if useful.

**Step 3: Shorten tab labels on mobile**

Use labels:

```text
Upload
Paste
URL
```

Keep accessible labels via `aria-label` or title if needed.

### Task 3: Collapse Narration Settings on Mobile

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Add state**

Add:

```js
settingsCollapsed: true,
```

**Step 2: Add summary row**

Add a button at the top of the settings card:

```html
<button type="button" class="settings-summary" @click="settingsCollapsed = !settingsCollapsed">
  <span>Narration</span>
  <span x-text="`${voiceLabel(jobForm.voice)} · ${Number(jobForm.speed).toFixed(1)}x`"></span>
</button>
```

**Step 3: Wrap settings controls**

Wrap existing voice/speed/checkbox controls with:

```html
<div x-show="!settingsCollapsed" class="settings-body">
```

Use CSS so this is expanded on desktop.

**Step 4: Add `voiceLabel(id)` helper**

Return `Ava`, `Noah`, or `Emma` for the current voice id.

### Task 4: Add Mobile Sticky CTA

**Files:**
- Modify: `audiobook/static/index.html`

**Step 1: Keep desktop inline CTA**

Add a class to the existing submit button container:

```html
<button ... class="primary-button create-submit-inline w-full">
```

**Step 2: Add mobile sticky CTA inside the form**

Add:

```html
<div class="mobile-sticky-create">
  <button type="submit" class="primary-button w-full" :disabled="submitting || !canSubmit()">
    <span x-text="submitting ? 'Creating audiobook...' : 'Create Audiobook'"></span>
  </button>
</div>
```

Hide it on desktop and hide the inline CTA on mobile.

### Task 5: Add Mobile CSS

**Files:**
- Modify: `audiobook/static/index.html`

Add mobile rules under `@media (max-width: 720px)`:

```css
.create-shell { padding-bottom: calc(96px + env(safe-area-inset-bottom)); }
.create-form { gap: 16px; }
.method-tabs { grid-template-columns: repeat(3, minmax(0, 1fr)); border-radius: 999px; }
.upload-zone { min-height: 156px; padding: 20px; }
.textarea-control { min-height: 180px; }
.settings-summary { display: flex; }
.settings-body { margin-top: 16px; }
.create-submit-inline { display: none; }
.mobile-sticky-create { position: fixed; ... }
```

### Task 6: Bump Service Worker Cache

**Files:**
- Modify: `audiobook/static/sw.js`
- Modify: `test_ui_polish.py`

Bump from `audiobook-app-v21` to `audiobook-app-v22`.

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

Expected: tests pass, HTML validates structurally, server returns `200`, and served service worker shows `audiobook-app-v22`.
