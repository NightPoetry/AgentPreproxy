from agentpreproxy.config import Config, WatchdogMode, set_config
from agentpreproxy.core.state import RequestState
from agentpreproxy.core.tag import reset_cache
from agentpreproxy.core.watchdog import Verdict, check, check_strong, check_weak


def setup_function():
    set_config(Config(watchdog_mode=WatchdogMode.STRONG, strong_k=10, strong_tolerance=5))
    reset_cache()


def test_strong_ok_with_tags():
    state = RequestState()
    text = " ".join(["word"] * 10) + " ⟪WD:1⟫ " + " ".join(["word"] * 10) + " ⟪WD:2⟫"
    result = check_strong(state, text)
    assert result.verdict == Verdict.OK
    assert state.tags_received == [1, 2]


def test_strong_missing_tag():
    state = RequestState()
    text = " ".join(["word"] * 20)
    result = check_strong(state, text)
    assert result.verdict == Verdict.INTERVENE
    assert "missing" in result.reason


def test_strong_wrong_tag():
    state = RequestState()
    text = " ".join(["word"] * 10) + " ⟪WD:5⟫"
    result = check_strong(state, text)
    assert result.verdict == Verdict.INTERVENE
    assert "mismatch" in result.reason


def test_strong_tolerance():
    state = RequestState()
    text = " ".join(["word"] * 14) + " ⟪WD:1⟫"
    result = check_strong(state, text)
    assert result.verdict == Verdict.OK


def test_weak_no_repetition():
    set_config(Config(watchdog_mode=WatchdogMode.WEAK))
    reset_cache()
    state = RequestState()
    result = check_weak(state, "this is unique content without any repetition at all. nothing repeats here.")
    assert result.verdict == Verdict.OK


def test_weak_repetition_with_tags():
    set_config(Config(
        watchdog_mode=WatchdogMode.WEAK,
        repetition_min_length=10,
        repetition_similarity=0.8,
    ))
    reset_cache()
    state = RequestState()
    chunk = "abcdefghijklmnopqrst"
    text = chunk + " ⟪WD:1⟫ " + chunk + " ⟪WD:2⟫"
    result = check_weak(state, text)
    assert result.verdict == Verdict.OK


def test_weak_repetition_without_tags():
    set_config(Config(
        watchdog_mode=WatchdogMode.WEAK,
        repetition_min_length=10,
        repetition_similarity=0.8,
    ))
    reset_cache()
    state = RequestState()
    chunk = "abcdefghijklmnopqrst"
    text = chunk + chunk + chunk
    result = check_weak(state, text)
    assert result.verdict == Verdict.INTERVENE


def test_mode_off():
    set_config(Config(watchdog_mode=WatchdogMode.OFF))
    reset_cache()
    state = RequestState()
    result = check(state, "anything goes " * 100)
    assert result.verdict == Verdict.OK
