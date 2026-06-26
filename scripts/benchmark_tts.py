#!/usr/bin/env python3
"""Run a local Kokoro audiobook generation benchmark and emit JSON metrics."""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHUNK_MODE = "packed"
DEFAULT_TARGET_CHARS = 800
DEFAULT_MAX_CHARS = 1200
SMOKE_SENTENCE = "This is a short local TTS benchmark sentence."


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc

    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark local audiobook TTS generation and print JSON metrics."
    )
    parser.add_argument("input", nargs="?", help="Path or URL to benchmark input")
    parser.add_argument("--output-dir", default="out_bench", help="Benchmark output directory")
    parser.add_argument("--voice", default="af_heart", help="Kokoro voice to use")
    parser.add_argument("--speed", type=float, default=1.0, help="Speech speed")
    parser.add_argument("--lang", default="auto", help="Language code ('auto', 'a', 'z')")
    parser.add_argument(
        "--chunk-mode",
        choices=("sentence", "packed"),
        default=DEFAULT_CHUNK_MODE,
        help="Chunking strategy to benchmark",
    )
    parser.add_argument("--target-chars", type=positive_int, help="Packed chunk target size")
    parser.add_argument("--max-chars", type=positive_int, help="Packed chunk hard maximum size")
    parser.add_argument(
        "--repeat-text",
        type=positive_int,
        help="Generate a small repeated text input when no input path is supplied",
    )
    return parser


def resolve_positive_int(value: int | None, env_name: str, default: int) -> int:
    if value is not None:
        return value

    raw = os.environ.get(env_name)
    if raw is None:
        return default

    try:
        parsed = int(raw)
    except ValueError:
        return default

    return parsed if parsed > 0 else default


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def prepare_input(args: argparse.Namespace, output_dir: Path, parser: argparse.ArgumentParser) -> str:
    if args.input and args.repeat_text is not None:
        parser.error("--repeat-text can only be used when no input path is provided")

    if args.input:
        if not is_url(args.input):
            input_path = Path(args.input)
            if not input_path.exists():
                parser.error(f"input file does not exist: {input_path}")
        return args.input

    if args.repeat_text is None:
        parser.error("input path is required unless --repeat-text is provided")

    output_dir.mkdir(parents=True, exist_ok=True)
    input_path = output_dir / "benchmark_input.txt"
    input_path.write_text((SMOKE_SENTENCE + " ") * args.repeat_text + "\n", encoding="utf-8")
    return str(input_path)


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total

    for child in path.rglob("*"):
        if child.is_file():
            total += child.stat().st_size
    return total


def cuda_metrics(torch_module: Any) -> tuple[bool, str | None]:
    available = bool(torch_module.cuda.is_available())
    if not available:
        return False, None

    try:
        return True, str(torch_module.cuda.get_device_name(0))
    except Exception:
        return True, None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    input_source = prepare_input(args, output_dir, parser)

    target_chars = resolve_positive_int(
        args.target_chars,
        "AUDIOBOOK_CHUNK_TARGET_CHARS",
        DEFAULT_TARGET_CHARS,
    )
    max_chars = resolve_positive_int(
        args.max_chars,
        "AUDIOBOOK_CHUNK_MAX_CHARS",
        DEFAULT_MAX_CHARS,
    )

    os.environ["AUDIOBOOK_CHUNK_MODE"] = args.chunk_mode
    os.environ["AUDIOBOOK_CHUNK_TARGET_CHARS"] = str(target_chars)
    os.environ["AUDIOBOOK_CHUNK_MAX_CHARS"] = str(max_chars)

    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    progress: dict[int, int] = {}

    def on_progress(stage: str, **kwargs: Any) -> None:
        if stage == "chapter_info":
            try:
                progress[int(kwargs["index"])] = int(kwargs.get("total_chunks") or 0)
            except (KeyError, TypeError, ValueError):
                return

    original_stdout = sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        import torch

        from audiobook.engine import generate_audiobook

        cuda_available, cuda_device_name = cuda_metrics(torch)
        started_at = time.perf_counter()
        result = generate_audiobook(
            source_input=input_source,
            out_dir=output_dir,
            voice=args.voice,
            speed=args.speed,
            lang=args.lang,
            force=True,
            progress_cb=on_progress,
        )
        generation_seconds = time.perf_counter() - started_at

    audio_seconds = sum(float(chapter.get("duration") or 0.0) for chapter in result.chapters_meta)
    metrics = {
        "input": input_source,
        "chunk_mode": args.chunk_mode,
        "target_chars": target_chars,
        "max_chars": max_chars,
        "voice": args.voice,
        "speed": args.speed,
        "cuda_available": cuda_available,
        "cuda_device_name": cuda_device_name,
        "generation_seconds": generation_seconds,
        "audio_seconds": audio_seconds,
        "real_time_factor": generation_seconds / audio_seconds if audio_seconds > 0 else None,
        "chapter_count": len(result.chapters_meta),
        "output_dir": str(result.out_dir),
        "output_bytes": directory_size(result.out_dir),
        "chunk_count": sum(progress.values()),
    }

    print(json.dumps(metrics, indent=2, sort_keys=True), file=original_stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
