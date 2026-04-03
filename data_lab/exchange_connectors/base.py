#!/usr/bin/env python3
"""
Base Exchange Connector
Abstract class for exchange data feed implementations
"""

import os
import sys
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('ExchangeConnector')


class FeedStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class TickData:
    """Single tick data point"""
    symbol: str
    price: float
    volume: float
    bid: float = 0.0
    ask: float = 0.0
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"
    sequence: int = 0


@dataclass
class OrderBookData:
    """Order book depth data"""
    symbol: str
    bids: List[List[float]] = field(default_factory=list)
    asks: List[List[float]] = field(default_factory=list)
    last_update_id: int = 0
    timestamp: float = field(default_factory=time.time)
    source: str = "unknown"


@dataclass
class KlineData:
    """OHLCV/kline data"""
    symbol: str
    interval: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float = 0.0
    trades: int = 0
    source: str = "unknown"


class BaseExchangeConnector(ABC):
    """
    Abstract base class for exchange connectors.
    All exchange implementations should inherit from this class.
    """
    
    def __init__(
        self,
        name: str,
        symbols: List[str],
        config: Optional[Dict[str, Any]] = None
    ):
        self.name = name
        self.symbols = [s.upper() for s in symbols]
        self.config = config or {}
        
        self.status = FeedStatus.DISCONNECTED
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        self._tick_callbacks: List[Callable] = []
        self._orderbook_callbacks: List[Callable] = []
        self._kline_callbacks: List[Callable] = []
        self._error_callbacks: List[Callable] = []
        
        self._last_tick_time: Dict[str, float] = {}
        self._tick_count = 0
        self._error_count = 0
        
        self._tick_latencies: List[float] = []
        self._max_latency_samples = 1000
        
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to exchange"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from exchange"""
        pass
    
    @abstractmethod
    def _receive_loop(self):
        """Main receiving loop - implemented by subclasses"""
        pass
    
    @abstractmethod
    def subscribe_ticker(self, symbols: Optional[List[str]] = None) -> bool:
        """Subscribe to ticker/price updates"""
        pass
    
    @abstractmethod
    def subscribe_orderbook(self, symbols: Optional[List[str]] = None) -> bool:
        """Subscribe to order book updates"""
        pass
    
    @abstractmethod
    def subscribe_kline(self, symbols: Optional[List[str]] = None, interval: str = "1m") -> bool:
        """Subscribe to kline/candlestick updates"""
        pass
    
    def start(self):
        """Start the connector"""
        with self._lock:
            if self._running:
                logger.warning(f"{self.name}: Already running")
                return
                
            self._running = True
            self.status = FeedStatus.CONNECTING
            
            self._thread = threading.Thread(target=self._receive_loop, daemon=True)
            self._thread.start()
            
            logger.info(f"{self.name}: Started")
    
    def stop(self):
        """Stop the connector"""
        with self._lock:
            if not self._running:
                return
                
            self._running = False
            
            if self._thread:
                self._thread.join(timeout=5)
                
            self.status = FeedStatus.DISCONNECTED
            logger.info(f"{self.name}: Stopped")
    
    def on_tick(self, callback: Callable[[TickData], None]):
        """Register tick callback"""
        self._tick_callbacks.append(callback)
    
    def on_orderbook(self, callback: Callable[[OrderBookData], None]):
        """Register order book callback"""
        self._orderbook_callbacks.append(callback)
    
    def on_kline(self, callback: Callable[[KlineData], None]):
        """Register kline callback"""
        self._kline_callbacks.append(callback)
    
    def on_error(self, callback: Callable[[Exception], None]):
        """Register error callback"""
        self._error_callbacks.append(callback)
    
    def _emit_tick(self, tick: TickData):
        """Emit tick to callbacks"""
        self._tick_count += 1
        self._last_tick_time[tick.symbol] = tick.timestamp
        
        for callback in self._tick_callbacks:
            try:
                callback(tick)
            except Exception as e:
                logger.error(f"Tick callback error: {e}")
    
    def _emit_orderbook(self, orderbook: OrderBookData):
        """Emit order book to callbacks"""
        for callback in self._orderbook_callbacks:
            try:
                callback(orderbook)
            except Exception as e:
                logger.error(f"OrderBook callback error: {e}")
    
    def _emit_kline(self, kline: KlineData):
        """Emit kline to callbacks"""
        for callback in self._kline_callbacks:
            try:
                callback(kline)
            except Exception as e:
                logger.error(f"Kline callback error: {e}")
    
    def _emit_error(self, error: Exception):
        """Emit error to callbacks"""
        self._error_count += 1
        
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                logger.error(f"Error callback error: {e}")
    
    def record_latency(self, latency_ms: float):
        """Record tick latency"""
        self._tick_latencies.append(latency_ms)
        if len(self._tick_latencies) > self._max_latency_samples:
            self._tick_latencies = self._tick_latencies[-self._max_latency_samples:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connector statistics"""
        avg_latency = sum(self._tick_latencies) / len(self._tick_latencies) if self._tick_latencies else 0
        
        return {
            'name': self.name,
            'status': self.status.value,
            'running': self._running,
            'symbols': self.symbols,
            'tick_count': self._tick_count,
            'error_count': self._error_count,
            'avg_latency_ms': avg_latency,
            'last_tick_times': self._last_tick_time
        }
    
    def is_connected(self) -> bool:
        """Check if connected"""
        return self.status == FeedStatus.CONNECTED and self._running


class DummyExchangeConnector(BaseExchangeConnector):
    """Dummy connector for testing"""
    
    def connect(self) -> bool:
        self.status = FeedStatus.CONNECTED
        return True
    
    def disconnect(self) -> bool:
        self.status = FeedStatus.DISCONNECTED
        return True
    
    def _receive_loop(self):
        while self._running:
            for symbol in self.symbols:
                tick = TickData(
                    symbol=symbol,
                    price=45000.0 + (hash(symbol) % 1000),
                    volume=100.0,
                    bid=44999.0,
                    ask=45001.0,
                    timestamp=time.time(),
                    source=self.name,
                    sequence=self._tick_count
                )
                self._emit_tick(tick)
            
            time.sleep(1)
    
    def subscribe_ticker(self, symbols: Optional[List[str]] = None) -> bool:
        return True
    
    def subscribe_orderbook(self, symbols: Optional[List[str]] = None) -> bool:
        return True
    
    def subscribe_kline(self, symbols: Optional[List[str]] = None, interval: str = "1m") -> bool:
        return True
