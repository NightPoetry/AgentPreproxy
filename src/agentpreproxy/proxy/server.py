from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agentpreproxy.config import get_config
from agentpreproxy.core.intervention import build_intervention
from agentpreproxy.core.state import RequestState, RequestStatus, create_state, remove_state
from agentpreproxy.core.tag import parse_tags
from agentpreproxy.core.watchdog import Verdict, check
from agentpreproxy.debug.hooks import get_hooks
from agentpreproxy.debug.logger import get_logger, request_id_var
from agentpreproxy.proxy.adapters.anthropic import AnthropicAdapter
from agentpreproxy.proxy.adapters.base import BaseAdapter, InternalRequest
from agentpreproxy.proxy.adapters.openai import OpenAIAdapter
from agentpreproxy.proxy.escape import clean_response, escape_input
from agentpreproxy.proxy.inject import inject_rules
from agentpreproxy.proxy.stream import StreamProcessor

log = get_logger("proxy.server")

app = FastAPI(title="AgentPreproxy")

_openai_adapter = OpenAIAdapter()
_anthropic_adapter = AnthropicAdapter()


def _get_adapter(path: str) -> tuple[BaseAdapter, str]:
    if "/v1/messages" in path:
        return _anthropic_adapter, "anthropic"
    return _openai_adapter, "openai"


def _get_backend_url(api_format: str, path: str) -> str:
    cfg = get_config()
    if api_format == "anthropic":
        return cfg.anthropic_base_url.rstrip("/") + path
    return cfg.openai_base_url.rstrip("/") + path


def _build_headers(original_headers: dict, api_format: str) -> dict[str, str]:
    cfg = get_config()
    headers: dict[str, str] = {}
    for key in ("content-type", "accept"):
        if key in original_headers:
            headers[key] = original_headers[key]
    if api_format == "openai":
        key = cfg.openai_api_key or original_headers.get("authorization", "")
        if key and not key.startswith("Bearer "):
            key = f"Bearer {key}"
        if key:
            headers["authorization"] = key
    else:
        key = cfg.anthropic_api_key or original_headers.get("x-api-key", "")
        if key:
            headers["x-api-key"] = key
        av = original_headers.get("anthropic-version", "2023-06-01")
        headers["anthropic-version"] = av
    return headers


async def _forward_non_stream(
    adapter: BaseAdapter,
    internal_req: InternalRequest,
    state: RequestState,
    headers: dict[str, str],
    backend_url: str,
) -> JSONResponse:
    body = adapter.denormalize_request(internal_req)
    body["stream"] = False
    log.debug("[%s] forwarding non-stream to %s", state.request_id, backend_url)

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(backend_url, json=body, headers=headers)

    if resp.status_code != 200:
        log.warning("[%s] backend returned %d", state.request_id, resp.status_code)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)

    resp_body = resp.json()
    internal_resp = adapter.normalize_response(resp_body)
    result = check(state, internal_resp.content)

    if result.verdict == Verdict.INTERVENE:
        action = build_intervention(state, internal_req, result.reason)
        if action.should_intervene and action.replacement_request:
            log.info("[%s] intervening: %s", state.request_id, result.reason)
            retry_body = adapter.denormalize_request(action.replacement_request)
            retry_body["stream"] = False
            async with httpx.AsyncClient(timeout=120) as client:
                retry_resp = await client.post(backend_url, json=retry_body, headers=headers)
            if retry_resp.status_code == 200:
                resp_body = retry_resp.json()
                internal_resp = adapter.normalize_response(resp_body)

    internal_resp.content = clean_response(internal_resp.content)
    final_body = adapter.denormalize_response(internal_resp, body)
    state.status = RequestStatus.COMPLETED
    get_hooks().response_sent(request_id=state.request_id, content_length=len(internal_resp.content))
    remove_state(state.request_id)
    return JSONResponse(content=final_body)


async def _forward_stream(
    adapter: BaseAdapter,
    internal_req: InternalRequest,
    state: RequestState,
    headers: dict[str, str],
    backend_url: str,
):
    body = adapter.denormalize_request(internal_req)
    body["stream"] = True
    log.debug("[%s] forwarding stream to %s", state.request_id, backend_url)
    processor = StreamProcessor()

    async def generate():
        intervened = False
        chunk_template: dict[str, Any] = {}

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", backend_url, json=body, headers=headers) as resp:
                if resp.status_code != 200:
                    error_body = await resp.aread()
                    yield b"data: " + error_body + b"\n\n"
                    return

                async for line in resp.aiter_lines():
                    if intervened:
                        break
                    if not line.startswith("data: "):
                        yield (line + "\n").encode()
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        remaining, remaining_tags = processor.flush_remaining()
                        if remaining:
                            for tv in remaining_tags:
                                state.record_tag(tv)
                            out_chunk = adapter.make_stream_chunk(remaining, chunk_template)
                            yield b"data: " + json.dumps(out_chunk).encode() + b"\n\n"
                        yield b"data: [DONE]\n\n"
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        yield (line + "\n").encode()
                        continue

                    if not chunk_template:
                        chunk_template = chunk

                    delta_text = adapter.extract_stream_delta(chunk)
                    if delta_text is None:
                        yield (line + "\n").encode()
                        continue

                    clean_text, tag_values = processor.feed(delta_text)
                    for tv in tag_values:
                        state.record_tag(tv)

                    if clean_text:
                        result = check(state, clean_text)
                        if result.verdict == Verdict.INTERVENE:
                            log.info("[%s] stream intervention: %s", state.request_id, result.reason)
                            get_hooks().intervention_triggered(
                                request_id=state.request_id, reason=result.reason,
                            )
                            intervened = True
                            yield b"data: [DONE]\n\n"
                            break
                        out_chunk = adapter.make_stream_chunk(clean_text, chunk_template)
                        yield b"data: " + json.dumps(out_chunk).encode() + b"\n\n"

        state.status = RequestStatus.INTERVENED if intervened else RequestStatus.COMPLETED
        get_hooks().response_sent(request_id=state.request_id, content_length=len(processor.total_flushed))
        remove_state(state.request_id)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.api_route("/{path:path}", methods=["POST"])
async def proxy_endpoint(request: Request, path: str):
    adapter, api_format = _get_adapter(path)
    state = create_state()
    request_id_var.set(state.request_id)

    body = await request.json()
    get_hooks().request_received(request_id=state.request_id, api_format=api_format)
    log.info("[%s] received %s request: %s", state.request_id, api_format, path)

    internal_req = adapter.normalize_request(body)

    for msg in internal_req.messages:
        if msg.role != "system":
            msg.set_text(escape_input(msg.text()))

    inject_rules(internal_req)

    orig_headers = dict(request.headers)
    headers = _build_headers(orig_headers, api_format)
    backend_url = _get_backend_url(api_format, "/" + path)

    get_hooks().request_forwarded(request_id=state.request_id, backend_url=backend_url)

    if internal_req.stream:
        return await _forward_stream(adapter, internal_req, state, headers, backend_url)
    else:
        return await _forward_non_stream(adapter, internal_req, state, headers, backend_url)
