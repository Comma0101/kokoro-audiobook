import os
from dataclasses import dataclass
from pathlib import Path


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _int_env(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default

    return value if value >= minimum else default


@dataclass(frozen=True)
class AppConfig:
    out_dir: Path
    max_upload_bytes: int
    max_text_bytes: int
    start_inprocess_worker: bool
    worker_enabled: bool
    cleanup_enabled: bool
    recover_stale_jobs: bool
    job_stale_after_seconds: int
    job_max_attempts: int
    enforce_queue_limits: bool
    max_active_jobs_per_user: int
    max_global_queued_jobs: int
    min_create_interval_seconds: int
    enable_disk_pressure_cleanup: bool
    orphan_upload_ttl_seconds: int
    out_dir_max_bytes: int
    min_free_disk_bytes: int
    enable_fp16: bool


def get_config() -> AppConfig:
    out_dir = Path(os.getenv("OUT_DIR", "./out")).absolute()
    return AppConfig(
        out_dir=out_dir,
        max_upload_bytes=_int_env("MAX_UPLOAD_BYTES", 2 * 1024 * 1024 * 1024, minimum=1),
        max_text_bytes=_int_env("MAX_TEXT_BYTES", 50 * 1024 * 1024, minimum=1),
        start_inprocess_worker=_bool_env("START_INPROCESS_WORKER", True),
        worker_enabled=_bool_env("WORKER_ENABLED", True),
        cleanup_enabled=_bool_env("CLEANUP_ENABLED", True),
        recover_stale_jobs=_bool_env("RECOVER_STALE_JOBS", False),
        job_stale_after_seconds=_int_env("JOB_STALE_AFTER_SECONDS", 30 * 60, minimum=1),
        job_max_attempts=_int_env("JOB_MAX_ATTEMPTS", 3, minimum=1),
        enforce_queue_limits=_bool_env("ENFORCE_QUEUE_LIMITS", False),
        max_active_jobs_per_user=_int_env("MAX_ACTIVE_JOBS_PER_USER", 1, minimum=1),
        max_global_queued_jobs=_int_env("MAX_GLOBAL_QUEUED_JOBS", 10, minimum=1),
        min_create_interval_seconds=_int_env("MIN_CREATE_INTERVAL_SECONDS", 0, minimum=0),
        enable_disk_pressure_cleanup=_bool_env("ENABLE_DISK_PRESSURE_CLEANUP", False),
        orphan_upload_ttl_seconds=_int_env("ORPHAN_UPLOAD_TTL_SECONDS", 24 * 60 * 60, minimum=1),
        out_dir_max_bytes=_int_env("OUT_DIR_MAX_BYTES", 0, minimum=0),
        min_free_disk_bytes=_int_env("MIN_FREE_DISK_BYTES", 0, minimum=0),
        enable_fp16=_bool_env("ENABLE_FP16", False),
    )
