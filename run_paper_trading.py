#!/usr/bin/env python3
"""
Paper Trading System Launcher
=============================
Starts the autonomous paper trading system with:
- Dashboard (Flask)
- Telegram Bot (optional)
- Paper Trading Engine

Usage:
    python run_paper_trading.py              # Start everything
    python run_paper_trading.py --dashboard   # Dashboard only
    python run_paper_trading.py --engine      # Engine only
    python run_paper_trading.py --telegram    # Telegram bot only
"""

import os
import sys
import argparse
import signal
from pathlib import Path
from loguru import logger

proj_root = Path(__file__).parent
sys.path.insert(0, str(proj_root))

from dotenv import load_dotenv
load_dotenv()

logger.add("logs/paper_trading.log", rotation="10 MB", retention="7 days")

engine = None
dashboard_thread = None
telegram_app = None


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info("Shutting down...")
    if engine:
        engine.stop()
    sys.exit(0)


def start_engine(config_path: str = None):
    """Start the paper trading engine."""
    global engine
    
    from paper_trading.engine import PaperTradingEngine
    
    logger.info("Starting Paper Trading Engine...")
    
    engine = PaperTradingEngine(config_path)
    engine.start()
    
    logger.info(f"Engine started: capital=${engine.capital}, leverage={engine.leverage}x")
    
    return engine


def start_dashboard(engine=None, host: str = "0.0.0.0", port: int = 8080):
    """Start the web dashboard."""
    from paper_trading.dashboard.app import create_app
    import paper_trading.dashboard.app as dashboard_app
    import threading
    from werkzeug.serving import make_server
    
    dashboard_app.engine = engine
    app = create_app(engine)
    
    ports_to_try = [port] + list(range(port + 1, port + 10))
    
    for try_port in ports_to_try:
        try:
            logger.info(f"Starting Dashboard on {host}:{try_port}...")
            server = make_server(host, try_port, app, threaded=True)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            logger.info(f"Dashboard server started on port {try_port}")
            return
        except OSError as e:
            logger.warning(f"Port {try_port} unavailable: {e}")
            continue
    
    raise RuntimeError(f"Could not bind to any port {ports_to_try}")


def start_telegram_bot():
    """Start the Telegram bot."""
    from paper_trading.telegram_commands import setup_bot, set_engine
    
    global telegram_app, engine
    
    logger.info("Starting Telegram Bot...")
    
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    
    if not token or token == 'YOUR_BOT_TOKEN_HERE':
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping Telegram bot")
        return None
    
    telegram_app = setup_bot(token)
    
    if engine:
        set_engine(engine)
    
    telegram_app.run_polling(drop_pending_updates=True)
    
    return telegram_app


def start_all():
    """Start all components."""
    global engine, dashboard_thread
    
    engine = start_engine()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    import threading
    
    dashboard_thread = threading.Thread(
        target=start_dashboard, 
        args=(engine,),
        daemon=True
    )
    dashboard_thread.start()
    
    import time
    time.sleep(3)
    
    # Check multiple ports for dashboard
    dashboard_ready = False
    for port in [8080, 8081, 8082]:
        try:
            import urllib.request
            urllib.request.urlopen(f"http://localhost:{port}/", timeout=3)
            logger.info(f"Dashboard verified accessible on port {port}")
            dashboard_ready = True
            break
        except:
            continue
    
    if not dashboard_ready:
        logger.warning("Dashboard not yet accessible")
    
    # Start Telegram bot in background thread if configured
    telegram_thread = threading.Thread(
        target=start_telegram_bot,
        daemon=False
    )
    telegram_thread.start()
    
    logger.info("=" * 50)
    logger.info("Paper Trading System Started")
    logger.info("=" * 50)
    logger.info(f"Dashboard: http://localhost:8080")
    logger.info(f"Engine: Running (capital=${engine.capital}, leverage={engine.leverage}x)")
    logger.info("=" * 50)
    
    try:
        while True:
            import time
            time.sleep(10)
            
            status = engine.get_status()
            logger.debug(f"Status: {status.get('running')}, regime: {status.get('current_regime')}")
            
    except KeyboardInterrupt:
        logger.info("Interrupted...")
        engine.stop()
    
    except Exception as e:
        logger.error(f"Error: {e}")
        engine.stop()
        raise


def main():
    parser = argparse.ArgumentParser(description='Paper Trading System')
    parser.add_argument('--dashboard', action='store_true', help='Start dashboard only')
    parser.add_argument('--engine', action='store_true', help='Start engine only')
    parser.add_argument('--telegram', action='store_true', help='Start Telegram bot only')
    parser.add_argument('--host', default='0.0.0.0', help='Dashboard host')
    parser.add_argument('--port', type=int, default=8080, help='Dashboard port')
    parser.add_argument('--config', help='Config file path')
    
    args = parser.parse_args()
    
    if args.dashboard and args.engine:
        start_all()
    elif args.dashboard:
        start_dashboard(host=args.host, port=args.port)
    elif args.engine:
        start_engine(args.config)
        import time
        while True:
            time.sleep(1)
    elif args.telegram:
        start_telegram_bot()
    else:
        start_all()


if __name__ == "__main__":
    main()
