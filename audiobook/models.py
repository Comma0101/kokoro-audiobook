from dataclasses import dataclass

@dataclass
class Chapter:
    index: int          # 1-based
    title: str          # e.g. "Chapter 1" or EPUB heading; fallback "Part_{index}"
    text: str           # cleaned plain text

@dataclass
class Cue:               # one SRT subtitle entry
    start: float         # seconds, absolute within the chapter
    end: float
    text: str            # the graphemes Kokoro actually spoke for this segment
