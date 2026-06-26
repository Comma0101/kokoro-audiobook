# Audiobook AI - Runbook

## Local Development

Start the FastAPI server on port 8000. By default, local development still starts
the TTS worker in the same process:

```bash
cd /home/comma/Documents/kokoro-audiobook
.venv/bin/python -m uvicorn audiobook.server:app --host 0.0.0.0 --port 8000
```

Open the local UI at `http://localhost:8000`. Google/Firebase sign-in may reject `http://127.0.0.1:8000` unless `127.0.0.1` is added in Firebase Authentication authorized domains.

## Production-Style Local Run

Run the API and worker separately so heavy TTS work cannot freeze the web server:

```bash
cd /home/comma/Documents/kokoro-audiobook

# Terminal 1: API only
START_INPROCESS_WORKER=0 .venv/bin/python -m uvicorn audiobook.server:app --host 0.0.0.0 --port 8000

# Terminal 2: worker and cleanup loops
WORKER_ENABLED=1 RECOVER_STALE_JOBS=1 .venv/bin/python -m audiobook.worker
```

Useful production environment flags:

```text
OUT_DIR=./out
START_INPROCESS_WORKER=0
WORKER_ENABLED=1
RECOVER_STALE_JOBS=1
JOB_STALE_AFTER_SECONDS=1800
JOB_MAX_ATTEMPTS=3
ENFORCE_QUEUE_LIMITS=1
MAX_ACTIVE_JOBS_PER_USER=1
MAX_GLOBAL_QUEUED_JOBS=10
MIN_CREATE_INTERVAL_SECONDS=30
MAX_UPLOAD_BYTES=2147483648
MAX_TEXT_BYTES=52428800
URL_FETCH_MAX_BYTES=5242880
URL_FETCH_MAX_REDIRECTS=5
ENABLE_DISK_PRESSURE_CLEANUP=1
OUT_DIR_MAX_BYTES=0
MIN_FREE_DISK_BYTES=10737418240
ORPHAN_UPLOAD_TTL_SECONDS=86400
```

## Authentication

Firebase Authentication is required for the web UI. Place the Firebase Admin SDK
service-account JSON at:

```text
firebase-adminsdk.json
```

Never commit this file. It is ignored by `.gitignore`.

## Public HTTPS (Cloudflare Tunnel)

To expose this securely over HTTPS (required for phone lock-screen audio and PWA offline features), run a Cloudflare Tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```
This gives you a public HTTPS URL (e.g. `https://random-words.trycloudflare.com`). Visit this URL on your phone to use the UI.
