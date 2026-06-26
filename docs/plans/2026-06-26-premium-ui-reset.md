# Premium UI Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Unify Create, Library, and Player into one minimal premium product interface.

**Architecture:** Keep the existing single-file Alpine app and existing product behavior. Replace inconsistent visual treatment with shared tokens, a restrained app header, cleaner page shells, simplified library cards, and a player that reads as a dark listening mode of the same product.

**Tech Stack:** Static HTML/CSS, Alpine.js, Tailwind CDN, existing Python contract tests in `test_ui_polish.py`.

---

### Task 1: Add UI Contract Tests

**Files:**
- Modify: `test_ui_polish.py`

**Steps:**
1. Add tests that assert the premium shell exists: `.app-header`, `.app-container`, `.page-kicker`, `.page-title`, `.avatar-button`.
2. Add tests that assert card cleanup exists: `displayTitle(job)`, `coverDisplayTitle(job)`, `cleanSourceLabel(job)`, `.book-card-title`, `.book-card-meta`.
3. Add tests that assert the player is connected to the same system: `.player-header`, `.player-listening-surface`, `.player-transcript`.
4. Run `.venv/bin/python test_ui_polish.py` and verify the new tests fail.

### Task 2: Unify App Shell

**Files:**
- Modify: `audiobook/static/index.html`

**Steps:**
1. Replace the hard header border and bright avatar with a contained, soft app header.
2. Add shared page container, kicker, and page title classes.
3. Make page titles sans-serif in the application shell; reserve serif for covers/transcript only.

### Task 3: Clean Create and Library

**Files:**
- Modify: `audiobook/static/index.html`

**Steps:**
1. Tighten Create spacing and tabs without changing the workflow.
2. Redesign Library cards into quiet premium product cards.
3. Sanitize display strings so raw URLs and suspicious source suffixes do not dominate covers or titles.

### Task 4: Restrain Player

**Files:**
- Modify: `audiobook/static/index.html`

**Steps:**
1. Hide the global header while player is active.
2. Use a dark warm listening background derived from the same tokens.
3. Reduce transcript size and control-panel drama while preserving custom controls.

### Task 5: Verify

**Files:**
- Test: `test_ui_polish.py`
- Test: existing regression scripts

**Commands:**
```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_norm.py
.venv/bin/python test_chunker.py
.venv/bin/python test_url_source_security.py
.venv/bin/python test_production_readiness.py
.venv/bin/python -m compileall -q audiobook scripts
xmllint --html --noout audiobook/static/index.html
git diff --check
curl -I http://127.0.0.1:8000/
```
