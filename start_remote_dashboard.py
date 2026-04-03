#!/usr/bin/env python3
"""
Start Paper Trading Dashboard with Remote Access (ngrok)
===========================================================
"""

import os
import sys
import time
import signal
import subprocess
from pathlib import Path

# Add project to path
proj_root = Path(__file__).parent
sys.path.insert(0, str(proj_root))

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    print("=" * 60)
    print("  Paper Trading Dashboard - Remote Access")
    print("=" * 60)
    print()
    
    # Step 1: Start paper trading system
    print("[1/4] Starting paper trading system...")
    os.chdir(proj_root)
    
    # Start the paper trading in background
    proc = subprocess.Popen(
        [str(proj_root / "venv/bin/python"), "run_paper_trading.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True
    )
    print(f"  Started (PID: {proc.pid})")
    
    # Wait for dashboard to be ready
    print("  Waiting for dashboard to start...")
    time.sleep(8)
    
    # Step 2: Start ngrok tunnel
    print("[2/4] Starting ngrok tunnel...")
    from pyngrok import ngrok
    
    # Connect to ngrok (will prompt for auth token if not configured)
    try:
        # Create HTTP tunnel to port 8080
        tunnel = ngrok.connect(8080, "http", name="paper-trading-dashboard")
        public_url = tunnel.public_url
        print(f"  Tunnel created: {public_url}")
    except Exception as e:
        print(f"  Error: {e}")
        print()
        print("  To use ngrok, you need to:")
        print("  1. Sign up at https://ngrok.com (free)")
        print("  2. Get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken")
        print("  3. Run: ngrok config add-authtoken YOUR_AUTH_TOKEN")
        print("  4. Run this script again")
        print()
        proc.terminate()
        sys.exit(1)
    
    # Step 3: Display access info
    print()
    print("=" * 60)
    print("  Dashboard is now accessible!")
    print("=" * 60)
    print()
    print(f"  URL: {public_url}")
    print()
    print("  Login credentials:")
    print("  ─────────────────")
    print("  Username: admin")
    print("  Password: PtTr@2026!xK9m")
    print()
    print("  Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()
        print("Shutting down...")
    
    # Cleanup
    print("Stopping ngrok...")
    ngrok.disconnect(tunnel)
    ngrok.kill()
    
    print("Stopping paper trading...")
    proc.terminate()
    proc.wait()
    
    print("Done.")

if __name__ == "__main__":
    main()