"""
Market Data Module
=================
Real-time market data from Binance WebSocket API.
"""

import os
import asyncio
import json
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from loguru import logger
import websockets

BINANCE_WS_URL = os.getenv("BINANCE_WS_URL", "wss://stream.binance.com:9443/ws")
PAPER_MODE = os.getenv("PAPER_MODE", "true").lower() == "true"


@dataclass
class TickerData:
    symbol: str
    price: float
    volume: float
    bid_price: float
    ask_price: float
    high_24h: float
    low_24h: float
    change_24h: float
    change_percent_24h: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class KlineData:
    symbol: str
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float
    trades: int
    interval: str
    timestamp: float = field(default_factory=time.time)


class BinanceMarketData:
    def __init__(self, symbols: List[str] = None, callbacks: Dict[str, Callable] = None):
        self.symbols = symbols or ["btcusdt", "ethusdt", "bnbusdt"]
        self.callbacks = callbacks or {}
        self.ws = None
        self.running = False
        self.reconnect_delay = 5
        self._loop = None
        self._thread = None
        self._ticker_cache: Dict[str, TickerData] = {}
        self._kline_cache: Dict[str, List[KlineData]] = {}
        
        logger.info(f"BinanceMarketData initialized for {self.symbols} (Paper Mode: {PAPER_MODE})")
    
    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_async, daemon=True)
        self._thread.start()
        logger.info("Market data feed started")
    
    def stop(self):
        self.running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Market data feed stopped")
    
    def _run_async(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._connect_loop())
    
    async def _connect_loop(self):
        while self.running:
            try:
                streams = "/".join(
                    [f"{s}@ticker" for s in self.symbols] +
                    [f"{s}@kline_1m" for s in self.symbols]
                )
                ws_url = f"{BINANCE_WS_URL}/{streams}"
                
                async with websockets.connect(ws_url) as ws:
                    self.ws = ws
                    logger.info(f"Connected to Binance WebSocket")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"WebSocket disconnected, reconnecting in {self.reconnect_delay}s...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self.running:
                await asyncio.sleep(self.reconnect_delay)
    
    async def _handle_message(self, message: str):
        try:
            data = json.loads(message)
            
            if "e" in data and data["e"] == "24hrTicker":
                ticker = self._parse_ticker(data)
                self._ticker_cache[ticker.symbol] = ticker
                
                if "ticker" in self.callbacks:
                    self.callbacks["ticker"](ticker)
                
                symbol_upper = ticker.symbol.upper()
                shared_data = {
                    "price": ticker.price,
                    "volume": ticker.volume,
                    "bid": ticker.bid_price,
                    "ask": ticker.ask_price,
                    "high": ticker.high_24h,
                    "low": ticker.low_24h,
                    "change": ticker.change_24h,
                    "change_percent": ticker.change_percent_24h,
                    "timestamp": ticker.timestamp
                }
                
                if symbol_upper in self.callbacks:
                    self.callbacks[symbol_upper](shared_data)
                    
            elif "e" in data and data["e"] == "kline":
                kline = data["k"]
                kline_data = {
                    "symbol": data["s"].lower(),
                    "open": float(kline["o"]),
                    "high": float(kline["h"]),
                    "low": float(kline["l"]),
                    "close": float(kline["c"]),
                    "volume": float(kline["v"]),
                    "timestamp": float(kline["t"]) / 1000,
                }
                if "kline" in self.callbacks:
                    self.callbacks["kline"](kline_data)
                    
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")
    
    def _parse_ticker(self, data: Dict) -> TickerData:
        symbol = data["s"].lower()
        return TickerData(
            symbol=symbol,
            price=float(data["c"]),
            volume=float(data["v"]),
            bid_price=float(data["b"]),
            ask_price=float(data["a"]),
            high_24h=float(data["h"]),
            low_24h=float(data["l"]),
            change_24h=float(data["p"]),
            change_percent_24h=float(data["P"])
        )
    
    def get_ticker(self, symbol: str) -> Optional[TickerData]:
        return self._ticker_cache.get(symbol.lower())
    
    def get_price(self, symbol: str) -> Optional[float]:
        ticker = self.get_ticker(symbol)
        return ticker.price if ticker else None
    
    def subscribe_ticker(self, callback: Callable, symbol: str = None):
        if symbol:
            self.callbacks[symbol.upper()] = callback
        else:
            self.callbacks["ticker"] = callback

    def subscribe(self, callback: Callable, symbol: str):
        self.subscribe_ticker(callback, symbol)
    
    def get_all_prices(self) -> Dict[str, float]:
        return {s: t.price for s, t in self._ticker_cache.items() if t}


class MockMarketData:
    def __init__(self, symbols: List[str] = None):
        self.symbols = symbols or ["BTCUSDT", "ETHUSDT"]
        self._running = False
        self._thread = None
        self._callbacks = {}
        self._prices = self._fetch_real_prices()
        
    def _fetch_real_prices(self) -> Dict[str, float]:
        """Fetch current prices from Binance public API."""
        import urllib.request
        import json
        prices = {}
        for symbol in self.symbols:
            try:
                api_symbol = symbol.upper()
                url = f"https://api.binance.com/api/v3/ticker/price?symbol={api_symbol}"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode())
                    prices[symbol] = float(data['price'])
            except Exception as e:
                fallback = 102000 if "btc" in symbol.lower() else 3500 if "eth" in symbol.lower() else 150 if "sol" in symbol.lower() else 650 if "bnb" in symbol.lower() else 2.20 if "xrp" in symbol.lower() else 1000
                prices[symbol] = fallback
        return prices
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._generate_data, daemon=True)
        self._thread.start()
        
    def stop(self):
        self._running = False
        
    def _generate_data(self):
        import numpy as np
        import urllib.request
        import json
        
        last_refresh = time.time()
        refresh_interval = 30  # Refresh real prices every 30 seconds
        
        while self._running:
            # Periodically refresh real prices from Binance
            if time.time() - last_refresh > refresh_interval:
                try:
                    real_prices = self._fetch_real_prices()
                    for sym, price in real_prices.items():
                        self._prices[sym] = price
                    last_refresh = time.time()
                except:
                    pass
            
            for symbol in self.symbols:
                change = np.random.randn() * 0.008  # More realistic ~0.8% volatility
                self._prices[symbol] *= (1 + change)
                
                data = {
                    "symbol": symbol,
                    "price": self._prices[symbol],
                    "volume": 100 + np.random.rand() * 500,
                    "bid": self._prices[symbol] * 0.999,
                    "ask": self._prices[symbol] * 1.001,
                    "timestamp": time.time()
                }
                
                if symbol in self._callbacks:
                    self._callbacks[symbol](data)
                    
            time.sleep(1)
    
    def subscribe(self, callback: Callable, symbol: str):
        self._callbacks[symbol] = callback
    
    def get_price(self, symbol: str) -> Optional[float]:
        symbol_upper = symbol.upper()
        if symbol_upper in self._prices:
            return self._prices[symbol_upper]
        symbol_lower = symbol.lower()
        if symbol_lower in self._prices:
            return self._prices[symbol_lower]
        for key, price in self._prices.items():
            if symbol.upper() in key.upper() or key.upper() in symbol.upper():
                return price
        return None


def get_market_data(symbols: List[str] = None, callbacks: Dict[str, Callable] = None):
    if PAPER_MODE:
        logger.info("Using MockMarketData for paper trading")
        return MockMarketData(symbols)
    else:
        logger.info("Using BinanceMarketData for live trading")
        return BinanceMarketData(symbols, callbacks)


market_data_instance: Optional[BinanceMarketData] = None


def get_market_data_instance(symbols: List[str] = None) -> BinanceMarketData:
    global market_data_instance
    if market_data_instance is None:
        market_data_instance = get_market_data(symbols)
    return market_data_instance
