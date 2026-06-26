import os
import re


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")
_PACKED_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|(?<=[。！？])\s*")
_SAFE_SPLIT_PUNCTUATION = "。！？.!?，,；;：:"
_WHITESPACE_RE = re.compile(r"\s+")


def chunk_text(text: str, *, mode=None, target_chars=None, max_chars=None) -> list[str]:
    """
    Split text into coarse feed chunks for Kokoro.

    Sentence mode preserves the original one-sentence-per-chunk behavior.
    Packed mode combines short sentences to improve local generation throughput.
    Do not rely on these strings for SRT text. Kokoro re-chunks internally.
    """
    resolved_mode = _resolve_mode(mode)

    if resolved_mode == "sentence":
        return _sentence_chunks(text)

    if resolved_mode == "packed":
        resolved_max_chars = _resolve_positive_int(
            max_chars,
            "AUDIOBOOK_CHUNK_MAX_CHARS",
            1200,
        )
        resolved_target_chars = _resolve_positive_int(
            target_chars,
            "AUDIOBOOK_CHUNK_TARGET_CHARS",
            800,
        )
        pieces = _split_long_pieces(_packed_sentence_pieces(text), resolved_max_chars)
        return _pack_pieces(pieces, resolved_target_chars, resolved_max_chars)

    raise ValueError(f"Unsupported chunk mode: {resolved_mode}")


def _resolve_mode(mode):
    if mode is None:
        mode = os.environ.get("AUDIOBOOK_CHUNK_MODE", "packed")
    return str(mode).strip().lower()


def _resolve_positive_int(value, env_name, default):
    if value is None:
        value = os.environ.get(env_name)
        if value is None:
            return default

        try:
            resolved = int(value)
        except (TypeError, ValueError):
            return default

        if resolved < 1:
            return default
        return resolved

    try:
        resolved = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{env_name} must be a positive integer") from exc
    if resolved < 1:
        raise ValueError(f"{env_name} must be a positive integer")
    return resolved


def _sentence_chunks(text):
    chunks = []
    for piece in _SENTENCE_SPLIT_RE.split(text):
        stripped = piece.strip()
        if stripped:
            chunks.append(stripped)
    return chunks


def _packed_sentence_pieces(text):
    pieces = []
    for piece in _PACKED_SENTENCE_SPLIT_RE.split(text):
        cleaned = _WHITESPACE_RE.sub(" ", piece).strip()
        if cleaned:
            pieces.append(cleaned)
    return pieces


def _split_long_pieces(pieces, max_chars):
    chunks = []
    for piece in pieces:
        chunks.extend(_split_long_piece(piece, max_chars))
    return chunks


def _split_long_piece(piece, max_chars):
    if len(piece) <= max_chars:
        return [piece]

    chunks = []
    remaining = piece

    while len(remaining) > max_chars:
        split_at = _punctuation_split_at(remaining, max_chars)
        if split_at > 0:
            chunk = remaining[:split_at].strip()
            remaining = remaining[split_at:].strip()
        else:
            split_at = remaining.rfind(" ", 0, max_chars + 1)
            if split_at <= 0:
                chunk = remaining[:max_chars].strip()
                remaining = remaining[max_chars:].strip()
            else:
                chunk = remaining[:split_at].strip()
                remaining = remaining[split_at + 1 :].strip()

        if chunk:
            chunks.append(chunk)

    if remaining:
        chunks.append(remaining)

    return chunks


def _punctuation_split_at(text, max_chars):
    split_at = -1
    window = text[:max_chars]
    for punctuation in _SAFE_SPLIT_PUNCTUATION:
        split_at = max(split_at, window.rfind(punctuation))

    if split_at < 0:
        return -1
    return split_at + 1


def _pack_pieces(pieces, target_chars, max_chars):
    chunks = []
    current = ""
    pack_limit = min(target_chars, max_chars)

    for piece in pieces:
        if not current:
            current = piece
            continue

        candidate = f"{current} {piece}"
        if len(candidate) <= pack_limit:
            current = candidate
        else:
            chunks.append(current)
            current = piece

    if current:
        chunks.append(current)

    return chunks
