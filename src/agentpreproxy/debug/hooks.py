from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from agentpreproxy.debug.logger import get_logger

log = get_logger("hooks")

Callback = Callable[..., None]


@dataclass
class DebugHooks:
    _listeners: dict[str, list[Callback]] = field(default_factory=dict)

    # ---- registration ----

    def on(self, event: str, cb: Callback) -> None:
        self._listeners.setdefault(event, []).append(cb)

    def off(self, event: str, cb: Callback) -> None:
        cbs = self._listeners.get(event, [])
        if cb in cbs:
            cbs.remove(cb)

    # ---- fire ----

    def fire(self, event: str, **kwargs: Any) -> None:
        log.debug("hook fired: %s  kwargs=%s", event, list(kwargs.keys()))
        for cb in self._listeners.get(event, []):
            try:
                cb(**kwargs)
            except Exception:
                log.exception("hook callback error for event=%s", event)

    # ---- convenience shortcuts ----

    def request_received(self, **kw: Any) -> None:
        self.fire("request_received", **kw)

    def request_forwarded(self, **kw: Any) -> None:
        self.fire("request_forwarded", **kw)

    def tag_parsed(self, **kw: Any) -> None:
        self.fire("tag_parsed", **kw)

    def tag_missing(self, **kw: Any) -> None:
        self.fire("tag_missing", **kw)

    def repetition_detected(self, **kw: Any) -> None:
        self.fire("repetition_detected", **kw)

    def intervention_triggered(self, **kw: Any) -> None:
        self.fire("intervention_triggered", **kw)

    def response_sent(self, **kw: Any) -> None:
        self.fire("response_sent", **kw)


_global_hooks: DebugHooks | None = None


def get_hooks() -> DebugHooks:
    global _global_hooks
    if _global_hooks is None:
        _global_hooks = DebugHooks()
    return _global_hooks


def set_hooks(hooks: DebugHooks) -> None:
    global _global_hooks
    _global_hooks = hooks
