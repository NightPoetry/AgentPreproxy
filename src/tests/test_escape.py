from agentpreproxy.proxy.escape import escape_input, unescape_output, clean_response
from agentpreproxy.core.tag import reset_cache


def setup_function():
    reset_cache()


def test_escape_no_tag_chars():
    assert escape_input("normal text") == "normal text"


def test_escape_tag_chars():
    text = "user says ⟪WD:1⟫ literally"
    escaped = escape_input(text)
    assert "⟪⟪" in escaped
    assert "⟫⟫" in escaped


def test_unescape_roundtrip():
    original = "literal ⟪WD:99⟫ text"
    escaped = escape_input(original)
    restored = unescape_output(escaped)
    assert restored == original


def test_unescape_no_doubled():
    assert unescape_output("no doubles") == "no doubles"


def test_clean_response_strips_tags_and_unescapes():
    text = "hello ⟪WD:1⟫ world ⟪⟪WD:literal⟫⟫ end"
    cleaned = clean_response(text)
    assert "⟪WD:1⟫" not in cleaned
    assert "⟪WD:literal⟫" in cleaned


def test_clean_response_plain_text():
    assert clean_response("just text") == "just text"
