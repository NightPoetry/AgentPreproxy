from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentpreproxy.config import get_config
from agentpreproxy.core.state import RequestState, RequestStatus
from agentpreproxy.debug.hooks import get_hooks
from agentpreproxy.debug.logger import get_logger
from agentpreproxy.proxy.adapters.base import InternalMessage, InternalRequest

log = get_logger("core.intervention")


@dataclass
class InterventionAction:
    should_intervene: bool
    reason: str = ""
    replacement_request: InternalRequest | None = None
    truncated_at: int = 0


def build_intervention(
    state: RequestState,
    original_request: InternalRequest,
    reason: str,
) -> InterventionAction:
    cfg = get_config()
    if not cfg.intervention_enabled:
        log.info("[%s] intervention disabled by config, skipping", state.request_id)
        return InterventionAction(should_intervene=False, reason="disabled")

    state.status = RequestStatus.INTERVENED
    state.intervention_count += 1

    get_hooks().intervention_triggered(
        request_id=state.request_id,
        reason=reason,
        intervention_count=state.intervention_count,
    )

    new_messages = list(original_request.messages)

    if state.accumulated_text:
        new_messages.append(InternalMessage(
            role="assistant",
            content=state.accumulated_text[:500],
        ))

    new_messages.append(InternalMessage(
        role="user",
        content=cfg.intervention_prompt,
    ))

    replacement = InternalRequest(
        messages=new_messages,
        stream=original_request.stream,
        model=original_request.model,
        api_format=original_request.api_format,
        raw_body=original_request.raw_body,
    )

    log.info(
        "[%s] intervention built: reason=%s, messages=%d",
        state.request_id, reason, len(new_messages),
    )

    return InterventionAction(
        should_intervene=True,
        reason=reason,
        replacement_request=replacement,
        truncated_at=state.word_count,
    )
