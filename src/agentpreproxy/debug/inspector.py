from __future__ import annotations

from fastapi import APIRouter

from agentpreproxy.config import get_config
from agentpreproxy.core.state import all_states
from agentpreproxy.debug.logger import get_logger

log = get_logger("debug.inspector")

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/state")
async def debug_state():
    states = all_states()
    return {rid: s.to_dict() for rid, s in states.items()}


@router.get("/config")
async def debug_config():
    cfg = get_config()
    return {
        fld: str(getattr(cfg, fld))
        for fld in cfg.__dataclass_fields__
        if fld not in ("openai_api_key", "anthropic_api_key")
    }


@router.post("/config")
async def debug_update_config(updates: dict):
    cfg = get_config()
    applied = {}
    for key, val in updates.items():
        if hasattr(cfg, key) and key not in ("openai_api_key", "anthropic_api_key"):
            current = getattr(cfg, key)
            if isinstance(current, bool):
                setattr(cfg, key, bool(val))
            elif isinstance(current, int):
                setattr(cfg, key, int(val))
            elif isinstance(current, float):
                setattr(cfg, key, float(val))
            else:
                setattr(cfg, key, val)
            applied[key] = str(getattr(cfg, key))
            log.info("config updated: %s = %s", key, getattr(cfg, key))
    return {"applied": applied}


@router.get("/stats")
async def debug_stats():
    states = all_states()
    return {
        "active_requests": len(states),
        "total_tags": sum(len(s.tags_received) for s in states.values()),
        "total_interventions": sum(s.intervention_count for s in states.values()),
        "total_repetition_flags": sum(s.repetition_flags for s in states.values()),
    }
