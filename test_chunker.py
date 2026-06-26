import os
from contextlib import contextmanager

from audiobook.chunker import chunk_text


@contextmanager
def patched_env(**updates):
    previous = {name: os.environ.get(name) for name in updates}
    try:
        for name, value in updates.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = str(value)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def assert_raises(expected_type, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except expected_type as exc:
        return exc
    except Exception as exc:
        raise AssertionError(
            f"expected {expected_type.__name__}, got {type(exc).__name__}: {exc}"
        ) from exc
    raise AssertionError(f"expected {expected_type.__name__}")


def test_sentence_mode_keeps_one_sentence_per_chunk():
    text = "Alpha. Beta! Gamma?"

    chunks = chunk_text(text, mode="sentence")

    assert chunks == ["Alpha.", "Beta!", "Gamma?"]


def test_sentence_mode_preserves_old_rollback_behavior():
    first = "Alpha   keeps\tinternal spacing."
    long_sentence = "x" * 95
    text = f"  {first} {long_sentence}  "

    chunks = chunk_text(text, mode="sentence", max_chars=40)

    assert chunks == [first, long_sentence]
    assert len(chunks[1]) > 40


def test_packed_mode_combines_short_sentences():
    text = "One. Two. Three."

    chunks = chunk_text(text, mode="packed", target_chars=80, max_chars=120)

    assert chunks == ["One. Two. Three."]


def test_packed_mode_splits_chinese_sentence_punctuation_without_spaces():
    text = "第一句完成。第二句继续！第三句收尾？"

    chunks = chunk_text(text, mode="packed", target_chars=18, max_chars=40)

    assert chunks == ["第一句完成。 第二句继续！", "第三句收尾？"]


def test_packed_mode_respects_max_chunk_size():
    text = "Alpha beta gamma. Delta epsilon zeta. Eta theta iota. Kappa lambda mu."

    chunks = chunk_text(text, mode="packed", target_chars=200, max_chars=45)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 45 for chunk in chunks)
    assert " ".join(chunks) == text


def test_long_unpunctuated_text_splits_safely():
    text = "x" * 95

    chunks = chunk_text(text, mode="packed", target_chars=30, max_chars=40)

    assert [len(chunk) for chunk in chunks] == [40, 40, 15]
    assert "".join(chunks) == text


def test_long_no_space_text_prefers_punctuation_before_raw_split():
    text = "甲" * 34 + "，" + "乙" * 34 + "。" + "丙" * 10

    chunks = chunk_text(text, mode="packed", target_chars=80, max_chars=40)

    assert chunks == ["甲" * 34 + "，", "乙" * 34 + "。", "丙" * 10]
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert "".join(chunks) == text


def test_no_empty_chunks_from_messy_spacing():
    text = "   First. \n\n   Second!        \n Third?    "

    chunks = chunk_text(text, mode="packed", target_chars=200, max_chars=200)

    assert chunks == ["First. Second! Third?"]
    assert all(chunk.strip() for chunk in chunks)


def test_absent_env_defaults_to_packed_target_800_max_1200():
    short_text = "Alpha. Beta! Gamma?"
    target_first = "a" * 399 + "."
    target_exact_second = "b" * 398 + "."
    target_over_second = "b" * 399 + "."
    target_exact_text = f"{target_first} {target_exact_second}"
    target_over_text = f"{target_first} {target_over_second}"
    long_text = "x" * 1250

    assert len(target_exact_text) == 800
    assert len(target_over_text) == 801

    with patched_env(
        AUDIOBOOK_CHUNK_MODE=None,
        AUDIOBOOK_CHUNK_TARGET_CHARS=None,
        AUDIOBOOK_CHUNK_MAX_CHARS=None,
    ):
        short_chunks = chunk_text(short_text)
        target_exact_chunks = chunk_text(target_exact_text)
        target_over_chunks = chunk_text(target_over_text)
        long_chunks = chunk_text(long_text)

    assert short_chunks == [short_text]
    assert target_exact_chunks == [target_exact_text]
    assert target_over_chunks == [target_first, target_over_second]
    assert [len(chunk) for chunk in long_chunks] == [1200, 50]
    assert all(0 < len(chunk) <= 1200 for chunk in long_chunks)
    assert "".join(long_chunks) == long_text


def test_env_default_mode_can_be_sentence():
    with patched_env(AUDIOBOOK_CHUNK_MODE="sentence"):
        chunks = chunk_text("Alpha. Beta.")

    assert chunks == ["Alpha.", "Beta."]


def test_env_default_mode_can_be_packed():
    with patched_env(
        AUDIOBOOK_CHUNK_MODE="packed",
        AUDIOBOOK_CHUNK_TARGET_CHARS="80",
        AUDIOBOOK_CHUNK_MAX_CHARS="120",
    ):
        chunks = chunk_text("Alpha. Beta.")

    assert chunks == ["Alpha. Beta."]


def test_env_target_chars_are_honored_in_packed_mode():
    with patched_env(
        AUDIOBOOK_CHUNK_MODE="packed",
        AUDIOBOOK_CHUNK_TARGET_CHARS="12",
        AUDIOBOOK_CHUNK_MAX_CHARS="120",
    ):
        chunks = chunk_text("Alpha. Beta. Gamma.")

    assert chunks == ["Alpha. Beta.", "Gamma."]


def test_env_max_chars_are_honored_in_packed_mode():
    with patched_env(
        AUDIOBOOK_CHUNK_MODE="packed",
        AUDIOBOOK_CHUNK_TARGET_CHARS="120",
        AUDIOBOOK_CHUNK_MAX_CHARS="10",
    ):
        chunks = chunk_text("abcdefghijklmnopqrst")

    assert chunks == ["abcdefghij", "klmnopqrst"]


def test_invalid_numeric_env_values_fall_back_to_defaults():
    with patched_env(
        AUDIOBOOK_CHUNK_MODE="packed",
        AUDIOBOOK_CHUNK_TARGET_CHARS="invalid",
        AUDIOBOOK_CHUNK_MAX_CHARS="0",
    ):
        chunks = chunk_text("Alpha. Beta.")

    assert chunks == ["Alpha. Beta."]


def test_invalid_numeric_args_raise_value_error():
    assert_raises(ValueError, chunk_text, "Alpha.", mode="packed", target_chars=0)
    assert_raises(ValueError, chunk_text, "Alpha.", mode="packed", max_chars="invalid")


def test_unsupported_mode_raises_value_error():
    assert_raises(ValueError, chunk_text, "Alpha.", mode="paragraph")


def test_optional_args_are_keyword_only():
    assert_raises(TypeError, chunk_text, "Alpha.", "packed")


def run_tests():
    test_sentence_mode_keeps_one_sentence_per_chunk()
    test_sentence_mode_preserves_old_rollback_behavior()
    test_packed_mode_combines_short_sentences()
    test_packed_mode_splits_chinese_sentence_punctuation_without_spaces()
    test_packed_mode_respects_max_chunk_size()
    test_long_unpunctuated_text_splits_safely()
    test_long_no_space_text_prefers_punctuation_before_raw_split()
    test_no_empty_chunks_from_messy_spacing()
    test_absent_env_defaults_to_packed_target_800_max_1200()
    test_env_default_mode_can_be_sentence()
    test_env_default_mode_can_be_packed()
    test_env_target_chars_are_honored_in_packed_mode()
    test_env_max_chars_are_honored_in_packed_mode()
    test_invalid_numeric_env_values_fall_back_to_defaults()
    test_invalid_numeric_args_raise_value_error()
    test_unsupported_mode_raises_value_error()
    test_optional_args_are_keyword_only()
    print("All chunker tests passed!")


if __name__ == "__main__":
    run_tests()
