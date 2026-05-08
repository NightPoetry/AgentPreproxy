from __future__ import annotations

import copy
from typing import Any

from agentpreproxy.debug.logger import get_logger
from agentpreproxy.proxy.adapters.base import (
    BaseAdapter,
    InternalMessage,
    InternalRequest,
    InternalResponse,
)

log = get_logger("proxy.adapters.openai")


class OpenAIAdapter(BaseAdapter):
    api_format = "openai"

    def normalize_request(self, body: dict[str, Any]) -> InternalRequest:
        messages: list[InternalMessage] = []
        for msg in body.get("messages", []):
            messages.append(InternalMessage(role=msg["role"], content=msg.get("content", "")))
        req = InternalRequest(
            messages=messages,
            stream=body.get("stream", False),
            model=body.get("model", ""),
            api_format=self.api_format,
            raw_body=body,
        )
        log.debug("normalized openai request: %d messages, stream=%s", len(messages), req.stream)
        return req

    def denormalize_request(self, req: InternalRequest) -> dict[str, Any]:
        body = copy.deepcopy(req.raw_body)
        rebuilt: list[dict[str, Any]] = []
        for msg in req.messages:
            rebuilt.append({"role": msg.role, "content": msg.content})
        body["messages"] = rebuilt
        body["stream"] = req.stream
        if req.model:
            body["model"] = req.model
        return body

    def normalize_response(self, body: dict[str, Any]) -> InternalResponse:
        content = ""
        finish_reason = None
        choices = body.get("choices", [])
        if choices:
            choice = choices[0]
            msg = choice.get("message", {})
            content = msg.get("content", "") or ""
            finish_reason = choice.get("finish_reason")
        log.debug("normalized openai response: %d chars, finish=%s", len(content), finish_reason)
        return InternalResponse(content=content, finish_reason=finish_reason, raw_body=body)

    def denormalize_response(self, resp: InternalResponse, raw_request_body: dict[str, Any]) -> dict[str, Any]:
        body = copy.deepcopy(resp.raw_body)
        if body.get("choices"):
            body["choices"][0]["message"]["content"] = resp.content
        return body

    def extract_stream_delta(self, chunk: dict[str, Any]) -> str | None:
        choices = chunk.get("choices", [])
        if not choices:
            return None
        delta = choices[0].get("delta", {})
        return delta.get("content")

    def make_stream_chunk(self, text: str, chunk_template: dict[str, Any]) -> dict[str, Any]:
        chunk = copy.deepcopy(chunk_template)
        if chunk.get("choices"):
            chunk["choices"][0]["delta"] = {"content": text}
        return chunk
