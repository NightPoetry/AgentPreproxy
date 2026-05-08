from __future__ import annotations

import re
from dataclasses import dataclass

from agentpreproxy.config import get_config
from agentpreproxy.debug.logger import get_logger

log = get_logger("core.tag")


@dataclass(frozen=True)
class ParsedTag:
    raw: str
    value: int
    start: int
    end: int


def _build_regex() -> re.Pattern[str]:
    cfg = get_config()
    o = re.escape(cfg.tag_open)
    c = re.escape(cfg.tag_close)
    p = re.escape(cfg.tag_prefix)
    return re.compile(rf"{o}{p}:(\d+){c}")


def _build_prefix_regex() -> re.Pattern[str]:
    cfg = get_config()
    o = re.escape(cfg.tag_open)
    p = re.escape(cfg.tag_prefix)
    return re.compile(rf"{o}{p}:\d*$")


_tag_re: re.Pattern[str] | None = None
_prefix_re: re.Pattern[str] | None = None


def _get_tag_re() -> re.Pattern[str]:
    global _tag_re
    if _tag_re is None:
        _tag_re = _build_regex()
    return _tag_re


def _get_prefix_re() -> re.Pattern[str]:
    global _prefix_re
    if _prefix_re is None:
        _prefix_re = _build_prefix_regex()
    return _prefix_re


def reset_cache() -> None:
    global _tag_re, _prefix_re
    _tag_re = None
    _prefix_re = None


def parse_tags(text: str) -> list[ParsedTag]:
    regex = _get_tag_re()
    results: list[ParsedTag] = []
    for m in regex.finditer(text):
        tag = ParsedTag(raw=m.group(0), value=int(m.group(1)), start=m.start(), end=m.end())
        log.debug("parsed tag: value=%d at [%d:%d]", tag.value, tag.start, tag.end)
        results.append(tag)
    return results


def strip_tags(text: str) -> str:
    regex = _get_tag_re()
    return regex.sub("", text)


def could_be_tag_prefix(text: str) -> bool:
    return bool(_get_prefix_re().search(text))


def format_tag(n: int) -> str:
    return get_config().format_tag(n)
