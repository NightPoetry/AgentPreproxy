from agentpreproxy.core.tag import format_tag, parse_tags, strip_tags, could_be_tag_prefix, reset_cache


def setup_function():
    reset_cache()


def test_format_tag():
    assert format_tag(1) == "⟪WD:1⟫"
    assert format_tag(42) == "⟪WD:42⟫"


def test_parse_single_tag():
    text = "hello ⟪WD:1⟫ world"
    tags = parse_tags(text)
    assert len(tags) == 1
    assert tags[0].value == 1
    assert tags[0].raw == "⟪WD:1⟫"


def test_parse_multiple_tags():
    text = "a ⟪WD:1⟫ b ⟪WD:2⟫ c ⟪WD:3⟫"
    tags = parse_tags(text)
    assert [t.value for t in tags] == [1, 2, 3]


def test_parse_no_tags():
    assert parse_tags("no tags here") == []


def test_strip_tags():
    text = "hello ⟪WD:1⟫ world ⟪WD:2⟫ end"
    assert strip_tags(text) == "hello  world  end"


def test_strip_tags_no_tags():
    text = "nothing to strip"
    assert strip_tags(text) == text


def test_could_be_tag_prefix():
    assert could_be_tag_prefix("some text ⟪WD:") is True
    assert could_be_tag_prefix("some text ⟪WD:1") is True
    assert could_be_tag_prefix("some text ⟪W") is False
    assert could_be_tag_prefix("no prefix") is False


def test_parse_tag_positions():
    text = "ab⟪WD:5⟫cd"
    tags = parse_tags(text)
    assert len(tags) == 1
    assert text[tags[0].start:tags[0].end] == "⟪WD:5⟫"
