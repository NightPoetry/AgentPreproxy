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

log = get_logger("proxy.adapters.anthropic")


class AnthropicAdapter(BaseAdapter):
    api_format = "anthropic"

    def normalize_request(self, body: dict[str, Any]) -> InternalRequest:
        messages: list[InternalMessage] = []
        system_text = body.get("system", "")
        if system_text:
            if isinstance(system_text, list):
                parts = [b.get("text", "") for b in system_text if isinstance(b, dict)]
                system_text = "\n".join(parts)
            messages.append(InternalMessage(role="system", content=system_text))
        for msg in body.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block["text"])
                content = "\n".join(text_parts) if text_parts else ""
            messages.append(InternalMessage(role=msg["role"], content=content))
        req = InternalRequest(
            messages=messages,
            stream=body.get("stream", False),
            model=body.get("model", ""),
            api_format=self.api_format,
            raw_body=body,
        )
        log.debug("normalized anthropic request: %d messages, stream=%s", len(messages), req.stream)
        return req

    def denormalize_request(self, req: InternalRequest) -> dict[str, Any]:
        body = copy.deepcopy(req.raw_body)
        system_parts = [m for m in req.messages if m.role == "system"]
        non_system = [m for m in req.messages if m.role != "system"]
        if system_parts:
            body["system"] = "\n\n".join(m.text() for m in system_parts)
        rebuilt: list[dict[str, Any]] = []
        for msg in non_system:
            rebuilt.append({"role": msg.role, "content": msg.content})
        body["messages"] = rebuilt
        body["stream"] = req.stream
        if req.model:
            body["model"] = req.model
        return body

    def normalize_response(self, body: dict[str, Any]) -> InternalResponse:
        content = ""
        finish_reason = body.get("stop_reason")
        for block in body.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                content += block.get("text", "")
        log.debug("normalized anthropic response: %d chars, stop=%s", len(content), finish_reason)
        return InternalResponse(content=content, finish_reason=finish_reason, raw_body=body)

    def denormalize_response(self, resp: InternalResponse, raw_request_body: dict[str, Any]) -> dict[str, Any]:
        body = copy.deepcopy(resp.raw_body)
        for block in body.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = resp.content
                break
        return body

    def extract_stream_delta(self, chunk: dict[str, Any]) -> str | None:
        evt_type = chunk.get("type", "")
        if evt_type == "content_block_delta":
            delta = chunk.get("delta", {})
            if delta.get("type") == "text_delta":
                return delta.get("text")
        return None

    def make_stream_chunk(self, text: str, chunk_template: dict[str, Any]) -> dict[str, Any]:
        chunk = copy.deepcopy(chunk_template)
        chunk["type"] = "content_block_delta"
        chunk["delta"] = {"type": "text_delta", "text": text}
        return chunk
