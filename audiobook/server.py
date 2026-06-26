import os
import time
import json
import asyncio
import uuid
import shutil
import secrets
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, auth as firebase_auth

from .config import get_config
from .db import get_create_limit_violation, init_db, get_db, hash_session_token

app = FastAPI()

# Initialize Firebase Admin
try:
    if os.path.exists("firebase-adminsdk.json"):
        cred = credentials.Certificate("firebase-adminsdk.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    print(f"Firebase Admin init error: {e}")

# Explicit origins only: a wildcard with allow_credentials=True is invalid for
# cookie auth (browsers refuse it) and an open CSRF surface. Override via env
# ALLOWED_ORIGINS (comma-separated) on the deployment host.
_DEFAULT_ORIGINS = "http://localhost:8000,http://127.0.0.1:8000,https://audiobook.kumma.me"
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG = get_config()

OUT_DIR = CONFIG.out_dir
OUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR = OUT_DIR / "_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)

# Upload limits (override via env on the deployment host).
# Generous defaults for the beta friend-circle test (big image-heavy PDFs run large).
MAX_UPLOAD_BYTES = CONFIG.max_upload_bytes
MAX_TEXT_BYTES = CONFIG.max_text_bytes

def _enforce_create_limits(user_id: str):
    if not CONFIG.enforce_queue_limits:
        return

    violation = get_create_limit_violation(
        user_id,
        max_active_jobs_per_user=CONFIG.max_active_jobs_per_user,
        max_global_queued_jobs=CONFIG.max_global_queued_jobs,
        min_create_interval_seconds=CONFIG.min_create_interval_seconds,
    )
    if violation:
        raise HTTPException(status_code=429, detail=violation)

def _save_upload_bounded(upload_file, dest_path: str, max_bytes: int) -> int:
    """Stream an upload to disk, aborting (and cleaning up) if it exceeds max_bytes."""
    written = 0
    with open(dest_path, "wb") as f:
        while True:
            chunk = upload_file.file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                f.close()
                try: os.remove(dest_path)
                except OSError: pass
                raise HTTPException(413, f"File too large (max {max_bytes // (1024 * 1024)} MB).")
            f.write(chunk)
    return written

init_db()

# --- Auth Dependency ---
def get_current_user(request: Request):
    session_token = request.cookies.get("session_token")
    if not session_token:
        session_token = request.headers.get("X-Token") or request.query_params.get("token")
        
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    session_hash = hash_session_token(session_token)
    with get_db() as db:
        row = db.execute("SELECT user_id, expires_at FROM sessions WHERE session_hash = ?", (session_hash,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if float(row['expires_at']) < time.time():
            db.execute("DELETE FROM sessions WHERE session_hash = ?", (session_hash,))
            db.commit()
            raise HTTPException(status_code=401, detail="Session expired")
        return row['user_id']

# --- Auth Routes ---
from dataclasses import dataclass

@dataclass
class ExternalIdentity:
    provider: str
    subject: str
    email: Optional[str] = None
    phone: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

# Firebase Verification
def verify_external_identity(id_token: str) -> ExternalIdentity:
    if not os.path.exists("firebase-adminsdk.json"):
        raise HTTPException(status_code=500, detail="Server missing firebase-adminsdk.json. Please download it from Firebase Project Settings -> Service Accounts and place it in the project root.")

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return ExternalIdentity(
            provider="firebase",
            subject=decoded_token['uid'],
            email=decoded_token.get('email'),
            phone=decoded_token.get('phone_number'),
            display_name=decoded_token.get('name'),
            avatar_url=decoded_token.get('picture')
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

class SessionRequest(BaseModel):
    id_token: str

@app.post("/api/auth/session")
async def create_session(req: SessionRequest, response: Response):
    identity = verify_external_identity(req.id_token)
    
    with get_db() as db:
        row = db.execute("SELECT user_id FROM user_identities WHERE provider = ? AND provider_subject = ?", 
                         (identity.provider, identity.subject)).fetchone()
        
        now_ts = str(time.time())
        if row:
            user_id = row['user_id']
            # Optionally update email/display_name if changed
        else:
            user_id = str(uuid.uuid4())
            db.execute("INSERT INTO users (id, email, phone, display_name, avatar_url, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (user_id, identity.email, identity.phone, identity.display_name, identity.avatar_url, now_ts, now_ts))
                       
            ident_id = str(uuid.uuid4())
            db.execute("INSERT INTO user_identities (id, user_id, provider, provider_subject, email, phone, display_name, avatar_url, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (ident_id, user_id, identity.provider, identity.subject, identity.email, identity.phone, identity.display_name, identity.avatar_url, now_ts, now_ts))
            
            db.execute("INSERT INTO user_settings (user_id, created_at, updated_at) VALUES (?, ?, ?)",
                       (user_id, now_ts, now_ts))
                       
        session_token = secrets.token_hex(32)
        session_hash = hash_session_token(session_token)
        session_id = str(uuid.uuid4())
        expires_at = str(time.time() + (30 * 24 * 60 * 60))
        
        db.execute("INSERT INTO sessions (id, user_id, session_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                   (session_id, user_id, session_hash, now_ts, expires_at))
        db.commit()
        
        response.set_cookie(key="session_token", value=session_token, httponly=True, samesite="lax", max_age=30*24*60*60, path="/")
        return {"status": "ok", "user_id": user_id}

@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        session_hash = hash_session_token(session_token)
        with get_db() as db:
            db.execute("DELETE FROM sessions WHERE session_hash = ?", (session_hash,))
            db.commit()
    response.delete_cookie("session_token", path="/")
    return {"status": "ok"}

@app.get("/api/auth/me")
async def get_me(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        user = dict(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())
        settings_row = db.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        settings = dict(settings_row) if settings_row else {}
        identities = [dict(r) for r in db.execute("SELECT provider FROM user_identities WHERE user_id = ?", (user_id,)).fetchall()]
        
        return {
            "id": user['id'],
            "email": user['email'],
            "phone": user['phone'],
            "display_name": user['display_name'],
            "avatar_url": user['avatar_url'],
            "providers": [i['provider'] for i in identities],
            "settings": settings
        }

@app.on_event("startup")
async def startup_event():
    cfg = get_config()
    if cfg.start_inprocess_worker:
        from .worker import run_cleanup_loop, run_worker_loop

        asyncio.create_task(run_worker_loop(cfg))
        asyncio.create_task(run_cleanup_loop(cfg))

# --- Jobs API ---
@app.post("/api/books")
async def create_book(
    url: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    voice: str = Form("af_heart"),
    voice_zh: str = Form("zf_xiaobei"),
    speed: float = Form(1.0),
    lang: str = Form("auto"),
    normalize: bool = Form(True),
    user_id: str = Depends(get_current_user)
):
    _enforce_create_limits(user_id)
    job_id = str(uuid.uuid4())
    
    source_type = "text"
    source_input = None
    display_title = ""

    if url:
        source_type = "url"
        source_input = url
        display_title = url
    elif text:
        source_type = "text"
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            raise HTTPException(413, f"Text too large (max {MAX_TEXT_BYTES // (1024 * 1024)} MB).")
        source_input = str(UPLOAD_DIR / f"{job_id}.txt")
        with open(source_input, "w", encoding="utf-8") as f:
            f.write(text)
        snippet = " ".join(text.split()[:8]).strip()
        display_title = (snippet[:50].rstrip() + "…") if len(snippet) > 50 else snippet
        display_title = display_title or "Pasted Text"
    elif file:
        source_type = "upload"
        ext = Path(file.filename).suffix.lower()
        if ext not in [".txt", ".pdf", ".epub", ".docx"]:
            raise HTTPException(400, "Invalid file type. Only .txt, .pdf, .epub, .docx allowed.")
        source_input = str(UPLOAD_DIR / f"{job_id}{ext}")
        _save_upload_bounded(file, source_input, MAX_UPLOAD_BYTES)
        display_title = Path(file.filename).stem
    else:
        raise HTTPException(400, "Must provide url, text, or file.")
        
    now_ts = str(time.time())
    
    with get_db() as db:
        db.execute("""
            INSERT INTO books (
                id, owner_id, title, source_type, source_input, status, language, voice, voice_zh, speed, normalize, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (job_id, user_id, display_title, source_type, source_input, "queued", lang, voice, voice_zh, speed, int(normalize), now_ts, now_ts))
        db.commit()

    return {"id": job_id, "status": "queued"}

@app.get("/api/books")
async def list_books(user_id: str = Depends(get_current_user)):
    with get_db() as db:
        cursor = db.execute("SELECT * FROM books WHERE owner_id = ? AND deleted_at IS NULL ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get('progress_meta'):
                try: d['progress'] = json.loads(d['progress_meta'])
                except: d['progress'] = {}
            else:
                d['progress'] = {}
            d.pop('server_audio_path', None)
            d.pop('server_cues_path', None)
            d.pop('source_input', None)
            result.append(d)
        return result

@app.get("/api/books/{book_id}")
async def get_book(book_id: str, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        cursor = db.execute("SELECT * FROM books WHERE id = ? AND owner_id = ? AND deleted_at IS NULL", (book_id, user_id))
        row = cursor.fetchone()
        if not row: raise HTTPException(404, "Not found")
        d = dict(row)
        if d.get('progress_meta'):
            try: d['progress'] = json.loads(d['progress_meta'])
            except: d['progress'] = {}
        d.pop('server_audio_path', None)
        d.pop('server_cues_path', None)
        return d

@app.delete("/api/books/{book_id}")
async def delete_book(book_id: str, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT id FROM books WHERE id = ? AND owner_id = ? AND deleted_at IS NULL", (book_id, user_id)).fetchone()
        if not row: raise HTTPException(404, "Not found")
            
        now_ts = time.time()
        book_dir = OUT_DIR / book_id
        if book_dir.exists():
            shutil.rmtree(book_dir)
            
        db.execute("UPDATE books SET deleted_at = ?, server_deleted_at = ?, updated_at = ? WHERE id = ?", (str(now_ts), str(now_ts), str(now_ts), book_id))
        db.commit()
    return {"status": "deleted"}

@app.get("/api/books/{book_id}/audio/{filename}")
async def get_book_audio(book_id: str, filename: str, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT id, server_deleted_at FROM books WHERE id = ? AND owner_id = ? AND deleted_at IS NULL", (book_id, user_id)).fetchone()
        if not row or row['server_deleted_at']:
            raise HTTPException(404, "Not found")
            
        audio_path = OUT_DIR / book_id / filename
        if not audio_path.exists():
            raise HTTPException(404, "Audio file not found on server")
            
        return FileResponse(audio_path, media_type="audio/mpeg")

@app.get("/api/books/{book_id}/cues/{filename}")
async def get_book_cues(book_id: str, filename: str, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT id, server_deleted_at FROM books WHERE id = ? AND owner_id = ? AND deleted_at IS NULL", (book_id, user_id)).fetchone()
        if not row or row['server_deleted_at']:
            raise HTTPException(404, "Not found")
            
        cues_path = OUT_DIR / book_id / filename
        if not cues_path.exists():
            raise HTTPException(404, "Cues file not found on server")
            
        return FileResponse(cues_path, media_type="application/json")

@app.post("/api/books/{book_id}/local-saved")
async def mark_local_saved(book_id: str, user_id: str = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT id FROM books WHERE id = ? AND owner_id = ? AND deleted_at IS NULL", (book_id, user_id)).fetchone()
        if not row:
            raise HTTPException(404, "Not found")
            
        now_ts = time.time()
        expires_at = now_ts + (60 * 60) # 1 hour grace after verified local save
        
        db.execute("UPDATE books SET local_saved_at = ?, server_expires_at = ?, updated_at = ? WHERE id = ?",
                   (str(now_ts), str(expires_at), str(now_ts), book_id))
        db.commit()
    return {"status": "ok"}

app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
