import re

def chunk_text(text: str) -> list[str]:
    """
    Split into sentence-ish pieces with regex.
    This is only a coarse feed into Kokoro.
    Do not rely on these strings for SRT text. Kokoro re-chunks internally.
    """
    chunks = re.split(r'(?<=[.!?])\s+', text)
    return [c.strip() for c in chunks if c.strip()]
