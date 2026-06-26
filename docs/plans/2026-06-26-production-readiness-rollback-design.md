# Production Readiness And Rollback Design

Date: 2026-06-26

## Goal

Harden the existing audiobook app for a small real-user launch without changing the core product experience.

The app should keep the same user-facing flow:

- user adds content
- server extracts/generates audiobook
- user saves audio offline on their device
- server copy expires faster after local save

This plan does not move generation to browser WebGPU, does not redesign the product, and does not require Google Cloud before local validation.

## Current Risk Areas

1. Web server and AI generation run in the same Python process.
   Heavy Kokoro generation can starve or crash the web process.

2. Processing jobs can become stuck.
   If the process restarts mid-generation, a book can remain `processing` forever.

3. The queue is unbounded.
   One user can submit too many jobs and consume GPU time or disk space.

4. Server disk can fill.
   Large MP3 files and uploaded source files need stricter retention and cleanup behavior.

5. Performance is not measured consistently.
   We need real generation time, audio duration, real-time factor, and failure counts before renting cloud GPU capacity.

## Guiding Principles

- Keep changes additive.
- Keep the old behavior available until the new path is proven.
- Use environment flags for every risky behavior change.
- Test on the local RTX 4070 Super machine first.
- Avoid destructive database migrations.
- Do not introduce Redis, Celery, Kubernetes, or browser-side TTS yet.
- Keep SQLite for this version unless local stress tests prove it is the limiting factor.

## Rollback Strategy

Every milestone must have a rollback path.

### Code Rollback

If the project is initialized as its own Git repository, create a branch before implementation:

```bash
git checkout -b production-readiness-v1
```

If this project remains an untracked folder inside a parent repository, create a timestamped backup of the app files before implementation:

```bash
mkdir -p backups
tar --exclude out --exclude .venv --exclude __pycache__ -czf backups/code-2026-06-26-before-prod-readiness.tgz audiobook tests docs
```

### Data Rollback

Before any database migration:

```bash
mkdir -p backups
cp audiobook.db backups/audiobook-2026-06-26-before-prod-readiness.db
```

The migration plan only adds columns and tables. It must not rename or delete existing columns.

### Runtime Rollback

The old in-process worker path remains available during the migration.

Initial flags:

```text
START_INPROCESS_WORKER=1
WORKER_ENABLED=1
RECOVER_STALE_JOBS=0
ENFORCE_QUEUE_LIMITS=0
ENABLE_DISK_PRESSURE_CLEANUP=0
ENABLE_FP16=0
```

Production-style flags after validation:

```text
START_INPROCESS_WORKER=0
WORKER_ENABLED=1
RECOVER_STALE_JOBS=1
ENFORCE_QUEUE_LIMITS=1
ENABLE_DISK_PRESSURE_CLEANUP=1
ENABLE_FP16=0
```

If the separate worker has problems, stop the external worker and set:

```text
START_INPROCESS_WORKER=1
```

If stale job recovery behaves incorrectly, set:

```text
RECOVER_STALE_JOBS=0
```

If rate limits block legitimate testing, set:

```text
ENFORCE_QUEUE_LIMITS=0
```

If disk pressure cleanup is too aggressive, set:

```text
ENABLE_DISK_PRESSURE_CLEANUP=0
```

## Environment Flags

Recommended config surface:

```text
START_INPROCESS_WORKER
WORKER_ENABLED
WORKER_ID
JOB_STALE_AFTER_SECONDS
JOB_MAX_ATTEMPTS
RECOVER_STALE_JOBS

ENFORCE_QUEUE_LIMITS
MAX_ACTIVE_JOBS_PER_USER
MAX_GLOBAL_QUEUED_JOBS
MIN_CREATE_INTERVAL_SECONDS

SERVER_COPY_TTL_SECONDS
LOCAL_SAVED_GRACE_SECONDS
ENABLE_DISK_PRESSURE_CLEANUP
OUT_DIR_MAX_BYTES
MIN_FREE_DISK_BYTES
ORPHAN_UPLOAD_TTL_SECONDS

ENABLE_FP16
BENCHMARK_MODE
```

Defaults should preserve current local behavior as much as possible.

## Target Architecture

### Development Default

```text
FastAPI process
  - serves web UI
  - accepts uploads
  - may run in-process worker for simple local development
  - may run cleanup loop
```

### Production-Style Local Test

```text
Terminal 1: FastAPI web server
Terminal 2: audiobook worker process
```

The worker claims queued jobs from SQLite, generates audio, updates progress, and marks jobs ready or failed.

This gives us most of the production safety benefits without introducing a queue broker.

## Migration Safety

Database migrations should be additive:

```text
books.worker_id TEXT
books.processing_started_at TEXT
books.heartbeat_at TEXT
books.attempt_count INTEGER DEFAULT 0
books.last_error_at TEXT
```

Optional later table:

```text
job_events
  id
  book_id
  event_type
  message
  created_at
```

Avoid the optional events table until logs are not enough.

## Local Validation Before Cloud

The RTX 4070 Super machine is strong enough for this phase.

Validation goals:

- baseline generation speed on current code
- generation speed after worker split
- web server responsiveness while worker generates
- recovery after killing the worker mid-job
- queue limit behavior
- server copy cleanup behavior
- disk usage during and after jobs

Only after those pass should we run a small Google Cloud GPU benchmark.

## What We Are Not Doing Yet

- No browser WebGPU migration.
- No dynamic batching across users.
- No Redis/Celery.
- No Postgres migration.
- No Kubernetes.
- No mobile app packaging.
- No FP16 by default.
- No aggressive streaming-only generation.

Those may become useful later, but they add risk before the basic production plumbing is stable.
