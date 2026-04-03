#!/usr/bin/env python3
"""
Order Book Manager
Manages order book depth, maintains local state, and validates freshness
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

from data_lab.exchange_connectors import OrderBookData, TickData

logger = logging.getLogger('OrderBookManager')


@dataclass
class OrderBookSnapshot:
    """Full order book snapshot"""
    symbol: str
    bids: List[List[float]]
    asks: List[List[float]]
    mid_price: float
    spread: float
    spread_percent: float
    bid_depth: float
    ask_depth: float
    depth_imbalance: float
    timestamp: float
    update_id: int


class OrderBookManager:
    """
    Manages order book state and depth calculations.
    Validates refresh rates and maintains book depth.
    """
    
    def __init__(
        self,
        max_depth: int = 20,
        stale_threshold_ms: int = 1000
    ):
        self.max_depth = max_depth
        self.stale_threshold_ms = stale_threshold_ms
        
        self._books: Dict[str, OrderBookSnapshot] = {}
        self._last_update: Dict[str, float] = {}
        self._update_history: Dict[str, deque] = {}
        
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        self._refresh_count = 0
        self._stale_count = 0
        
    def update_orderbook(self, data: OrderBookData) -> Optional[OrderBookSnapshot]:
        """Update order book with new data"""
        with self._lock:
            symbol = data.symbol
            
            if data.last_update_id <= self._books.get(symbol, OrderBookSnapshot(
                symbol='', bids=[], asks=[], mid_price=0, spread=0,
                spread_percent=0, bid_depth=0, ask_depth=0,
                depth_imbalance=0, timestamp=0, update_id=0
            )).update_id:
                return None
            
            bids = data.bids[:self.max_depth]
            asks = data.asks[:self.max_depth]
            
            if not bids or not asks:
                return None
                
            best_bid = bids[0][0]
            best_ask = asks[0][0]
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            spread_percent = (spread / mid_price) * 100 if mid_price > 0 else 0
            
            bid_depth = sum(b[1] for b in bids)
            ask_depth = sum(a[1] for a in asks)
            depth_imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth) if (bid_depth + ask_depth) > 0 else 0
            
            snapshot = OrderBookSnapshot(
                symbol=symbol,
                bids=bids,
                asks=asks,
                mid_price=mid_price,
                spread=spread,
                spread_percent=spread_percent,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
                depth_imbalance=depth_imbalance,
                timestamp=data.timestamp,
                update_id=data.last_update_id
            )
            
            self._books[symbol] = snapshot
            self._last_update[symbol] = time.time()
            self._refresh_count += 1
            
            self._record_update(symbol, snapshot)
            
            for callback in self._callbacks:
                try:
                    callback(snapshot)
                except Exception as e:
                    logger.error(f"OrderBook callback error: {e}")
                    
            return snapshot
    
    def _record_update(self, symbol: str, snapshot: OrderBookSnapshot):
        """Record update for history"""
        if symbol not in self._update_history:
            self._update_history[symbol] = deque(maxlen=100)
            
        self._update_history[symbol].append({
            'timestamp': snapshot.timestamp,
            'update_id': snapshot.update_id,
            'spread': snapshot.spread
        })
    
    def get_snapshot(self, symbol: str) -> Optional[OrderBookSnapshot]:
        """Get current order book snapshot"""
        with self._lock:
            return self._books.get(symbol)
    
    def get_best_prices(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get best bid and ask"""
        snapshot = self.get_snapshot(symbol)
        if not snapshot:
            return None
            
        return {
            'bid': snapshot.bids[0][0] if snapshot.bids else 0,
            'ask': snapshot.asks[0][0] if snapshot.asks else 0,
            'mid': snapshot.mid_price,
            'spread': snapshot.spread
        }
    
    def is_fresh(self, symbol: str) -> bool:
        """Check if order book is fresh (within threshold)"""
        last_update = self._last_update.get(symbol)
        if not last_update:
            return False
            
        age_ms = (time.time() - last_update) * 1000
        is_fresh = age_ms < self.stale_threshold_ms
        
        if not is_fresh:
            self._stale_count += 1
            
        return is_fresh
    
    def get_freshness(self, symbol: str) -> float:
        """Get order book freshness as percentage"""
        last_update = self._last_update.get(symbol)
        if not last_update:
            return 0.0
            
        age_ms = (time.time() - last_update) * 1000
        freshness = max(0, 100 - (age_ms / self.stale_threshold_ms * 100))
        return freshness
    
    def get_spread(self, symbol: str) -> Optional[float]:
        """Get current spread"""
        snapshot = self.get_snapshot(symbol)
        return snapshot.spread if snapshot else None
    
    def get_depth_imbalance(self, symbol: str) -> Optional[float]:
        """Get depth imbalance (-1 to 1)"""
        snapshot = self.get_snapshot(symbol)
        return snapshot.depth_imbalance if snapshot else None
    
    def on_update(self, callback: Callable[[OrderBookSnapshot], None]):
        """Register update callback"""
        self._callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get manager statistics"""
        with self._lock:
            return {
                'tracked_symbols': len(self._books),
                'refresh_count': self._refresh_count,
                'stale_count': self._stale_count,
                'stale_percent': (self._stale_count / self._refresh_count * 100) if self._refresh_count > 0 else 0,
                'symbols': {
                    symbol: {
                        'last_update': self._last_update.get(symbol),
                        'freshness': self.get_freshness(symbol)
                    }
                    for symbol in self._books.keys()
                }
            }
    
    def get_all_snapshots(self) -> Dict[str, OrderBookSnapshot]:
        """Get all order book snapshots"""
        with self._lock:
            return self._books.copy()


class OrderBookAggregator:
    """
    Aggregates order books from multiple sources/exchanges.
    Maintains best prices across all sources.
    """
    
    def __init__(self):
        self._sources: Dict[str, OrderBookManager] = {}
        self._lock = threading.Lock()
    
    def register_source(self, source_name: str, manager: OrderBookManager):
        """Register an order book source"""
        with self._lock:
            self._sources[source_name] = manager
            logger.info(f"Registered order book source: {source_name}")
    
    def get_best_bid_ask(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get best bid/ask across all sources"""
        with self._lock:
            best_bid = 0
            best_ask = float('inf')
            source_bid = None
            source_ask = None
            
            for source, manager in self._sources.items():
                snapshot = manager.get_snapshot(symbol)
                if not snapshot:
                    continue
                    
                if snapshot.bids and snapshot.bids[0][0] > best_bid:
                    best_bid = snapshot.bids[0][0]
                    source_bid = source
                    
                if snapshot.asks and snapshot.asks[0][0] < best_ask:
                    best_ask = snapshot.asks[0][0]
                    source_ask = source
            
            if best_bid == 0 or best_ask == float('inf'):
                return None
                
            return {
                'symbol': symbol,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'mid': (best_bid + best_ask) / 2,
                'spread': best_ask - best_bid,
                'source_bid': source_bid,
                'source_ask': source_ask
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get aggregated stats"""
        with self._lock:
            return {
                'sources': list(self._sources.keys()),
                'source_stats': {
                    source: manager.get_stats()
                    for source, manager in self._sources.items()
                }
            }
