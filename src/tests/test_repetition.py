from agentpreproxy.config import Config, set_config
from agentpreproxy.core.repetition import detect_repetition


def setup_function():
    set_config(Config(repetition_min_length=10, repetition_similarity=0.8))


def test_no_repetition():
    result = detect_repetition("this is completely unique text with no repeated parts whatsoever in the whole thing")
    assert result.detected is False


def test_obvious_repetition():
    chunk = "hello world this is repeated "
    text = chunk * 5
    result = detect_repetition(text)
    assert result.detected is True
    assert result.similarity >= 0.8


def test_short_text_no_detection():
    result = detect_repetition("short")
    assert result.detected is False


def test_tail_repetition():
    unique = "this is the beginning of a longer text. " * 2
    repeated = "this exact phrase keeps showing up. "
    text = unique + repeated * 4
    result = detect_repetition(text)
    assert result.detected is True
