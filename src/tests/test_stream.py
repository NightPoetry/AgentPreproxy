from agentpreproxy.config import Config, set_config
from agentpreproxy.core.tag import reset_cache
from agentpreproxy.proxy.stream import StreamProcessor


def setup_function():
    set_config(Config())
    reset_cache()


def test_stream_plain_text():
    sp = StreamProcessor()
    out, tags = sp.feed("hello world")
    remaining, remaining_tags = sp.flush_remaining()
    full = out + remaining
    assert "hello world" in full
    assert tags == [] and remaining_tags == []


def test_stream_strips_tags():
    sp = StreamProcessor()
    parts = ["hello ", "⟪WD:1⟫", " world"]
    collected = ""
    all_tags = []
    for p in parts:
        text, tags = sp.feed(p)
        collected += text
        all_tags.extend(tags)
    text, tags = sp.flush_remaining()
    collected += text
    all_tags.extend(tags)
    assert "⟪WD:1⟫" not in collected
    assert 1 in all_tags


def test_stream_split_tag_across_tokens():
    sp = StreamProcessor()
    tokens = ["before ", "⟪WD", ":1⟫", " after"]
    collected = ""
    all_tags = []
    for t in tokens:
        text, tags = sp.feed(t)
        collected += text
        all_tags.extend(tags)
    text, tags = sp.flush_remaining()
    collected += text
    all_tags.extend(tags)
    assert "⟪" not in collected
    assert 1 in all_tags
    assert "before" in collected
    assert "after" in collected


def test_stream_unescape_doubled():
    sp = StreamProcessor()
    text, _ = sp.feed("literal ⟪⟪WD:1⟫⟫ text")
    remaining, _ = sp.flush_remaining()
    full = text + remaining
    assert "⟪WD:1⟫" in full
