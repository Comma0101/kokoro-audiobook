import subprocess
import os
import soundfile as sf
from pathlib import Path
from .models import Cue

def format_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def _write_srt(cues: list[Cue], path: Path):
    lines = []
    for i, cue in enumerate(cues, start=1):
        lines.append(str(i))
        start_str = format_time(cue.start)
        end_str = format_time(cue.end)
        lines.append(f"{start_str} --> {end_str}")
        lines.append(cue.text)
        lines.append("") # Blank line
        
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

def assemble_chapter(tmp_wav: Path, cues: list[Cue], out_dir: Path, stem: str, write_srt: bool = True):
    """
    Converts WAV to MP3, removes WAV, and conditionally writes SRT.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    mp3_path = out_dir / f"{stem}.mp3"
    srt_path = out_dir / f"{stem}.srt"
    
    # 1. Transcode to MP3 with ffmpeg using CBR for accurate HTML5 seeking
    cmd = [
        "ffmpeg", "-y", "-i", str(tmp_wav), 
        "-codec:a", "libmp3lame", "-b:a", "64k", 
        str(mp3_path)
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Delete tmp wav
    if tmp_wav.exists():
        tmp_wav.unlink()
        
    # 2. Write SRT
    if write_srt:
        _write_srt(cues, srt_path)
