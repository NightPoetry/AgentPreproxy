from __future__ import annotations

from agentpreproxy.config import get_config
from agentpreproxy.core.tag import strip_tags
from agentpreproxy.debug.logger import get_logger

log = get_logger("proxy.escape")

_PLACEHOLDER_OPEN = "\x00_TAG_OPEN_\x00"
_PLACEHOLDER_CLOSE = "\x00_TAG_CLOSE_\x00"


def escape_input(text: str) -> str:
    cfg = get_config()
    o, c = cfg.tag_open, cfg.tag_close
    if o not in text and c not in text:
        return text
    result = text.replace(o, o + o).replace(c, c + c)
    log.debug("escaped input: %d tag chars doubled", result.count(o + o) + result.count(c + c))
    return result


def unescape_output(text: str) -> str:
    cfg = get_config()
    o, c = cfg.tag_open, cfg.tag_close
    doubled_o = o + o
    doubled_c = c + c
    if doubled_o not in text and doubled_c not in text:
        return text
    result = text.replace(doubled_o, o).replace(doubled_c, c)
    log.debug("unescaped output: restored literal tag chars")
    return result


def clean_response(text: str) -> str:
    cfg = get_config()
    doubled_o = cfg.tag_open + cfg.tag_open
    doubled_c = cfg.tag_close + cfg.tag_close

    text = text.replace(doubled_o, _PLACEHOLDER_OPEN)
    text = text.replace(doubled_c, _PLACEHOLDER_CLOSE)

    text = strip_tags(text)

    text = text.replace(_PLACEHOLDER_OPEN, cfg.tag_open)
    text = text.replace(_PLACEHOLDER_CLOSE, cfg.tag_close)

    return text
