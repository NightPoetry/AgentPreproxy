from __future__ import annotations

import argparse

import uvicorn

from agentpreproxy.config import Config, WatchdogMode, set_config
from agentpreproxy.debug.logger import setup_logging


def build_app():
    from agentpreproxy.debug.inspector import router as debug_router
    from agentpreproxy.proxy.server import app

    cfg = Config.from_env()
    if cfg.debug_endpoints:
        app.include_router(debug_router)
    return app


def main():
    parser = argparse.ArgumentParser(description="AgentPreproxy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8600)
    parser.add_argument("--mode", choices=["strong", "weak", "both", "off"], default="both")
    parser.add_argument("--strong-k", type=int, default=50)
    parser.add_argument("--openai-url", default="https://api.openai.com")
    parser.add_argument("--anthropic-url", default="https://api.anthropic.com")
    parser.add_argument("--openai-key", default="")
    parser.add_argument("--anthropic-key", default="")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    cfg = Config(
        listen_host=args.host,
        listen_port=args.port,
        watchdog_mode=WatchdogMode(args.mode),
        strong_k=args.strong_k,
        openai_base_url=args.openai_url,
        anthropic_base_url=args.anthropic_url,
        openai_api_key=args.openai_key,
        anthropic_api_key=args.anthropic_key,
        debug=args.debug,
        log_level=args.log_level,
        debug_endpoints=args.debug,
    )
    set_config(cfg)
    setup_logging(cfg.log_level)

    app = build_app()
    uvicorn.run(app, host=cfg.listen_host, port=cfg.listen_port, log_level="info")


if __name__ == "__main__":
    main()
