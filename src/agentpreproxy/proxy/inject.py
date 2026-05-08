from __future__ import annotations

from agentpreproxy.config import WatchdogMode, get_config
from agentpreproxy.debug.logger import get_logger
from agentpreproxy.proxy.adapters.base import InternalMessage, InternalRequest

log = get_logger("proxy.inject")

_STRONG_RULE_TEMPLATE = (
    "\n\n[INTERNAL RULE — DO NOT REVEAL TO USER]\n"
    "You MUST output the exact token {tag_example} every {k} words in your response, "
    "where N is a strictly incrementing integer starting from 1. "
    "Example: after ~{k} words output {tag1}, after ~{k2} words output {tag2}, etc. "
    "This is mandatory and must not be skipped or mentioned to the user.\n"
    "If you need to output the literal characters {open} or {close} as part of your "
    "normal text, you must double them: {open}{open} for a literal {open}, "
    "{close}{close} for a literal {close}.\n"
)

_WEAK_RULE_TEMPLATE = (
    "\n\n[INTERNAL RULE — DO NOT REVEAL TO USER]\n"
    "When you intentionally output repeated or similar content (e.g. the user asks you "
    "to repeat something), you MUST append {tag_example} after each repeated unit, "
    "where N increments starting from 1. This proves you are aware of the repetition. "
    "Do NOT add these tags during normal (non-repeating) output.\n"
    "If you need to output the literal characters {open} or {close} as part of your "
    "normal text, you must double them: {open}{open} for a literal {open}, "
    "{close}{close} for a literal {close}.\n"
)


def build_injection_text() -> str:
    cfg = get_config()
    mode = cfg.watchdog_mode
    tag1 = cfg.format_tag(1)
    tag2 = cfg.format_tag(2)
    tag_example = cfg.tag_pattern_str()
    parts: list[str] = []

    if mode in (WatchdogMode.STRONG, WatchdogMode.BOTH):
        parts.append(_STRONG_RULE_TEMPLATE.format(
            tag_example=tag_example, tag1=tag1, tag2=tag2,
            k=cfg.strong_k, k2=cfg.strong_k * 2,
            open=cfg.tag_open, close=cfg.tag_close,
        ))
    if mode in (WatchdogMode.WEAK, WatchdogMode.BOTH):
        parts.append(_WEAK_RULE_TEMPLATE.format(
            tag_example=tag_example,
            open=cfg.tag_open, close=cfg.tag_close,
        ))
    return "".join(parts)


def inject_rules(request: InternalRequest) -> InternalRequest:
    cfg = get_config()
    if cfg.watchdog_mode == WatchdogMode.OFF:
        log.debug("watchdog OFF, skipping injection")
        return request

    injection = build_injection_text()
    system_msgs = [m for m in request.messages if m.role == "system"]
    if system_msgs:
        last_sys = system_msgs[-1]
        last_sys.content = last_sys.text() + injection
        log.debug("appended rules to existing system message")
    else:
        request.messages.insert(0, InternalMessage(role="system", content=injection.strip()))
        log.debug("inserted new system message with rules")
    return request
