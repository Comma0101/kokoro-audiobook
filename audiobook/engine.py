import os
import time
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Any
import subprocess

from .sources import get_source
from .chunker import chunk_text
from .tts import synth_chapter, get_pipeline
from .assemble import assemble_chapter
from .util import sanitize_filename
from .normalize import normalize_for_speech, strip_non_latin
from .lang import detect_lang

@dataclass
class BookResult:
    book_id: str
    title: str
    out_dir: Path
    chapters_meta: list[dict]

def generate_audiobook(source_input: str, out_dir: Path, voice: str = "af_heart", voice_zh: str = "zf_xiaobei", speed: float = 1.0, lang: str = "auto",
                       normalize: bool = True, write_srt: bool = True, single_file: bool = False,
                       force: bool = False, title: str = None, progress_cb: Callable = None) -> BookResult:

    chapters = get_source(source_input).load(source_input)
    if not chapters:
        raise ValueError("No text extracted from input.")

    # Human-friendly display title + folder slug.
    # `title` (from the caller) wins; otherwise derive a sensible one instead of a temp/UUID path.
    is_url = source_input.startswith("http://") or source_input.startswith("https://")
    if title and title.strip():
        book_title = title.strip()
    elif is_url:
        # Use the extracted article <title> rather than the URL slug.
        book_title = (chapters[0].title or "").strip() or "Web Article"
    else:
        book_title = Path(source_input).stem

    stem = sanitize_filename(book_title) or "untitled"
    book_dir = out_dir / stem
    book_dir.mkdir(parents=True, exist_ok=True)
    
    chapter_mp3s = []
    chapters_meta = []
    
    for i, chapter in enumerate(chapters, 1):
        ch_stem = f"Chapter_{chapter.index:02d}_{sanitize_filename(chapter.title)}"
        mp3_path = book_dir / f"{ch_stem}.mp3"
        srt_path = book_dir / f"{ch_stem}.srt"
        cues_path = book_dir / f"{ch_stem}.cues.json"
        tmp_wav = book_dir / f"{ch_stem}.wav"
        
        chapter_mp3s.append(mp3_path)
        total_chapters = len(chapters)

        if progress_cb:
            progress_cb(stage="chapter_start", index=i, total=total_chapters, title=chapter.title)

        if not force and mp3_path.exists():
            chapters_meta.append({
                "index": i,
                "title": chapter.title,
                "mp3": mp3_path.name,
                "srt": srt_path.name if write_srt else None,
                "cues": cues_path.name,
                "duration": 0  # placeholder since we skipped
            })
            if progress_cb:
                progress_cb(stage="chapter_skipped", index=i, total=total_chapters, title=chapter.title)
            continue

        # Per-chapter language routing
        ch_lang = lang if lang != 'auto' else detect_lang(chapter.text)
        pipeline = get_pipeline(ch_lang)

        if ch_lang == 'z':
            ch_voice = voice_zh
            # Whitespace cleanup only, no normalizer or non-latin strip
            chapter_text = " ".join(chapter.text.split())
        else:
            ch_voice = voice
            chapter_text = chapter.text
            if normalize:
                chapter_text = normalize_for_speech(chapter_text)
            chapter_text = strip_non_latin(chapter_text)

        chunks = chunk_text(chapter_text)
        chunk_chars = sum(len(chunk) for chunk in chunks)
        max_chunk_chars = max((len(chunk) for chunk in chunks), default=0)
        chunk_mode = os.environ.get("AUDIOBOOK_CHUNK_MODE", "packed").strip().lower()

        if progress_cb:
            progress_cb(stage="chapter_info", index=i, total=total_chapters, title=chapter.title,
                        total_chunks=len(chunks), chunk_chars=chunk_chars,
                        max_chunk_chars=max_chunk_chars, chunk_mode=chunk_mode,
                        lang=ch_lang, voice=ch_voice)

        def _on_chunk(chunks_done, total_chunks, audio_seconds, _i=i):
            if progress_cb:
                progress_cb(stage="chapter_progress", index=_i, total=total_chapters,
                            chunks_done=chunks_done, total_chunks=total_chunks,
                            audio_seconds=audio_seconds)

        start = time.time()
        dur_seconds, cues = synth_chapter(pipeline, chunks, tmp_wav, voice=ch_voice, speed=speed,
                                          on_progress=_on_chunk)
        elapsed = time.time() - start
        rtf = elapsed / dur_seconds if dur_seconds > 0 else 0.0

        # Save cues.json
        cues_dict = [{"start": c.start, "end": c.end, "text": c.text} for c in cues]
        with open(cues_path, "w", encoding="utf-8") as f:
            json.dump(cues_dict, f, ensure_ascii=False)

        # Assemble
        assemble_chapter(tmp_wav, cues, book_dir, ch_stem, write_srt=write_srt)

        chapters_meta.append({
            "index": i,
            "title": chapter.title,
            "mp3": mp3_path.name,
            "srt": srt_path.name if write_srt else None,
            "cues": cues_path.name,
            "duration": dur_seconds
        })

        if progress_cb:
            progress_cb(stage="chapter_done", index=i, total=total_chapters,
                        seconds=dur_seconds, elapsed=elapsed, rtf=rtf)
            
    if single_file and len(chapter_mp3s) > 1:
        concat_txt = book_dir / "concat.txt"
        with open(concat_txt, "w", encoding="utf-8") as f:
            for mp3 in chapter_mp3s:
                if mp3.exists():
                    abs_path = str(mp3.absolute()).replace("'", "'\\''")
                    f.write(f"file '{abs_path}'\n")
        single_mp3 = book_dir / "Audiobook.mp3"
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt), "-c", "copy", str(single_mp3)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        concat_txt.unlink()
        
    return BookResult(
        book_id=stem,
        title=book_title,
        out_dir=book_dir,
        chapters_meta=chapters_meta
    )
