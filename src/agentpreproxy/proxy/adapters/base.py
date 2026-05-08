from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InternalMessage:
    role: str
    content: str | list[Any]

    def text(self) -> str:
        if isinstance(self.content, str):
            return self.content
        parts = []
        for block in self.content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)

    def set_text(self, new_text: str) -> None:
        if isinstance(self.content, str):
            self.content = new_text
        else:
            self.content = new_text


@dataclass
class InternalRequest:
    messages: list[InternalMessage]
    stream: bool
    model: str
    api_format: str
    raw_body: dict[str, Any] = field(default_factory=dict)


@dataclass
class InternalResponse:
    content: str
    finish_reason: str | None = None
    raw_body: dict[str, Any] = field(default_factory=dict)


class BaseAdapter:
    api_format: str = ""

    def normalize_request(self, body: dict[str, Any]) -> InternalRequest:
        raise NotImplementedError

    def denormalize_request(self, req: InternalRequest) -> dict[str, Any]:
        raise NotImplementedError

    def normalize_response(self, body: dict[str, Any]) -> InternalResponse:
        raise NotImplementedError

    def denormalize_response(self, resp: InternalResponse, raw_request_body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def extract_stream_delta(self, chunk: dict[str, Any]) -> str | None:
        raise NotImplementedError

    def make_stream_chunk(self, text: str, chunk_template: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
