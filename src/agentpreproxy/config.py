from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class WatchdogMode(str, Enum):
    STRONG = "strong"
    WEAK = "weak"
    BOTH = "both"
    OFF = "off"


@dataclass
class Config:
    # --- proxy ---
    listen_host: str = "127.0.0.1"
    listen_port: int = 8600

    openai_base_url: str = "https://api.openai.com"
    anthropic_base_url: str = "https://api.anthropic.com"

    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- tag ---
    tag_open: str = "⟪"   # ⟪
    tag_close: str = "⟫"  # ⟫
    tag_prefix: str = "WD"

    # --- watchdog ---
    watchdog_mode: WatchdogMode = WatchdogMode.BOTH
    strong_k: int = 50
    strong_tolerance: int = 20

    # --- weak mode ---
    repetition_min_length: int = 30
    repetition_similarity: float = 0.85
    repetition_window: int = 3

    # --- intervention ---
    intervention_enabled: bool = True
    intervention_prompt: str = (
        "你之前的输出出现了异常重复。"
        "请停下来，重新审视用户最初的请求，然后从上次有效内容之后继续。"
    )

    # --- debug ---
    debug: bool = False
    log_level: str = "INFO"
    debug_endpoints: bool = True

    @classmethod
    def from_env(cls) -> Config:
        cfg = cls()
        for fld in cfg.__dataclass_fields__:
            env_key = f"APP_{fld.upper()}"
            env_val = os.environ.get(env_key)
            if env_val is None:
                continue
            current = getattr(cfg, fld)
            if isinstance(current, bool):
                setattr(cfg, fld, env_val.lower() in ("1", "true", "yes"))
            elif isinstance(current, int):
                setattr(cfg, fld, int(env_val))
            elif isinstance(current, float):
                setattr(cfg, fld, float(env_val))
            elif isinstance(current, WatchdogMode):
                setattr(cfg, fld, WatchdogMode(env_val))
            else:
                setattr(cfg, fld, env_val)
        return cfg

    def tag_pattern_str(self) -> str:
        return f"{self.tag_open}{self.tag_prefix}:N{self.tag_close}"

    def format_tag(self, n: int) -> str:
        return f"{self.tag_open}{self.tag_prefix}:{n}{self.tag_close}"


_global_config: Config | None = None


def get_config() -> Config:
    global _global_config
    if _global_config is None:
        _global_config = Config.from_env()
    return _global_config


def set_config(cfg: Config) -> None:
    global _global_config
    _global_config = cfg
