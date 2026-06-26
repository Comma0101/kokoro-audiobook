import sqlite3
import time
import hashlib
from pathlib import Path

DB_PATH = Path("./audiobook.db").absolute()

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT,
            phone TEXT,
            display_name TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_identities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            provider_subject TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            display_name TEXT,
            avatar_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(provider, provider_subject)
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            default_voice TEXT,
            default_playback_speed REAL DEFAULT 1.0,
            auto_save_offline INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            session_hash TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT
        );

        CREATE TABLE IF NOT EXISTS books (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_input TEXT,
            status TEXT NOT NULL,
            progress REAL NOT NULL DEFAULT 0,
            progress_meta TEXT,
            language TEXT,
            voice TEXT,
            voice_zh TEXT,
            speed REAL DEFAULT 1.0,
            normalize INTEGER DEFAULT 1,
            duration_seconds REAL,
            server_audio_path TEXT,
            server_cues_path TEXT,
            server_expires_at TEXT,
            server_deleted_at TEXT,
            local_saved_at TEXT,
            error_message TEXT,
            worker_id TEXT,
            processing_started_at TEXT,
            heartbeat_at TEXT,
            attempt_count INTEGER DEFAULT 0,
            last_error_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT
        );
        """)

        # --- Lightweight idempotent migrations (additive columns only) ---
        book_cols = {r['name'] for r in db.execute("PRAGMA table_info(books)").fetchall()}
        if 'total_bytes' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN total_bytes INTEGER")
        if 'worker_id' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN worker_id TEXT")
        if 'processing_started_at' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN processing_started_at TEXT")
        if 'heartbeat_at' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN heartbeat_at TEXT")
        if 'attempt_count' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN attempt_count INTEGER DEFAULT 0")
        if 'last_error_at' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN last_error_at TEXT")

# --- Auth Helpers ---

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

# --- Job Queue Helpers ---

def claim_next_queued_book(worker_id: str | None = None, now: float | None = None):
    """
    Atomically claims the next queued book and returns it as a dict.
    Returns None if no jobs are queued.
    """
    with get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        
        cursor = db.execute("SELECT * FROM books WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1")
        row = cursor.fetchone()
        
        if not row:
            db.execute("COMMIT")
            return None
            
        now_ts = str(time.time() if now is None else now)
        db.execute(
            """
            UPDATE books
            SET status = 'processing',
                worker_id = ?,
                processing_started_at = ?,
                heartbeat_at = ?,
                attempt_count = COALESCE(attempt_count, 0) + 1,
                updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (worker_id, now_ts, now_ts, now_ts, row['id']),
        )
        db.execute("COMMIT")

        claimed = dict(row)
        claimed["status"] = "processing"
        claimed["worker_id"] = worker_id
        claimed["processing_started_at"] = now_ts
        claimed["heartbeat_at"] = now_ts
        claimed["attempt_count"] = int(claimed.get("attempt_count") or 0) + 1
        return claimed


def recover_stale_processing_jobs(
    *,
    now: float | None = None,
    stale_after_seconds: int = 30 * 60,
    max_attempts: int = 3,
) -> dict[str, int]:
    now_value = time.time() if now is None else now
    cutoff = now_value - stale_after_seconds
    requeued = 0
    failed = 0

    with get_db() as db:
        db.execute("BEGIN IMMEDIATE")
        rows = db.execute(
            """
            SELECT id, attempt_count, heartbeat_at
            FROM books
            WHERE status = 'processing'
              AND (
                heartbeat_at IS NULL
                OR CAST(heartbeat_at AS REAL) < ?
              )
            """,
            (cutoff,),
        ).fetchall()

        now_ts = str(now_value)
        for row in rows:
            attempts = int(row["attempt_count"] or 0)
            if attempts >= max_attempts:
                db.execute(
                    """
                    UPDATE books
                    SET status = 'failed',
                        error_message = ?,
                        last_error_at = ?,
                        worker_id = NULL,
                        heartbeat_at = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        f"Generation failed after stale worker heartbeat ({attempts} attempts).",
                        now_ts,
                        now_ts,
                        row["id"],
                    ),
                )
                failed += 1
            else:
                db.execute(
                    """
                    UPDATE books
                    SET status = 'queued',
                        worker_id = NULL,
                        processing_started_at = NULL,
                        heartbeat_at = NULL,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (now_ts, row["id"]),
                )
                requeued += 1

        db.execute("COMMIT")

    return {"requeued": requeued, "failed": failed}


def get_create_limit_violation(
    owner_id: str,
    *,
    max_active_jobs_per_user: int,
    max_global_queued_jobs: int,
    min_create_interval_seconds: int,
    now: float | None = None,
) -> str | None:
    now_value = time.time() if now is None else now

    with get_db() as db:
        active_count = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM books
            WHERE owner_id = ?
              AND deleted_at IS NULL
              AND status IN ('queued', 'processing')
            """,
            (owner_id,),
        ).fetchone()["count"]
        if active_count >= max_active_jobs_per_user:
            return "You already have an audiobook being created. Please wait for it to finish before starting another."

        global_queued_count = db.execute(
            """
            SELECT COUNT(*) AS count
            FROM books
            WHERE deleted_at IS NULL
              AND status = 'queued'
            """,
        ).fetchone()["count"]
        if global_queued_count >= max_global_queued_jobs:
            return "The audiobook creation queue is full. Please try again later."

        if min_create_interval_seconds > 0:
            latest = db.execute(
                """
                SELECT MAX(CAST(created_at AS REAL)) AS latest_created_at
                FROM books
                WHERE owner_id = ?
                  AND deleted_at IS NULL
                """,
                (owner_id,),
            ).fetchone()["latest_created_at"]
            if latest is not None and now_value - float(latest) < min_create_interval_seconds:
                return "Please wait before creating another audiobook."

    return None
