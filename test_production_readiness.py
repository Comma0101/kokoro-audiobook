import json
import os
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory


@contextmanager
def patched_env(**values):
    old = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = str(value)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_config_defaults_preserve_local_development():
    from audiobook.config import get_config

    with patched_env(
        START_INPROCESS_WORKER=None,
        WORKER_ENABLED=None,
        RECOVER_STALE_JOBS=None,
        ENFORCE_QUEUE_LIMITS=None,
        ENABLE_DISK_PRESSURE_CLEANUP=None,
        ENABLE_FP16=None,
    ):
        cfg = get_config()

    assert cfg.start_inprocess_worker is True
    assert cfg.worker_enabled is True
    assert cfg.recover_stale_jobs is False
    assert cfg.enforce_queue_limits is False
    assert cfg.enable_disk_pressure_cleanup is False
    assert cfg.enable_fp16 is False
    assert cfg.job_stale_after_seconds == 30 * 60
    assert cfg.job_max_attempts == 3


def test_config_reads_environment_overrides():
    from audiobook.config import get_config

    with patched_env(
        START_INPROCESS_WORKER="0",
        WORKER_ENABLED="false",
        RECOVER_STALE_JOBS="yes",
        ENFORCE_QUEUE_LIMITS="1",
        ENABLE_DISK_PRESSURE_CLEANUP="true",
        ENABLE_FP16="on",
        JOB_STALE_AFTER_SECONDS="45",
        JOB_MAX_ATTEMPTS="5",
    ):
        cfg = get_config()

    assert cfg.start_inprocess_worker is False
    assert cfg.worker_enabled is False
    assert cfg.recover_stale_jobs is True
    assert cfg.enforce_queue_limits is True
    assert cfg.enable_disk_pressure_cleanup is True
    assert cfg.enable_fp16 is True
    assert cfg.job_stale_after_seconds == 45
    assert cfg.job_max_attempts == 5


def test_worker_module_provides_external_entrypoint():
    from audiobook import worker

    assert callable(worker.run_worker_loop)
    assert callable(worker.run_cleanup_loop)
    assert callable(worker.main)


def test_worker_loop_moved_out_of_server_module():
    server_source = Path("audiobook/server.py").read_text(encoding="utf-8")

    assert "async def worker(" not in server_source
    assert "async def cleanup_daemon(" not in server_source
    assert "from .worker import" in server_source


def test_requirements_file_lists_runtime_dependencies():
    req = Path("requirements.txt")

    assert req.exists()
    text = req.read_text(encoding="utf-8")
    for dep in [
        "fastapi",
        "uvicorn",
        "firebase-admin",
        "kokoro",
        "torch",
        "soundfile",
        "PyMuPDF",
        "EbookLib",
        "beautifulsoup4",
        "trafilatura",
        "num2words",
        "ordered-set",
        "pypinyin",
    ]:
        assert dep in text


def test_google_cloud_env_uses_rollback_friendly_packed_chunks():
    env = Path("deploy/google-cloud/kokoro-audiobook.env").read_text(encoding="utf-8")

    assert "AUDIOBOOK_CHUNK_MODE=packed" in env
    assert "AUDIOBOOK_CHUNK_TARGET_CHARS=800" in env
    assert "AUDIOBOOK_CHUNK_MAX_CHARS=1200" in env


def _reset_test_db(tmpdir):
    from audiobook import db

    db.DB_PATH = Path(tmpdir) / "audiobook.db"
    db.init_db()
    return db


def _insert_user_and_book(
    db,
    *,
    book_id="book-1",
    user_id="user-1",
    status="queued",
    source_type="text",
    source_input="input.txt",
    heartbeat_at=None,
    attempt_count=0,
    created_at="1000",
):
    with db.get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users (id, created_at, updated_at) VALUES (?, ?, ?)",
            (user_id, created_at, created_at),
        )
        conn.execute(
            """
            INSERT INTO books (
                id, owner_id, title, source_type, source_input, status,
                created_at, updated_at, heartbeat_at, attempt_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                book_id,
                user_id,
                "Book",
                source_type,
                source_input,
                status,
                created_at,
                created_at,
                str(heartbeat_at) if heartbeat_at is not None else None,
                attempt_count,
            ),
        )
        conn.commit()


def test_claim_next_queued_book_records_worker_and_heartbeat():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db)

        job = db.claim_next_queued_book(worker_id="worker-a", now=2000.0)

        assert job["id"] == "book-1"
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", ("book-1",)).fetchone()

        assert row["status"] == "processing"
        assert row["worker_id"] == "worker-a"
        assert row["processing_started_at"] == "2000.0"
        assert row["heartbeat_at"] == "2000.0"
        assert row["attempt_count"] == 1


def test_fresh_processing_job_is_not_recovered():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="processing", heartbeat_at=1995.0, attempt_count=1)

        result = db.recover_stale_processing_jobs(now=2000.0, stale_after_seconds=60, max_attempts=3)

        assert result == {"requeued": 0, "failed": 0}
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", ("book-1",)).fetchone()
        assert row["status"] == "processing"


def test_stale_processing_job_is_requeued():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="processing", heartbeat_at=1000.0, attempt_count=1)

        result = db.recover_stale_processing_jobs(now=2000.0, stale_after_seconds=60, max_attempts=3)

        assert result == {"requeued": 1, "failed": 0}
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", ("book-1",)).fetchone()
        assert row["status"] == "queued"
        assert row["worker_id"] is None
        assert row["heartbeat_at"] is None


def test_stale_processing_job_over_attempt_limit_fails():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="processing", heartbeat_at=1000.0, attempt_count=3)

        result = db.recover_stale_processing_jobs(now=2000.0, stale_after_seconds=60, max_attempts=3)

        assert result == {"requeued": 0, "failed": 1}
        with db.get_db() as conn:
            row = conn.execute("SELECT * FROM books WHERE id = ?", ("book-1",)).fetchone()
        assert row["status"] == "failed"
        assert "stale" in row["error_message"].lower()


def test_worker_does_not_complete_job_owned_by_another_worker():
    from audiobook.config import get_config
    from audiobook.engine import BookResult
    from audiobook import worker

    original_generate = worker.generate_audiobook
    try:
        with TemporaryDirectory() as tmpdir:
            db = _reset_test_db(tmpdir)
            _insert_user_and_book(db, status="processing", heartbeat_at=2000.0, attempt_count=1)
            with db.get_db() as conn:
                conn.execute("UPDATE books SET worker_id = ? WHERE id = ?", ("worker-b", "book-1"))
                conn.commit()

            out_dir = Path(tmpdir) / "out"
            generated_dir = out_dir / "generated"
            generated_dir.mkdir(parents=True)
            (generated_dir / "chapter.mp3").write_bytes(b"mp3")

            def fake_generate_audiobook(**kwargs):
                return BookResult(
                    book_id="generated",
                    title="Generated",
                    out_dir=generated_dir,
                    chapters_meta=[{"duration": 1.0, "mp3": "chapter.mp3", "cues": "chapter.cues.json"}],
                )

            worker.generate_audiobook = fake_generate_audiobook
            cfg = replace(get_config(), out_dir=out_dir)
            job = {
                "id": "book-1",
                "source_input": "input.txt",
                "voice": "af_heart",
                "voice_zh": "zf_xiaobei",
                "speed": 1.0,
                "language": "a",
                "normalize": 1,
                "title": "Book",
                "source_type": "text",
            }

            worker.process_job(job, cfg, "worker-a")

            with db.get_db() as conn:
                row = conn.execute("SELECT status, worker_id FROM books WHERE id = ?", ("book-1",)).fetchone()
            assert row["status"] == "processing"
            assert row["worker_id"] == "worker-b"
    finally:
        worker.generate_audiobook = original_generate


def test_queue_limit_allows_user_under_limits():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="ready")

        violation = db.get_create_limit_violation(
            "user-1",
            max_active_jobs_per_user=1,
            max_global_queued_jobs=1,
            min_create_interval_seconds=0,
            now=2000.0,
        )

        assert violation is None


def test_queue_limit_blocks_user_with_active_job():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="queued")

        violation = db.get_create_limit_violation(
            "user-1",
            max_active_jobs_per_user=1,
            max_global_queued_jobs=10,
            min_create_interval_seconds=0,
            now=2000.0,
        )

        assert violation == "You already have an audiobook being created. Please wait for it to finish before starting another."


def test_queue_limit_blocks_when_global_queue_is_full():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, book_id="book-1", user_id="user-1", status="queued")

        violation = db.get_create_limit_violation(
            "user-2",
            max_active_jobs_per_user=1,
            max_global_queued_jobs=1,
            min_create_interval_seconds=0,
            now=2000.0,
        )

        assert violation == "The audiobook creation queue is full. Please try again later."


def test_queue_limit_blocks_rapid_repeat_create():
    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        _insert_user_and_book(db, status="ready", created_at="1990")

        violation = db.get_create_limit_violation(
            "user-1",
            max_active_jobs_per_user=1,
            max_global_queued_jobs=10,
            min_create_interval_seconds=30,
            now=2000.0,
        )

        assert violation == "Please wait before creating another audiobook."


def test_expired_server_copy_cleanup_removes_ready_book_files():
    from audiobook.config import get_config
    from audiobook import worker

    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        out_dir = Path(tmpdir) / "out"
        book_dir = out_dir / "book-1"
        book_dir.mkdir(parents=True)
        (book_dir / "chapter.mp3").write_bytes(b"audio")
        _insert_user_and_book(db, status="ready")
        with db.get_db() as conn:
            conn.execute("UPDATE books SET server_expires_at = ? WHERE id = ?", ("1000", "book-1"))
            conn.commit()

        cfg = replace(get_config(), out_dir=out_dir)
        removed = worker.cleanup_expired_server_copies(cfg, now=2000.0)

        assert removed == 1
        assert not book_dir.exists()
        with db.get_db() as conn:
            row = conn.execute("SELECT server_deleted_at FROM books WHERE id = ?", ("book-1",)).fetchone()
        assert row["server_deleted_at"] == "2000.0"


def test_orphan_upload_cleanup_deletes_old_unreferenced_upload_only():
    from audiobook.config import get_config
    from audiobook import worker

    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        out_dir = Path(tmpdir) / "out"
        upload_dir = out_dir / "_uploads"
        upload_dir.mkdir(parents=True)
        orphan = upload_dir / "orphan.pdf"
        active = upload_dir / "active.pdf"
        orphan.write_bytes(b"old")
        active.write_bytes(b"active")
        os.utime(orphan, (1000.0, 1000.0))
        os.utime(active, (1000.0, 1000.0))
        _insert_user_and_book(
            db,
            status="processing",
            source_type="upload",
            source_input=str(active),
        )

        cfg = replace(get_config(), out_dir=out_dir, orphan_upload_ttl_seconds=60)
        removed = worker.cleanup_orphan_uploads(cfg, now=2000.0)

        assert removed == 1
        assert not orphan.exists()
        assert active.exists()


def test_disk_pressure_cleanup_is_gated_off_by_default():
    from audiobook.config import get_config
    from audiobook import worker

    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        out_dir = Path(tmpdir) / "out"
        book_dir = out_dir / "book-1"
        book_dir.mkdir(parents=True)
        (book_dir / "chapter.mp3").write_bytes(b"x" * 2048)
        _insert_user_and_book(db, status="ready")

        cfg = replace(get_config(), out_dir=out_dir, out_dir_max_bytes=1, enable_disk_pressure_cleanup=False)
        removed = worker.cleanup_disk_pressure(cfg, now=2000.0)

        assert removed == 0
        assert book_dir.exists()


def test_disk_pressure_cleanup_deletes_oldest_ready_copy():
    from audiobook.config import get_config
    from audiobook import worker

    with TemporaryDirectory() as tmpdir:
        db = _reset_test_db(tmpdir)
        out_dir = Path(tmpdir) / "out"
        old_dir = out_dir / "old-book"
        new_dir = out_dir / "new-book"
        processing_dir = out_dir / "processing-book"
        old_dir.mkdir(parents=True)
        new_dir.mkdir(parents=True)
        processing_dir.mkdir(parents=True)
        (old_dir / "chapter.mp3").write_bytes(b"x" * 1024)
        (new_dir / "chapter.mp3").write_bytes(b"x" * 32)
        (processing_dir / "chapter.mp3").write_bytes(b"x" * 2048)
        _insert_user_and_book(db, book_id="old-book", status="ready", created_at="1000")
        _insert_user_and_book(db, book_id="new-book", status="ready", created_at="2000")
        _insert_user_and_book(db, book_id="processing-book", status="processing", created_at="500")

        cfg = replace(get_config(), out_dir=out_dir, out_dir_max_bytes=2200, enable_disk_pressure_cleanup=True)
        removed = worker.cleanup_disk_pressure(cfg, now=3000.0)

        assert removed == 1
        assert not old_dir.exists()
        assert new_dir.exists()
        assert processing_dir.exists()


def test_worker_records_generation_metrics_on_ready_job():
    from audiobook.config import get_config
    from audiobook.engine import BookResult
    from audiobook import worker

    original_generate = worker.generate_audiobook
    try:
        with TemporaryDirectory() as tmpdir:
            db = _reset_test_db(tmpdir)
            _insert_user_and_book(db, status="processing", heartbeat_at=2000.0, attempt_count=1)
            with db.get_db() as conn:
                conn.execute("UPDATE books SET worker_id = ? WHERE id = ?", ("worker-a", "book-1"))
                conn.commit()

            out_dir = Path(tmpdir) / "out"
            generated_dir = out_dir / "generated"
            generated_dir.mkdir(parents=True)
            (generated_dir / "chapter.mp3").write_bytes(b"x" * 1024)

            def fake_generate_audiobook(**kwargs):
                kwargs["progress_cb"](
                    stage="chapter_info",
                    index=1,
                    total=1,
                    title="Chapter",
                    total_chunks=2,
                    chunk_chars=200,
                    max_chunk_chars=120,
                    chunk_mode="sentence",
                    lang="a",
                    voice="af_heart",
                )
                return BookResult(
                    book_id="generated",
                    title="Generated",
                    out_dir=generated_dir,
                    chapters_meta=[{"duration": 10.0, "mp3": "chapter.mp3", "cues": "chapter.cues.json"}],
                )

            worker.generate_audiobook = fake_generate_audiobook
            cfg = replace(get_config(), out_dir=out_dir)
            job = {
                "id": "book-1",
                "source_input": "input.txt",
                "voice": "af_heart",
                "voice_zh": "zf_xiaobei",
                "speed": 1.0,
                "language": "a",
                "normalize": 1,
                "title": "Book",
                "source_type": "text",
            }

            worker.process_job(job, cfg, "worker-a")

            with db.get_db() as conn:
                row = conn.execute("SELECT status, progress_meta, total_bytes FROM books WHERE id = ?", ("book-1",)).fetchone()

            meta = json.loads(row["progress_meta"])
            assert row["status"] == "ready"
            assert row["total_bytes"] == 1024
            assert meta["generation_seconds"] >= 0
            assert meta["audio_duration_seconds"] == 10.0
            assert meta["real_time_factor"] >= 0
            assert meta["chunk_count"] == 2
            assert meta["output_bytes"] == 1024
            assert meta["error_type"] is None
    finally:
        worker.generate_audiobook = original_generate


if __name__ == "__main__":
    tests = [
        test_config_defaults_preserve_local_development,
        test_config_reads_environment_overrides,
        test_worker_module_provides_external_entrypoint,
        test_worker_loop_moved_out_of_server_module,
        test_requirements_file_lists_runtime_dependencies,
        test_google_cloud_env_uses_rollback_friendly_packed_chunks,
        test_claim_next_queued_book_records_worker_and_heartbeat,
        test_fresh_processing_job_is_not_recovered,
        test_stale_processing_job_is_requeued,
        test_stale_processing_job_over_attempt_limit_fails,
        test_worker_does_not_complete_job_owned_by_another_worker,
        test_queue_limit_allows_user_under_limits,
        test_queue_limit_blocks_user_with_active_job,
        test_queue_limit_blocks_when_global_queue_is_full,
        test_queue_limit_blocks_rapid_repeat_create,
        test_expired_server_copy_cleanup_removes_ready_book_files,
        test_orphan_upload_cleanup_deletes_old_unreferenced_upload_only,
        test_disk_pressure_cleanup_is_gated_off_by_default,
        test_disk_pressure_cleanup_deletes_oldest_ready_copy,
        test_worker_records_generation_metrics_on_ready_job,
    ]
    for test in tests:
        test()
    print("production readiness tests passed")
