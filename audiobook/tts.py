import sys
import numpy as np
import torch
import soundfile as sf
from pathlib import Path
from typing import Callable
from kokoro import KPipeline
from .models import Cue

SAMPLE_RATE = 24000

_PIPELINES = {}

def get_pipeline(lang_code='a'):
    if lang_code not in _PIPELINES:
        # Log to stderr so it never corrupts a stdout progress bar.
        print(f"Initializing Kokoro pipeline with language code '{lang_code}'...", file=sys.stderr)
        if not torch.cuda.is_available():
            print("WARNING: CUDA is not available. TTS will run on CPU and be very slow.", file=sys.stderr)
        else:
            print("CUDA is available. TTS will run on GPU.", file=sys.stderr)
        _PIPELINES[lang_code] = KPipeline(lang_code=lang_code)
    return _PIPELINES[lang_code]

def synth_chapter(pipeline, chunks: list[str], out_wav_path: Path, voice='af_heart', speed=1.0,
                  on_progress: Callable = None) -> tuple[float, list[Cue]]:
    """
    Synthesize audio for a list of text chunks and stream directly to WAV file.
    Returns the total duration in seconds and a list of SRT Cues.

    on_progress(chunks_done, total_chunks, audio_seconds) is called after each input
    chunk so callers can render fine-grained intra-chapter progress.
    """
    cues = []
    t = 0.0
    total = len(chunks)

    with sf.SoundFile(str(out_wav_path), 'w', samplerate=SAMPLE_RATE, channels=1) as wav_file:
        for i, chunk in enumerate(chunks, 1):
            generator = pipeline(chunk, voice=voice, speed=speed, split_pattern=r'(?<=[.!?。！？])\s*')
            for gs, ps, audio in generator:
                if audio is None:
                    continue
                dur = len(audio) / SAMPLE_RATE
                cues.append(Cue(start=t, end=t + dur, text=gs.strip()))
                t += dur
                wav_file.write(audio)
            if on_progress:
                on_progress(chunks_done=i, total_chunks=total, audio_seconds=t)

    return t, cues
