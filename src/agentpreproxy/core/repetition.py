from __future__ import annotations

from dataclasses import dataclass

from agentpreproxy.config import get_config
from agentpreproxy.debug.logger import get_logger

log = get_logger("core.repetition")


@dataclass
class RepetitionResult:
    detected: bool
    repeated_text: str = ""
    similarity: float = 0.0
    repeat_count: int = 0


def _char_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        return len(shorter) / len(longer)
    common = sum(1 for i, ch in enumerate(shorter) if i < len(longer) and ch == longer[i])
    return common / max(len(longer), 1)


def detect_repetition(text: str) -> RepetitionResult:
    cfg = get_config()
    min_len = cfg.repetition_min_length
    threshold = cfg.repetition_similarity

    if len(text) < min_len * 2:
        return RepetitionResult(detected=False)

    max_candidate = min(len(text) // 2, 500)

    for candidate_len in range(min_len, max_candidate + 1):
        tail = text[-candidate_len:]
        preceding = text[-(candidate_len * 2):-candidate_len]
        if not preceding:
            continue
        sim = _char_similarity(tail, preceding)
        if sim >= threshold:
            count = 1
            pos = len(text) - candidate_len
            while pos >= candidate_len:
                earlier = text[pos - candidate_len:pos]
                if _char_similarity(earlier, tail) >= threshold:
                    count += 1
                    pos -= candidate_len
                else:
                    break
            log.debug(
                "repetition detected: len=%d, sim=%.2f, count=%d",
                candidate_len, sim, count + 1,
            )
            return RepetitionResult(
                detected=True,
                repeated_text=tail[:100],
                similarity=sim,
                repeat_count=count + 1,
            )

    return RepetitionResult(detected=False)
