from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum

from agentpreproxy.debug.logger import get_logger

log = get_logger("core.state")


class RequestStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    INTERVENED = "intervened"


@dataclass
class RequestState:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    status: RequestStatus = RequestStatus.ACTIVE

    word_count: int = 0
    tag_expected: int = 1
    tags_received: list[int] = field(default_factory=list)
    accumulated_text: str = ""

    repetition_flags: int = 0
    intervention_count: int = 0

    def record_words(self, text: str) -> int:
        words = len(text.split())
        self.word_count += words
        self.accumulated_text += text
        return self.word_count

    def record_tag(self, value: int) -> None:
        self.tags_received.append(value)
        log.debug("[%s] tag received: %d (expected %d)", self.request_id, value, self.tag_expected)
        self.tag_expected = value + 1

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "word_count": self.word_count,
            "tag_expected": self.tag_expected,
            "tags_received": list(self.tags_received),
            "repetition_flags": self.repetition_flags,
            "intervention_count": self.intervention_count,
            "age_seconds": round(time.time() - self.created_at, 1),
        }


_active_states: dict[str, RequestState] = {}


def create_state() -> RequestState:
    state = RequestState()
    _active_states[state.request_id] = state
    log.debug("created state %s", state.request_id)
    return state


def get_state(request_id: str) -> RequestState | None:
    return _active_states.get(request_id)


def remove_state(request_id: str) -> None:
    _active_states.pop(request_id, None)


def all_states() -> dict[str, RequestState]:
    return dict(_active_states)
