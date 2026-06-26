# Production Readiness Implementation Plan

Date: 2026-06-26

## Scope

Implement production plumbing for the existing audiobook app while preserving the current user-facing feature set.

Primary outcome:

```text
same app experience, safer backend, clear rollback path
```

## Milestone 0: Baseline And Safety Snapshot

### Changes

- Record current app behavior and test status.
- Back up the SQLite database before any migration.
- Back up source files if the project is not in its own Git branch.
- Capture a local benchmark using a known text input.

### Verification

Run the current test set:

```bash
.venv/bin/python test_ui_polish.py
.venv/bin/python test_offline_retention.py
.venv/bin/python test_docx_support.py
.venv/bin/python test_norm.py
.venv/bin/python -m compileall -q audiobook
```

Record:

```text
input size
audio duration
generation wall time
real-time factor
peak disk size under out/
GPU model
VRAM use if available
```

### Rollback

No application changes in this milestone.

## Milestone 1: Config And Tests

### Changes

- Add a small config helper for production-readiness flags.
- Add tests for config defaults and environment overrides.
- Do not change runtime behavior yet.

### Verification

Tests should confirm:

- current local defaults still allow simple development
- queue limits are disabled unless enabled
- stale recovery is disabled unless enabled
- FP16 is disabled unless enabled

### Rollback

Remove the config helper and tests. No database or behavior changes.

## Milestone 2: Separate Worker Module

### Changes

- Move the existing job loop out of `audiobook/server.py` into `audiobook/worker.py`.
- Keep a small startup hook in `server.py` that can still start the worker in-process when `START_INPROCESS_WORKER=1`.
- Add a command entry path so the worker can run separately:

```bash
.venv/bin/python -m audiobook.worker
```

- Keep cleanup loop callable from either process, but run it in only one place by config.

### Verification

Run in current-compatible mode:

```text
START_INPROCESS_WORKER=1
```

Then run production-style local mode:

```text
Terminal 1: START_INPROCESS_WORKER=0 .venv/bin/uvicorn audiobook.server:app --host 127.0.0.1 --port 8000
Terminal 2: WORKER_ENABLED=1 .venv/bin/python -m audiobook.worker
```

Verify:

- create job works
- worker claims job
- progress updates
- job becomes ready
- web server remains responsive while generation runs

### Rollback

Set:

```text
START_INPROCESS_WORKER=1
```

If needed, revert only the worker extraction files. No database changes required in this milestone.

## Milestone 3: Stuck Job Recovery

### Changes

Add additive columns to `books`:

```text
worker_id
processing_started_at
heartbeat_at
attempt_count
last_error_at
```

Update job claim behavior:

- claim sets `worker_id`
- claim sets `processing_started_at`
- claim sets `heartbeat_at`
- claim increments `attempt_count`

Update worker progress:

- heartbeat updates during long generation
- ready/failed clears active worker metadata where useful

Add stale recovery:

- if `status='processing'` and heartbeat is older than `JOB_STALE_AFTER_SECONDS`, requeue the job
- if attempts exceed `JOB_MAX_ATTEMPTS`, mark failed with a recovery error

Gate recovery behind:

```text
RECOVER_STALE_JOBS=1
```

### Verification

Tests:

- queued job can be claimed by a worker
- processing job with fresh heartbeat is not touched
- stale processing job is requeued
- stale job over max attempts becomes failed

Manual:

- start a generation
- kill the worker process
- wait for stale threshold
- start worker again
- confirm job is retried or failed cleanly instead of staying stuck forever

### Rollback

Set:

```text
RECOVER_STALE_JOBS=0
```

The new database columns are harmless if unused.

## Milestone 4: Queue And Abuse Limits

### Changes

Before inserting a new book job, enforce configurable limits:

```text
MAX_ACTIVE_JOBS_PER_USER
MAX_GLOBAL_QUEUED_JOBS
MIN_CREATE_INTERVAL_SECONDS
```

Active means:

```text
queued + processing
```

Return HTTP 429 with clear copy when limits are hit:

```text
You already have an audiobook being created. Please wait for it to finish before starting another.
```

Gate behind:

```text
ENFORCE_QUEUE_LIMITS=1
```

### Verification

Tests:

- user under limit can create a job
- user over active-job limit receives 429
- global queue limit receives 429
- disabling `ENFORCE_QUEUE_LIMITS` restores old behavior

Manual:

- submit multiple jobs quickly from the same account
- confirm only the allowed number are accepted

### Rollback

Set:

```text
ENFORCE_QUEUE_LIMITS=0
```

## Milestone 5: Disk Retention Guardrails

### Changes

Keep existing behavior:

- normal server copy expiry
- faster expiry after local offline save

Add guardrails:

- delete expired server copies reliably
- remove orphan uploads older than `ORPHAN_UPLOAD_TTL_SECONDS`
- optionally delete oldest server copies under disk pressure
- never delete source files for currently processing jobs

Gate disk pressure cleanup behind:

```text
ENABLE_DISK_PRESSURE_CLEANUP=1
```

Config:

```text
OUT_DIR_MAX_BYTES
MIN_FREE_DISK_BYTES
ORPHAN_UPLOAD_TTL_SECONDS
```

### Verification

Tests:

- expired ready audiobook server files are deleted
- local-saved files expire according to the shorter grace period
- processing job files are not deleted
- orphan upload older than TTL is deleted
- disk pressure cleanup is inactive when disabled

Manual:

- create a local-saved audiobook
- confirm server copy expires faster
- confirm Library still shows local/offline status correctly

### Rollback

Set:

```text
ENABLE_DISK_PRESSURE_CLEANUP=0
```

Existing expiry behavior can remain.

## Milestone 6: Performance Metrics

### Changes

Record practical generation metrics in logs and optionally `progress_meta`:

```text
generation_started_at
generation_finished_at
generation_seconds
audio_duration_seconds
real_time_factor
text_char_count
chunk_count
output_bytes
error_type
```

Add a lightweight benchmark script or manual command that can run the same input repeatedly.

### Verification

Run at least two benchmark books:

- short input: 5-10 minutes estimated audio
- long input: 1+ hour estimated audio

Record:

```text
RTF = generation_seconds / audio_duration_seconds
```

### Rollback

Metrics are passive. If they create noise or break serialization, remove only the metrics writes.

## Milestone 7: Optional FP16 Experiment

### Changes

Add an experiment flag:

```text
ENABLE_FP16=1
```

Only try this after the worker split, recovery, queue limits, cleanup, and metrics are stable.

This milestone is not required before first deployment.

### Verification

Compare against baseline:

- output quality by listening test
- generation speed
- VRAM use
- failure rate

### Rollback

Set:

```text
ENABLE_FP16=0
```

## Release Gates

Do not deploy to cloud until these pass locally:

- web server and worker run as separate processes
- killed worker does not leave permanent zombie jobs
- user cannot queue unlimited jobs
- expired server copies are cleaned
- local offline saved copy behavior still works
- test suite passes
- at least one long audiobook benchmark completes

## Cloud Decision Gate

After local validation, run one small cloud benchmark only.

Compare:

```text
local RTX 4070 Super generation time
cloud GPU generation time
cloud hourly cost
expected concurrent users
average audiobook duration
```

Do not rent always-on cloud GPU capacity until local metrics show the real bottleneck.

## Implementation Order

Recommended order:

1. Milestone 0: Baseline and backup.
2. Milestone 1: Config and tests.
3. Milestone 2: Worker split.
4. Milestone 3: Stuck job recovery.
5. Milestone 4: Queue limits.
6. Milestone 5: Disk guardrails.
7. Milestone 6: Metrics.
8. Milestone 7: FP16 experiment only if needed.

Stop after each milestone and verify before continuing.
