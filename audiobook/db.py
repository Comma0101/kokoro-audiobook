import sqlite3
import os
import time
import secrets
import hashlib
import base64
import json
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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            deleted_at TEXT
        );
        """)

        # --- Lightweight idempotent migrations (additive columns only) ---
        book_cols = {r['name'] for r in db.execute("PRAGMA table_info(books)").fetchall()}
        if 'total_bytes' not in book_cols:
            db.execute("ALTER TABLE books ADD COLUMN total_bytes INTEGER")

# --- Auth Helpers ---

def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

# --- Job Queue Helpers ---

def claim_next_queued_book():
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
            
        now_ts = str(time.time())
        db.execute("UPDATE books SET status = 'processing', updated_at = ? WHERE id = ? AND status = 'queued'", (now_ts, row['id']))
        db.execute("COMMIT")
        
        return dict(row)
