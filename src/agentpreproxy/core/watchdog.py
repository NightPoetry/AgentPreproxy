from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agentpreproxy.config import WatchdogMode, get_config
from agentpreproxy.core.repetition import detect_repetition
from agentpreproxy.core.state import RequestState
from agentpreproxy.core.tag import ParsedTag, parse_tags
from agentpreproxy.debug.hooks import get_hooks
from agentpreproxy.debug.logger import get_logger

log = get_logger("core.watchdog")


class Verdict(str, Enum):
    OK = "ok"
    INTERVENE = "intervene"


@dataclass
class CheckResult:
    verdict: Verdict
    reason: str = ""


def check_strong(state: RequestState, new_text: str) -> CheckResult:
    cfg = get_config()
    k = cfg.strong_k
    tolerance = cfg.strong_tolerance

    tags = parse_tags(new_text)
    clean_words = new_text.split()
    state.record_words(new_text)

    for tag in tags:
        hooks = get_hooks()
        if tag.value == state.tag_expected:
            state.record_tag(tag.value)
            hooks.tag_parsed(value=tag.value, expected=tag.value)
        else:
            log.warning(
                "[%s] tag mismatch: got %d, expected %d",
                state.request_id, tag.value, state.tag_expected,
            )
            hooks.tag_parsed(value=tag.value, expected=state.tag_expected)
            return CheckResult(
                verdict=Verdict.INTERVENE,
                reason=f"tag mismatch: got {tag.value}, expected {state.tag_expected}",
            )

    words_since_last_tag = state.word_count - (len(state.tags_received) * k)
    if words_since_last_tag > k + tolerance:
        log.warning(
            "[%s] tag missing: %d words since last tag (limit %d+%d)",
            state.request_id, words_since_last_tag, k, tolerance,
        )
        get_hooks().tag_missing(
            expected=state.tag_expected, word_count=words_since_last_tag,
        )
        return CheckResult(
            verdict=Verdict.INTERVENE,
            reason=f"tag missing: {words_since_last_tag} words without tag",
        )

    return CheckResult(verdict=Verdict.OK)


def check_weak(state: RequestState, new_text: str) -> CheckResult:
    state.record_words(new_text)
    rep = detect_repetition(state.accumulated_text)

    if not rep.detected:
        return CheckResult(verdict=Verdict.OK)

    state.repetition_flags += 1
    get_hooks().repetition_detected(
        repeated_text=rep.repeated_text, similarity=rep.similarity,
    )
    log.info(
        "[%s] repetition detected (sim=%.2f), checking tags",
        state.request_id, rep.similarity,
    )

    tags = parse_tags(new_text)
    if tags and tags[-1].value == state.tag_expected - 1 or (tags and tags[-1].value >= 1):
        for tag in tags:
            state.record_tag(tag.value)
        log.info("[%s] tags present during repetition → controlled, passing", state.request_id)
        return CheckResult(verdict=Verdict.OK)

    log.warning("[%s] repetition without valid tags → runaway", state.request_id)
    return CheckResult(
        verdict=Verdict.INTERVENE,
        reason=f"repetition (sim={rep.similarity:.2f}) without valid counting tags",
    )


def check(state: RequestState, new_text: str) -> CheckResult:
    cfg = get_config()
    mode = cfg.watchdog_mode

    if mode == WatchdogMode.OFF:
        return CheckResult(verdict=Verdict.OK)

    if mode == WatchdogMode.STRONG:
        return check_strong(state, new_text)

    if mode == WatchdogMode.WEAK:
        return check_weak(state, new_text)

    # BOTH: strong first, then weak
    result = check_strong(state, new_text)
    if result.verdict == Verdict.INTERVENE:
        return result
    return check_weak(state, new_text)
