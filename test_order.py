#!/usr/bin/env python3
"""Test order placement on Binance Testnet."""

import os
import sys
from pathlib import Path

proj_root = Path(__file__).parent
sys.path.insert(0, str(proj_root))

from dotenv import load_dotenv
load_dotenv()

from paper_trading.layers.layer1_data.binance_live import BinanceLiveClient

def main():
    client = BinanceLiveClient(
        api_key=os.getenv('BINANCE_API_KEY'),
        api_secret=os.getenv('BINANCE_SECRET_KEY'),
        testnet=True
    )
    
    print("=" * 50)
    print("Binance Testnet Order Test")
    print("=" * 50)
    
    # Get account
    account = client.get_account()
    print(f"\nAccount: {account}")
    
    # Get price
    price = client.get_symbol_price('BTCUSDT')
    print(f"BTCUSDT Price: ${price}")
    
    # Place test buy order (smallest amount: 0.00001 BTC)
    print("\n--- Placing TEST BUY ORDER ---")
    order = client.market_buy('BTCUSDT', 0.0001)
    print(f"Order Result: {order}")
    
    # Check open orders
    open_orders = client.get_open_orders('BTCUSDT')
    print(f"Open Orders: {open_orders}")
    
    print("\n" + "=" * 50)
    print("Test Complete!")
    print("=" * 50)

if __name__ == "__main__":
    main()
