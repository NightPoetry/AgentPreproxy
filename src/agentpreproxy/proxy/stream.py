from __future__ import annotations

from dataclasses import dataclass, field

from agentpreproxy.config import get_config
from agentpreproxy.core.tag import could_be_tag_prefix, parse_tags, strip_tags
from agentpreproxy.debug.logger import get_logger
from agentpreproxy.proxy.escape import clean_response

log = get_logger("proxy.stream")


@dataclass
class StreamProcessor:
    _buffer: str = ""
    _flushed_text: str = ""
    _tags_found: list[int] = field(default_factory=list)

    def feed(self, token: str) -> tuple[str, list[int]]:
        self._buffer += token
        return self._try_flush()

    def flush_remaining(self) -> tuple[str, list[int]]:
        text = self._buffer
        self._buffer = ""
        return self._process_chunk(text)

    def _try_flush(self) -> tuple[str, list[int]]:
        if could_be_tag_prefix(self._buffer):
            log.debug("buffer might contain tag prefix, holding: %r", self._buffer[-20:])
            return "", []

        cfg = get_config()
        if cfg.tag_close in self._buffer:
            return self._flush_through_last_close()

        if len(self._buffer) > 200:
            to_flush = self._buffer[:-20]
            self._buffer = self._buffer[-20:]
            return self._process_chunk(to_flush)

        return "", []

    def _flush_through_last_close(self) -> tuple[str, list[int]]:
        cfg = get_config()
        idx = self._buffer.rfind(cfg.tag_close)
        if idx == -1:
            return "", []
        boundary = idx + len(cfg.tag_close)
        to_flush = self._buffer[:boundary]
        self._buffer = self._buffer[boundary:]
        return self._process_chunk(to_flush)

    def _process_chunk(self, text: str) -> tuple[str, list[int]]:
        tags = parse_tags(text)
        tag_values = [t.value for t in tags]
        self._tags_found.extend(tag_values)

        clean = clean_response(text)

        self._flushed_text += clean
        log.debug(
            "processed chunk: %d chars in, %d chars out, %d tags",
            len(text), len(clean), len(tag_values),
        )
        return clean, tag_values

    @property
    def total_flushed(self) -> str:
        return self._flushed_text

    @property
    def all_tags(self) -> list[int]:
        return list(self._tags_found)
