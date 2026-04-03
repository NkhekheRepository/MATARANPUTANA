#!/usr/bin/env python3
"""
Live Trading System Entry Point
================================
Starts the VN.PY TradingEngine + FastAPI API Gateway.
Supports paper, testnet, and live modes via TRADING_MODE env var.
"""

import os
import sys
import signal
import time
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

proj_root = Path(__file__).parent
sys.path.insert(0, str(proj_root))

load_dotenv()

logger.add("logs/live_trading.log", rotation="10 MB", retention="7 days")


def main():
    trading_mode = os.getenv("TRADING_MODE", "paper")
    server_type = os.getenv("BINANCE_SERVER", "REAL")

    logger.info("=" * 60)
    logger.info("FINANCIAL ORCHESTRATOR — LIVE TRADING ENGINE")
    logger.info("=" * 60)
    logger.info(f"Mode: {trading_mode}")
    logger.info(f"Server: {server_type}")
    logger.info(f"API Gateway: http://0.0.0.0:8000")

    if trading_mode == "live" and server_type == "REAL":
        logger.critical("*** LIVE TRADING WITH REAL CAPITAL ***")
    elif trading_mode == "live" and server_type == "TESTNET":
        logger.info("Running on TESTNET — simulated capital")
    else:
        logger.info("Paper trading mode — no real orders")
    logger.info("=" * 60)

    from vnpy_engine.vnpy_local.main_engine import get_engine
    from vnpy_engine.vnpy_local.api_gateway_enhanced import app

    engine = get_engine()

    def shutdown_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        try:
            engine.stop()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        import uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        engine.stop()


if __name__ == "__main__":
    main()
