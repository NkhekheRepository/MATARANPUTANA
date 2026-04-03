#!/usr/bin/env python3
"""
Binance Exchange Connector
Real-time market data via WebSocket and REST
"""

import os
import sys
import time
import json
import logging
import asyncio
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    logging.warning("websockets not available")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base import BaseExchangeConnector, TickData, OrderBookData, KlineData, FeedStatus

logger = logging.getLogger('BinanceConnector')


class BinanceConnector(BaseExchangeConnector):
    """
    Binance exchange connector for real-time market data.
    Supports WebSocket for live data and REST for historical data.
    """
    
    def __init__(
        self,
        symbols: List[str],
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__("Binance", symbols, config)
        
        self.ws_endpoint = self.config.get('ws_endpoint', 'wss://stream.binance.com:9443/ws')
        self.rest_endpoint = self.config.get('rest_endpoint', 'https://api.binance.com/api/v3')
        
        self._ws = None
        self._ws_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_thread: Optional[threading.Thread] = None
        
        self._ticker_subscriptions = set()
        self._orderbook_subscriptions = set()
        self._kline_subscriptions = set()
        
        self._last_orderbook_update: Dict[str, int] = {}
        self._sequence_number = 0
        
    def connect(self) -> bool:
        """Connect to Binance WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            logger.error("websockets library not available")
            self.status = FeedStatus.ERROR
            return False
            
        try:
            self.status = FeedStatus.CONNECTING
            self._start_ws_loop()
            self.status = FeedStatus.CONNECTED
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Binance: {e}")
            self.status = FeedStatus.ERROR
            return False
    
    def _start_ws_loop(self):
        """Start WebSocket connection in a thread"""
        self._ws_thread = threading.Thread(target=self._run_ws_async, daemon=True)
        self._ws_thread.start()
    
    def _run_ws_async(self):
        """Run async WebSocket loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._ws_loop = loop
        loop.run_until_complete(self._ws_connect())
    
    async def _ws_connect(self):
        """Connect to Binance WebSocket"""
        streams = []
        
        for symbol in self.symbols:
            streams.append(f"{symbol.lower()}@ticker")
        
        ws_url = f"{self.ws_endpoint}/{'/'.join(streams)}"
        
        try:
            async with websockets.connect(ws_url, ping_interval=30) as ws:
                self._ws = ws
                logger.info(f"Binance WebSocket connected")
                
                async for message in ws:
                    if not self._running:
                        break
                    self._handle_message(message)
                    
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"Binance WebSocket closed: {e}")
            self.status = FeedStatus.RECONNECTING
            await self._reconnect()
        except Exception as e:
            logger.error(f"Binance WebSocket error: {e}")
            self._emit_error(e)
            self.status = FeedStatus.ERROR
    
    async def _reconnect(self):
        """Reconnect to Binance WebSocket"""
        for attempt in range(5):
            if not self._running:
                break
            try:
                await asyncio.sleep(2 ** attempt)
                await self._ws_connect()
                return
            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt + 1} failed: {e}")
                
        self.status = FeedStatus.ERROR
    
    def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            if 'e' in data:
                event_type = data['e']
                
                if event_type == '24hrTicker':
                    self._handle_ticker(data)
                elif event_type == 'depthUpdate':
                    self._handle_orderbook(data)
                elif event_type == 'kline':
                    self._handle_kline(data)
                    
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    def _handle_ticker(self, data: Dict):
        """Handle ticker update"""
        symbol = data['s']
        receive_time = time.time()
        
        tick = TickData(
            symbol=symbol,
            price=float(data['c']),
            volume=float(data['v']),
            bid=float(data['b']),
            ask=float(data['a']),
            timestamp=data['E'] / 1000.0,
            source="binance",
            sequence=self._sequence_number
        )
        
        latency = (receive_time - tick.timestamp) * 1000
        self.record_latency(latency)
        
        self._sequence_number += 1
        self._emit_tick(tick)
    
    def _handle_orderbook(self, data: Dict):
        """Handle order book update"""
        symbol = data['s']
        update_id = data['u']
        
        if update_id <= self._last_orderbook_update.get(symbol, 0):
            return
            
        self._last_orderbook_update[symbol] = update_id
        
        orderbook = OrderBookData(
            symbol=symbol,
            bids=[[float(b[0]), float(b[1])] for b in data.get('b', [])],
            asks=[[float(a[0]), float(a[1])] for a in data.get('a', [])],
            last_update_id=update_id,
            timestamp=data['E'] / 1000.0,
            source="binance"
        )
        
        self._emit_orderbook(orderbook)
    
    def _handle_kline(self, data: Dict):
        """Handle kline/candlestick update"""
        kline = data['k']
        
        kline_data = KlineData(
            symbol=kline['s'],
            interval=kline['i'],
            open_time=kline['t'],
            open=float(kline['o']),
            high=float(kline['h']),
            low=float(kline['l']),
            close=float(kline['c']),
            volume=float(kline['v']),
            close_time=kline['T'],
            quote_volume=float(kline['q']),
            trades=kline['n'],
            source="binance"
        )
        
        self._emit_kline(kline_data)
    
    def disconnect(self) -> bool:
        """Disconnect from Binance"""
        self._running = False
        
        if self._ws:
            try:
                asyncio.set_event_loop(asyncio.new_event_loop())
            except:
                pass
                
        self.status = FeedStatus.DISCONNECTED
        logger.info("Binance WebSocket disconnected")
        return True
    
    def subscribe_ticker(self, symbols: Optional[List[str]] = None) -> bool:
        """Subscribe to ticker - handled in connect"""
        target_symbols = symbols or self.symbols
        self._ticker_subscriptions.update(target_symbols)
        
        if self._ws and self.status == FeedStatus.CONNECTED:
            logger.info(f"Subscribed to tickers: {target_symbols}")
            
        return True
    
    def subscribe_orderbook(self, symbols: Optional[List[str]] = None) -> bool:
        """Subscribe to order book"""
        target_symbols = symbols or self.symbols
        self._orderbook_subscriptions.update(target_symbols)
        logger.info(f"Order book subscriptions: {target_symbols}")
        return True
    
    def subscribe_kline(self, symbols: Optional[List[str]] = None, interval: str = "1m") -> bool:
        """Subscribe to kline"""
        target_symbols = symbols or self.symbols
        self._kline_subscriptions.update([f"{s}@{interval}" for s in target_symbols])
        logger.info(f"Kline subscriptions: {target_symbols} @ {interval}")
        return True
    
    def get_rest_ticker(self, symbol: str) -> Optional[TickData]:
        """Get current ticker via REST API"""
        if not REQUESTS_AVAILABLE:
            return None
            
        try:
            url = f"{self.rest_endpoint}/ticker/24hr"
            params = {'symbol': symbol.upper()}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return TickData(
                    symbol=data['symbol'],
                    price=float(data['lastPrice']),
                    volume=float(data['volume']),
                    bid=float(data['bidPrice']),
                    ask=float(data['askPrice']),
                    timestamp=time.time(),
                    source="binance_rest"
                )
        except Exception as e:
            logger.error(f"REST ticker error: {e}")
            
        return None
    
    def get_rest_orderbook(self, symbol: str, limit: int = 20) -> Optional[OrderBookData]:
        """Get order book via REST API"""
        if not REQUESTS_AVAILABLE:
            return None
            
        try:
            url = f"{self.rest_endpoint}/depth"
            params = {'symbol': symbol.upper(), 'limit': limit}
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return OrderBookData(
                    symbol=symbol.upper(),
                    bids=[[float(b[0]), float(b[1])] for b in data['bids']],
                    asks=[[float(a[0]), float(a[1])] for a in data['asks']],
                    last_update_id=data.get('lastUpdateId', 0),
                    timestamp=time.time(),
                    source="binance_rest"
                )
        except Exception as e:
            logger.error(f"REST orderbook error: {e}")
            
        return None
    
    def get_rest_klines(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 500
    ) -> List[KlineData]:
        """Get historical klines via REST API"""
        klines = []
        
        if not REQUESTS_AVAILABLE:
            return klines
            
        try:
            url = f"{self.rest_endpoint}/klines"
            params = {
                'symbol': symbol.upper(),
                'interval': interval,
                'limit': limit
            }
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for k in data:
                    klines.append(KlineData(
                        symbol=symbol.upper(),
                        interval=interval,
                        open_time=k[0],
                        open=float(k[1]),
                        high=float(k[2]),
                        low=float(k[3]),
                        close=float(k[4]),
                        volume=float(k[5]),
                        close_time=k[6],
                        quote_volume=float(k[7]),
                        trades=k[8],
                        source="binance_rest"
                    ))
        except Exception as e:
            logger.error(f"REST klines error: {e}")
            
        return klines
