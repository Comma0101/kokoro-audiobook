# Production Checklist

Use this as the launch gate before opening the audiobook app beyond private beta.

## 1. Source Control

- [ ] `main` is clean: `git status --short` returns no changes.
- [ ] Latest UI and production-readiness changes are committed.
- [ ] The deployed commit hash is recorded.
- [ ] A rollback commit or tag is identified before deployment.

## 2. Required Secrets And Domains

- [ ] `firebase-adminsdk.json` exists on the host and is not committed.
- [ ] Firebase Authentication authorized domains include the production domain.
- [ ] Google sign-in works on the production HTTPS URL.
- [ ] Phone sign-in works or is intentionally disabled.
- [ ] Any public URL uses HTTPS.
- [ ] `ALLOWED_ORIGINS` is set if the production domain differs from local development.

## 3. Production Process Model

Run the API and worker as separate processes.

API process:

```bash
START_INPROCESS_WORKER=0 .venv/bin/python -m uvicorn audiobook.server:app --host 0.0.0.0 --port 8000
```

Worker process:

```bash
WORKER_ENABLED=1 RECOVER_STALE_JOBS=1 .venv/bin/python -m audiobook.worker
```

- [ ] API process is supervised and restarts on failure.
- [ ] Worker process is supervised and restarts on failure.
- [ ] Only one cleanup loop is active per deployment.
- [ ] A killed worker does not freeze the API process.
- [ ] Stale processing jobs are recovered after `JOB_STALE_AFTER_SECONDS`.

## 4. Queue And Abuse Limits

Recommended initial production values:

```text
ENFORCE_QUEUE_LIMITS=1
MAX_ACTIVE_JOBS_PER_USER=1
MAX_GLOBAL_QUEUED_JOBS=10
MIN_CREATE_INTERVAL_SECONDS=30
MAX_UPLOAD_BYTES=2147483648
MAX_TEXT_BYTES=52428800
URL_FETCH_MAX_BYTES=5242880
URL_FETCH_MAX_REDIRECTS=5
JOB_MAX_ATTEMPTS=3
```

- [ ] One user cannot queue unlimited jobs.
- [ ] Upload size limits are appropriate for the host disk.
- [ ] URL import limits are enabled.
- [ ] Failed jobs show recoverable UI copy.

## 5. Storage And Cleanup

Recommended initial values:

```text
ENABLE_DISK_PRESSURE_CLEANUP=1
MIN_FREE_DISK_BYTES=10737418240
ORPHAN_UPLOAD_TTL_SECONDS=86400
```

- [ ] Server output directory is on a disk with enough free space.
- [ ] Server copy expiration policy is confirmed.
- [ ] Offline device copy behavior is tested in browser Cache Storage.
- [ ] Expired server copies are removed.
- [ ] Old orphan uploads are removed.
- [ ] Disk pressure cleanup is tested before public launch.

## 6. Verification Commands

Run before each production deploy:

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
```

- [ ] All commands pass on the deploy commit.
- [ ] `curl -I https://<production-domain>/` returns `200`.
- [ ] `/sw.js` serves the current app-shell cache version.

## 7. Staging Smoke Test

- [ ] Create an audiobook from pasted text.
- [ ] Create an audiobook from a small TXT or DOCX file.
- [ ] Create an audiobook from a PDF or EPUB.
- [ ] Generate one 1 to 2 hour audiobook.
- [ ] Generate one 8 to 10 hour audiobook before public launch.
- [ ] Save an audiobook offline on desktop.
- [ ] Save an audiobook offline on iPhone or Android.
- [ ] Close and reopen the app, then continue from the last position.
- [ ] Confirm playback still works after server copy expiration when saved offline.

## 8. Monitoring And Operations

- [ ] API logs are collected.
- [ ] Worker logs are collected.
- [ ] Disk free space is monitored.
- [ ] Queue depth is monitored.
- [ ] Failed job count is monitored.
- [ ] Generation duration and real-time factor are reviewed.
- [ ] CPU, RAM, GPU memory, and GPU utilization are checked during long generation.

## 9. Backup And Rollback

- [ ] SQLite database backup path is defined.
- [ ] Output directory backup policy is defined, or intentionally not backed up.
- [ ] Rollback command is written down.
- [ ] Previous commit deploy has been tested.
- [ ] Recovery from a killed worker has been tested.

## 10. Launch Decision

Private beta is acceptable when:

- [ ] All verification commands pass.
- [ ] API and worker run separately under supervision.
- [ ] Firebase auth works on the production domain.
- [ ] Cleanup is enabled and observed.
- [ ] At least one long audiobook generation completes.
- [ ] Offline save and resume work on a phone.
- [ ] Rollback path is known.

Public launch should wait until:

- [ ] Monitoring is in place.
- [ ] Rate limits have been tested with repeated submissions.
- [ ] Disk pressure behavior is understood.
- [ ] Failure/retry behavior has been observed in staging.
