import asyncio
import json
import os
import shutil
import time
import uuid
from pathlib import Path

from .config import get_config, AppConfig
from .db import (
    claim_next_queued_book,
    get_db,
    recover_stale_processing_jobs,
)
from .engine import generate_audiobook


def _worker_id() -> str:
    return f"{os.uname().nodename}-{os.getpid()}-{uuid.uuid4().hex[:8]}"


def _prewarm_tts():
    try:
        import torch
    except Exception:
        return

    if torch.cuda.is_available():
        from .tts import get_pipeline

        get_pipeline("a")


async def run_worker_loop(config: AppConfig | None = None, worker_id: str | None = None):
    cfg = config or get_config()
    if not cfg.worker_enabled:
        return

    cfg.out_dir.mkdir(exist_ok=True)
    upload_dir = cfg.out_dir / "_uploads"
    upload_dir.mkdir(exist_ok=True)
    worker_name = worker_id or _worker_id()

    await asyncio.to_thread(_prewarm_tts)

    while True:
        if cfg.recover_stale_jobs:
            await asyncio.to_thread(
                recover_stale_processing_jobs,
                stale_after_seconds=cfg.job_stale_after_seconds,
                max_attempts=cfg.job_max_attempts,
            )

        job = await asyncio.to_thread(claim_next_queued_book, worker_id=worker_name)
        if not job:
            await asyncio.sleep(2)
            continue

        await asyncio.to_thread(process_job, job, cfg, worker_name)


def process_job(job: dict, config: AppConfig | None = None, worker_id: str | None = None):
    cfg = config or get_config()
    job_id = job["id"]
    if not _job_owned_by_worker(job_id, worker_id):
        return

    progress_dict = {
        "title": "",
        "chapters_done": 0,
        "chapter_index": 0,
        "total_chapters": 0,
        "total_chunks": 0,
        "chunk_count": 0,
        "chunks_done": 0,
        "audio_seconds": 0,
        "total_audio_seconds": 0,
        "chunk_chars": 0,
        "text_char_count": 0,
        "max_chunk_chars": 0,
        "chunk_mode": "",
        "lang": "",
        "voice": "",
        "percent": 0,
    }

    def progress_cb(stage, **kwargs):
        p = progress_dict
        if stage == "chapter_start":
            p["title"] = kwargs.get("title", "")
            p["chapter_index"] = kwargs.get("index", 0)
            p["total_chapters"] = kwargs.get("total", 0)
        elif stage == "chapter_info":
            p["total_chunks"] = kwargs.get("total_chunks", 0)
            p["chunks_done"] = 0
            p["chunk_count"] += kwargs.get("total_chunks", 0)
            p["chunk_chars"] = kwargs.get("chunk_chars", 0)
            p["text_char_count"] += kwargs.get("chunk_chars", 0)
            p["max_chunk_chars"] = kwargs.get("max_chunk_chars", 0)
            p["chunk_mode"] = kwargs.get("chunk_mode", "")
            p["lang"] = kwargs.get("lang", "")
            p["voice"] = kwargs.get("voice", "")
        elif stage == "chapter_progress":
            p["chunks_done"] = kwargs.get("chunks_done", 0)
            p["total_chunks"] = kwargs.get("total_chunks", 0)
            p["audio_seconds"] = kwargs.get("audio_seconds", 0)
            frac = (
                kwargs.get("chunks_done", 0) / kwargs.get("total_chunks", 1)
            ) if kwargs.get("total_chunks") else 0
            p["percent"] = round(100 * (p["chapters_done"] + frac) / max(1, p["total_chapters"]), 1)
        elif stage in ["chapter_done", "chapter_skipped"]:
            p["chapters_done"] += 1
            if stage == "chapter_done":
                p["total_audio_seconds"] = p.get("total_audio_seconds", 0) + kwargs.get("seconds", 0)
            p["percent"] = round(100 * p["chapters_done"] / max(1, p["total_chapters"]), 1)

        now_ts = str(time.time())
        with get_db() as db:
            db.execute(
                """
                UPDATE books
                SET progress = ?,
                    progress_meta = ?,
                    heartbeat_at = ?,
                    updated_at = ?
                WHERE id = ?
                  AND (? IS NULL OR worker_id = ?)
                """,
                (p["percent"], json.dumps(p), now_ts, now_ts, job_id, worker_id, worker_id),
            )
            db.commit()

    generation_started_at = time.time()
    generation_perf_start = time.perf_counter()
    try:
        result = generate_audiobook(
            source_input=job["source_input"],
            out_dir=cfg.out_dir,
            voice=job["voice"],
            voice_zh=job.get("voice_zh", "zf_xiaobei"),
            speed=job["speed"],
            lang=job["language"],
            normalize=bool(job["normalize"]),
            title=job.get("title"),
            progress_cb=progress_cb,
            force=True,
        )

        if result.out_dir.exists() and result.out_dir.name != job_id:
            new_dir = cfg.out_dir / job_id
            if new_dir.exists():
                shutil.rmtree(new_dir)
            result.out_dir.rename(new_dir)

        book_final_dir = cfg.out_dir / job_id
        total_bytes = sum(f.stat().st_size for f in book_final_dir.glob("*.mp3")) if book_final_dir.exists() else 0
        now_ts = time.time()
        generation_seconds = time.perf_counter() - generation_perf_start
        audio_duration_seconds = sum(c["duration"] for c in result.chapters_meta)
        metrics = _generation_metrics(
            started_at=generation_started_at,
            finished_at=now_ts,
            generation_seconds=generation_seconds,
            audio_duration_seconds=audio_duration_seconds,
            progress=progress_dict,
            output_bytes=total_bytes,
            error_type=None,
        )
        expires_at = now_ts + (72 * 60 * 60)

        with get_db() as db:
            db.execute(
                """
                UPDATE books
                SET status = 'ready',
                    title = ?,
                    duration_seconds = ?,
                    total_bytes = ?,
                    progress_meta = ?,
                    server_expires_at = ?,
                    worker_id = NULL,
                    heartbeat_at = NULL,
                    updated_at = ?
                WHERE id = ?
                  AND (? IS NULL OR worker_id = ?)
                """,
                (
                    result.title,
                    audio_duration_seconds,
                    total_bytes,
                    json.dumps({"chapters": result.chapters_meta, **progress_dict, **metrics}),
                    str(expires_at),
                    str(now_ts),
                    job_id,
                    worker_id,
                    worker_id,
                ),
            )
            db.commit()

    except Exception as exc:
        finished_at = time.time()
        generation_seconds = time.perf_counter() - generation_perf_start
        metrics = _generation_metrics(
            started_at=generation_started_at,
            finished_at=finished_at,
            generation_seconds=generation_seconds,
            audio_duration_seconds=progress_dict.get("total_audio_seconds", 0),
            progress=progress_dict,
            output_bytes=0,
            error_type=type(exc).__name__,
        )
        now_ts = str(finished_at)
        with get_db() as db:
            db.execute(
                """
                UPDATE books
                SET status = 'failed',
                    error_message = ?,
                    progress_meta = ?,
                    last_error_at = ?,
                    worker_id = NULL,
                    heartbeat_at = NULL,
                    updated_at = ?
                WHERE id = ?
                  AND (? IS NULL OR worker_id = ?)
                """,
                (str(exc), json.dumps({**progress_dict, **metrics}), now_ts, now_ts, job_id, worker_id, worker_id),
            )
            db.commit()
    finally:
        if job.get("source_type") == "upload" and job["source_input"] and os.path.exists(job["source_input"]):
            try:
                os.remove(job["source_input"])
            except OSError:
                pass


def _generation_metrics(
    *,
    started_at: float,
    finished_at: float,
    generation_seconds: float,
    audio_duration_seconds: float,
    progress: dict,
    output_bytes: int,
    error_type: str | None,
) -> dict:
    return {
        "generation_started_at": started_at,
        "generation_finished_at": finished_at,
        "generation_seconds": generation_seconds,
        "audio_duration_seconds": audio_duration_seconds,
        "real_time_factor": generation_seconds / audio_duration_seconds if audio_duration_seconds > 0 else None,
        "text_char_count": progress.get("text_char_count", 0),
        "chunk_count": progress.get("chunk_count", 0),
        "output_bytes": output_bytes,
        "error_type": error_type,
    }


def _job_owned_by_worker(job_id: str, worker_id: str | None) -> bool:
    if worker_id is None:
        return True

    with get_db() as db:
        row = db.execute(
            "SELECT worker_id, status FROM books WHERE id = ?",
            (job_id,),
        ).fetchone()

    return bool(row and row["status"] == "processing" and row["worker_id"] == worker_id)


async def run_cleanup_loop(config: AppConfig | None = None):
    cfg = config or get_config()
    if not cfg.cleanup_enabled:
        return

    while True:
        run_cleanup_once(cfg)
        await asyncio.sleep(600)


def run_cleanup_once(config: AppConfig | None = None) -> dict[str, int]:
    cfg = config or get_config()
    return {
        "expired_server_copies": cleanup_expired_server_copies(cfg),
        "orphan_uploads": cleanup_orphan_uploads(cfg),
        "disk_pressure_copies": cleanup_disk_pressure(cfg),
    }


def cleanup_expired_server_copies(config: AppConfig | None = None, now: float | None = None) -> int:
    cfg = config or get_config()
    now_ts = time.time() if now is None else now
    removed = 0
    with get_db() as db:
        cursor = db.execute(
            """
            SELECT id
            FROM books
            WHERE status = 'ready'
              AND server_deleted_at IS NULL
              AND CAST(server_expires_at AS REAL) < ?
            """,
            (now_ts,),
        )
        expired_books = cursor.fetchall()

        for row in expired_books:
            book_id = row["id"]
            book_dir = cfg.out_dir / book_id
            if book_dir.exists():
                shutil.rmtree(book_dir)
            db.execute(
                "UPDATE books SET server_deleted_at = ?, updated_at = ? WHERE id = ?",
                (str(now_ts), str(now_ts), book_id),
            )
            removed += 1
        db.commit()
    return removed


def cleanup_orphan_uploads(config: AppConfig | None = None, now: float | None = None) -> int:
    cfg = config or get_config()
    upload_dir = cfg.out_dir / "_uploads"
    if not upload_dir.exists():
        return 0

    now_value = time.time() if now is None else now
    cutoff = now_value - cfg.orphan_upload_ttl_seconds
    with get_db() as db:
        active_rows = db.execute(
            """
            SELECT source_input
            FROM books
            WHERE deleted_at IS NULL
              AND source_type = 'upload'
              AND status IN ('queued', 'processing')
              AND source_input IS NOT NULL
            """
        ).fetchall()
    active_paths = {str(Path(row["source_input"]).resolve()) for row in active_rows}

    removed = 0
    for path in upload_dir.iterdir():
        if not path.is_file():
            continue
        if path.stat().st_mtime >= cutoff:
            continue
        if str(path.resolve()) in active_paths:
            continue
        path.unlink()
        removed += 1
    return removed


def cleanup_disk_pressure(config: AppConfig | None = None, now: float | None = None) -> int:
    cfg = config or get_config()
    if not cfg.enable_disk_pressure_cleanup:
        return 0
    if cfg.out_dir_max_bytes <= 0 and cfg.min_free_disk_bytes <= 0:
        return 0

    now_ts = time.time() if now is None else now
    removed = 0

    while _disk_pressure_active(cfg):
        with get_db() as db:
            row = db.execute(
                """
                SELECT id
                FROM books
                WHERE status = 'ready'
                  AND deleted_at IS NULL
                  AND server_deleted_at IS NULL
                ORDER BY CAST(created_at AS REAL) ASC
                LIMIT 1
                """
            ).fetchone()

            if not row:
                return removed

            book_id = row["id"]
            book_dir = cfg.out_dir / book_id
            if book_dir.exists():
                shutil.rmtree(book_dir)
            db.execute(
                "UPDATE books SET server_deleted_at = ?, updated_at = ? WHERE id = ?",
                (str(now_ts), str(now_ts), book_id),
            )
            db.commit()
            removed += 1

    return removed


def _disk_pressure_active(config: AppConfig) -> bool:
    if config.out_dir_max_bytes > 0 and _directory_size(config.out_dir) > config.out_dir_max_bytes:
        return True

    if config.min_free_disk_bytes > 0:
        try:
            return shutil.disk_usage(config.out_dir).free < config.min_free_disk_bytes
        except OSError:
            return False

    return False


def _directory_size(path) -> int:
    total = 0
    if not path.exists():
        return total

    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


async def _main_async():
    cfg = get_config()
    await asyncio.gather(run_worker_loop(cfg), run_cleanup_loop(cfg))


def main():
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
