#!/usr/bin/env python3
"""
Tick Validator
Validates tick data for quality, duplicates, and timestamps
"""

import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import deque
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('TickValidator')


class ValidationStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    DUPLICATE = "duplicate"
    STALE = "stale"
    MISSING_FIELDS = "missing_fields"


@dataclass
class ValidationResult:
    status: ValidationStatus
    message: str
    details: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class TickValidator:
    """
    Validates tick data for quality assurance.
    - Duplicate rejection via hash
    - Timestamp validation
    - Latency checking
    - Missing field detection
    """
    
    def __init__(
        self,
        max_latency_ms: float = 500,
        max_price_deviation_percent: float = 10.0,
        duplicate_window_seconds: float = 60.0
    ):
        self.max_latency_ms = max_latency_ms
        self.max_price_deviation_percent = max_price_deviation_percent
        self.duplicate_window_seconds = duplicate_window_seconds
        
        self._tick_hashes: deque = deque(maxlen=10000)
        self._last_prices: Dict[str, float] = {}
        
        self._validation_stats = {
            'total_validated': 0,
            'valid': 0,
            'duplicates': 0,
            'stale': 0,
            'invalid': 0,
            'missing_fields': 0,
            'latency_violations': 0
        }
    
    def _generate_hash(self, tick_data: Dict) -> str:
        """Generate unique hash for tick"""
        key = f"{tick_data.get('symbol')}:{tick_data.get('timestamp')}:{tick_data.get('price')}"
        return hashlib.md5(key.encode()).hexdigest()
    
    def _is_duplicate(self, tick_hash: str) -> bool:
        """Check if tick hash is duplicate"""
        return tick_hash in self._tick_hashes
    
    def _add_hash(self, tick_hash: str):
        """Add tick hash to recent history"""
        self._tick_hashes.append(tick_hash)
    
    def validate_tick(
        self,
        symbol: str,
        price: float,
        volume: float,
        timestamp: float,
        source: str,
        bid: Optional[float] = None,
        ask: Optional[float] = None
    ) -> ValidationResult:
        """Validate a single tick"""
        
        self._validation_stats['total_validated'] += 1
        
        if not symbol or not price or not timestamp:
            self._validation_stats['missing_fields'] += 1
            return ValidationResult(
                ValidationStatus.MISSING_FIELDS,
                "Missing required fields: symbol, price, or timestamp"
            )
        
        if price <= 0:
            self._validation_stats['invalid'] += 1
            return ValidationResult(
                ValidationStatus.INVALID,
                f"Invalid price: {price} <= 0"
            )
        
        receive_time = time.time()
        latency_ms = (receive_time - timestamp) * 1000
        
        if latency_ms > self.max_latency_ms:
            self._validation_stats['latency_violations'] += 1
            logger.warning(f"Latency violation: {latency_ms:.1f}ms > {self.max_latency_ms}ms")
        
        tick_data = {
            'symbol': symbol,
            'price': price,
            'timestamp': timestamp,
            'source': source
        }
        
        tick_hash = self._generate_hash(tick_data)
        
        if self._is_duplicate(tick_hash):
            self._validation_stats['duplicates'] += 1
            return ValidationResult(
                ValidationStatus.DUPLICATE,
                f"Duplicate tick detected for {symbol}",
                {'hash': tick_hash}
            )
        
        self._add_hash(tick_hash)
        
        if symbol in self._last_prices:
            last_price = self._last_prices[symbol]
            deviation_percent = abs(price - last_price) / last_price * 100
            
            if deviation_percent > self.max_price_deviation_percent:
                self._validation_stats['invalid'] += 1
                return ValidationResult(
                    ValidationStatus.INVALID,
                    f"Price deviation {deviation_percent:.2f}% exceeds threshold",
                    {'last_price': last_price, 'current_price': price}
                )
        
        self._last_prices[symbol] = price
        
        self._validation_stats['valid'] += 1
        
        return ValidationResult(
            ValidationStatus.VALID,
            f"Tick valid for {symbol}",
            {
                'latency_ms': latency_ms,
                'hash': tick_hash
            }
        )
    
    def validate_from_object(self, tick_obj) -> ValidationResult:
        """Validate tick from TickData object"""
        return self.validate_tick(
            symbol=tick_obj.symbol,
            price=tick_obj.price,
            volume=tick_obj.volume,
            timestamp=tick_obj.timestamp,
            source=tick_obj.source,
            bid=tick_obj.bid,
            ask=tick_obj.ask
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics"""
        total = self._validation_stats['total_validated']
        
        return {
            **self._validation_stats,
            'valid_percent': (self._validation_stats['valid'] / total * 100) if total > 0 else 0,
            'duplicate_percent': (self._validation_stats['duplicates'] / total * 100) if total > 0 else 0
        }
    
    def reset_stats(self):
        """Reset validation statistics"""
        self._validation_stats = {
            'total_validated': 0,
            'valid': 0,
            'duplicates': 0,
            'stale': 0,
            'invalid': 0,
            'missing_fields': 0,
            'latency_violations': 0
        }
    
    def get_last_price(self, symbol: str) -> Optional[float]:
        """Get last known price for symbol"""
        return self._last_prices.get(symbol)


class TickInterpolator:
    """
    Interpolates missing tick data.
    Fills gaps using linear interpolation.
    """
    
    def __init__(self, max_gap_seconds: float = 60.0):
        self.max_gap_seconds = max_gap_seconds
        
        self._price_history: Dict[str, deque] = {}
        self._gap_count = 0
    
    def add_tick(self, symbol: str, price: float, timestamp: float) -> Optional[Dict]:
        """Add tick and check for gaps"""
        if symbol not in self._price_history:
            self._price_history[symbol] = deque(maxlen=100)
        
        history = self._price_history[symbol]
        
        if len(history) > 0:
            last_price, last_time = history[-1]
            gap_seconds = timestamp - last_time
            
            if gap_seconds > self.max_gap_seconds:
                self._gap_count += 1
                
                interpolated_price = (last_price + price) / 2
                
                gap_data = {
                    'symbol': symbol,
                    'start_price': last_price,
                    'end_price': price,
                    'start_time': last_time,
                    'end_time': timestamp,
                    'interpolated_price': interpolated_price,
                    'gap_seconds': gap_seconds,
                    'filled': True
                }
                
                logger.info(f"Interpolated gap for {symbol}: {gap_seconds:.1f}s")
                return gap_data
        
        history.append((price, timestamp))
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get interpolator stats"""
        return {
            'gap_count': self._gap_count,
            'tracked_symbols': len(self._price_history)
        }
