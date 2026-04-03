#!/usr/bin/env python3
"""
Feature Engine
Generates feature vectors for strategy engines
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
import math

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('FeatureEngine')


@dataclass
class FeatureVector:
    """Generated feature vector"""
    symbol: str
    timestamp: float
    price_features: Dict[str, float] = field(default_factory=dict)
    volume_features: Dict[str, float] = field(default_factory=dict)
    technical_indicators: Dict[str, float] = field(default_factory=dict)
    microstructure_features: Dict[str, float] = field(default_factory=dict)


class TechnicalIndicators:
    """Technical indicator calculations"""
    
    @staticmethod
    def sma(values: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        if len(values) < period:
            return None
        return sum(values[-period:]) / period
    
    @staticmethod
    def ema(values: List[float], period: int) -> Optional[float]:
        """Exponential Moving Average"""
        if len(values) < period:
            return None
            
        multiplier = 2 / (period + 1)
        ema = values[0]
        
        for value in values[1:]:
            ema = (value - ema) * multiplier + ema
            
        return ema
    
    @staticmethod
    def rsi(values: List[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index"""
        if len(values) < period + 1:
            return None
            
        gains = []
        losses = []
        
        for i in range(1, len(values)):
            change = values[i] - values[i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        if len(gains) < period:
            return None
            
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
            
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(
        values: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9
    ) -> Optional[Dict[str, float]]:
        """MACD (Moving Average Convergence Divergence)"""
        if len(values) < slow_period + signal_period:
            return None
            
        fast_ema = TechnicalIndicators.ema(values, fast_period)
        slow_ema = TechnicalIndicators.ema(values, slow_period)
        
        if fast_ema is None or slow_ema is None:
            return None
            
        macd_line = fast_ema - slow_ema
        
        macd_values = []
        for i in range(slow_period, len(values)):
            fast = TechnicalIndicators.ema(values[:i+1], fast_period)
            slow = TechnicalIndicators.ema(values[:i+1], slow_period)
            if fast and slow:
                macd_values.append(fast - slow)
        
        if len(macd_values) < signal_period:
            return {'macd': macd_line, 'signal': None, 'histogram': None}
            
        signal = TechnicalIndicators.ema(macd_values, signal_period)
        histogram = macd_line - signal if signal else None
        
        return {
            'macd': macd_line,
            'signal': signal,
            'histogram': histogram
        }
    
    @staticmethod
    def bollinger_bands(
        values: List[float],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Optional[Dict[str, float]]:
        """Bollinger Bands"""
        if len(values) < period:
            return None
            
        sma = TechnicalIndicators.sma(values, period)
        if sma is None:
            return None
            
        variance = sum((x - sma) ** 2 for x in values[-period:]) / period
        std = math.sqrt(variance)
        
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        return {
            'upper': upper,
            'middle': sma,
            'lower': lower,
            'width': upper - lower
        }


class MicrostructureFeatures:
    """Market microstructure feature calculations"""
    
    @staticmethod
    def calculate_spread(bid: float, ask: float) -> Optional[float]:
        """Calculate bid-ask spread"""
        if bid <= 0 or ask <= 0:
            return None
        return (ask - bid) / ((ask + bid) / 2) * 10000
    
    @staticmethod
    def calculate_depth_imbalance(bids: List, asks: List) -> float:
        """Calculate order book depth imbalance"""
        bid_volume = sum(b[1] for b in bids) if bids else 0
        ask_volume = sum(a[1] for a in asks) if asks else 0
        
        total = bid_volume + ask_volume
        if total == 0:
            return 0
            
        return (bid_volume - ask_volume) / total
    
    @staticmethod
    def calculate_vwap(prices: List, volumes: List) -> Optional[float]:
        """Volume Weighted Average Price"""
        if not prices or not volumes or len(prices) != len(volumes):
            return None
            
        total_pv = sum(p * v for p, v in zip(prices, volumes))
        total_v = sum(volumes)
        
        return total_pv / total_v if total_v > 0 else None
    
    @staticmethod
    def calculate_trade_intensity(trades: List, window_seconds: int = 60) -> float:
        """Calculate trade intensity"""
        if not trades:
            return 0
        return len(trades) / window_seconds


class FeatureEngine:
    """
    Generates feature vectors from market data.
    Memory-efficient with configurable window sizes.
    """
    
    def __init__(
        self,
        max_price_history: int = 500,
        max_volume_history: int = 500,
        memory_limit_mb: int = 1024
    ):
        self.max_price_history = max_price_history
        self.max_volume_history = max_volume_history
        self.memory_limit_mb = memory_limit_mb
        
        self._price_history: Dict[str, deque] = {}
        self._volume_history: Dict[str, deque] = {}
        self._tick_history: Dict[str, deque] = {}
        
        self._indicators = TechnicalIndicators()
        self._microstructure = MicrostructureFeatures()
        
        self._feature_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        self._feature_count = 0
    
    def add_tick(
        self,
        symbol: str,
        price: float,
        volume: float,
        bid: float = 0,
        ask: float = 0,
        timestamp: Optional[float] = None
    ):
        """Add tick and generate features"""
        timestamp = timestamp or time.time()
        
        with self._lock:
            if symbol not in self._price_history:
                self._price_history[symbol] = deque(maxlen=self.max_price_history)
                self._volume_history[symbol] = deque(maxlen=self.max_volume_history)
                self._tick_history[symbol] = deque(maxlen=100)
            
            self._price_history[symbol].append(price)
            self._volume_history[symbol].append(volume)
            self._tick_history[symbol].append({
                'price': price,
                'volume': volume,
                'bid': bid,
                'ask': ask,
                'timestamp': timestamp
            })
            
            vector = self.generate_features(symbol)
            
            if vector:
                self._feature_count += 1
                
                for callback in self._feature_callbacks:
                    try:
                        callback(vector)
                    except Exception as e:
                        logger.error(f"Feature callback error: {e}")
    
    def generate_features(self, symbol: str) -> Optional[FeatureVector]:
        """Generate feature vector for symbol"""
        with self._lock:
            prices = list(self._price_history.get(symbol, []))
            volumes = list(self._volume_history.get(symbol, []))
            ticks = list(self._tick_history.get(symbol, []))
            
            if len(prices) < 2:
                return None
            
            latest_tick = ticks[-1] if ticks else {}
            
            price_features = self._calculate_price_features(prices)
            volume_features = self._calculate_volume_features(volumes)
            technical = self._calculate_technical_indicators(prices)
            microstructure = self._calculate_microstructure(ticks)
            
            return FeatureVector(
                symbol=symbol,
                timestamp=latest_tick.get('timestamp', time.time()),
                price_features=price_features,
                volume_features=volume_features,
                technical_indicators=technical,
                microstructure_features=microstructure
            )
    
    def _calculate_price_features(self, prices: List[float]) -> Dict[str, float]:
        """Calculate price-based features"""
        if not prices:
            return {}
            
        current = prices[-1]
        features = {
            'price': current,
            'returns_1': (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
        }
        
        if len(prices) >= 5:
            features['returns_5'] = (prices[-1] - prices[-5]) / prices[-5]
            
        if len(prices) >= 10:
            features['returns_10'] = (prices[-1] - prices[-10]) / prices[-10]
            
        if len(prices) >= 20:
            features['volatility_20'] = self._calculate_volatility(prices[-20:])
            features['high_20'] = max(prices[-20:])
            features['low_20'] = min(prices[-20:])
            
        return features
    
    def _calculate_volume_features(self, volumes: List[float]) -> Dict[str, float]:
        """Calculate volume-based features"""
        if not volumes:
            return {}
            
        features = {
            'volume': volumes[-1],
            'volume_ma_5': sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1],
            'volume_ratio': volumes[-1] / (sum(volumes[-5:]) / 5) if len(volumes) >= 5 else 1.0
        }
        
        return features
    
    def _calculate_technical_indicators(self, prices: List[float]) -> Dict[str, float]:
        """Calculate technical indicators"""
        indicators = {}
        
        sma_5 = self._indicators.sma(prices, 5)
        if sma_5:
            indicators['sma_5'] = sma_5
            
        sma_20 = self._indicators.sma(prices, 20)
        if sma_20:
            indicators['sma_20'] = sma_20
            
        ema_12 = self._indicators.ema(prices, 12)
        if ema_12:
            indicators['ema_12'] = ema_12
            
        rsi = self._indicators.rsi(prices)
        if rsi:
            indicators['rsi'] = rsi
            
        macd = self._indicators.macd(prices)
        if macd:
            indicators['macd'] = macd.get('macd', 0)
            indicators['macd_signal'] = macd.get('signal', 0)
            indicators['macd_histogram'] = macd.get('histogram', 0)
            
        bb = self._indicators.bollinger_bands(prices)
        if bb:
            indicators['bb_upper'] = bb.get('upper', 0)
            indicators['bb_middle'] = bb.get('middle', 0)
            indicators['bb_lower'] = bb.get('lower', 0)
            indicators['bb_width'] = bb.get('width', 0)
            
        return indicators
    
    def _calculate_microstructure(self, ticks: List[Dict]) -> Dict[str, float]:
        """Calculate microstructure features"""
        if not ticks:
            return {}
            
        latest = ticks[-1]
        
        spread = self._microstructure.calculate_spread(
            latest.get('bid', 0),
            latest.get('ask', 0)
        )
        
        bids = [(t.get('price'), t.get('volume')) for t in ticks if t.get('bid', 0) > 0]
        asks = [(t.get('price'), t.get('volume')) for t in ticks if t.get('ask', 0) > 0]
        
        depth = self._microstructure.calculate_depth_imbalance(bids, asks)
        
        features = {}
        
        if spread:
            features['spread_bps'] = spread
            
        features['depth_imbalance'] = depth
        
        prices = [t['price'] for t in ticks]
        volumes = [t['volume'] for t in ticks]
        
        vwap = self._microstructure.calculate_vwap(prices, volumes)
        if vwap:
            features['vwap'] = vwap
            
        return features
    
    def _calculate_volatility(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
            
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def on_features(self, callback: Callable[[FeatureVector], None]):
        """Register feature callback"""
        self._feature_callbacks.append(callback)
    
    def get_features(self, symbol: str) -> Optional[FeatureVector]:
        """Get current features for symbol"""
        return self.generate_features(symbol)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get engine statistics"""
        with self._lock:
            return {
                'tracked_symbols': len(self._price_history),
                'total_features_generated': self._feature_count,
                'symbols': {
                    symbol: {
                        'price_history': len(self._price_history[symbol]),
                        'volume_history': len(self._volume_history[symbol])
                    }
                    for symbol in self._price_history.keys()
                }
            }
    
    def clear_history(self, symbol: Optional[str] = None):
        """Clear history for symbol or all"""
        with self._lock:
            if symbol:
                if symbol in self._price_history:
                    self._price_history[symbol].clear()
                    self._volume_history[symbol].clear()
                    self._tick_history[symbol].clear()
            else:
                for hist in self._price_history.values():
                    hist.clear()
                for hist in self._volume_history.values():
                    hist.clear()
                for hist in self._tick_history.values():
                    hist.clear()


def get_feature_engine(config: Dict = None) -> FeatureEngine:
    """Create feature engine instance"""
    return FeatureEngine(
        max_price_history=config.get('max_price_history', 500) if config else 500,
        max_volume_history=config.get('max_volume_history', 500) if config else 500,
        memory_limit_mb=config.get('memory_limit_mb', 1024) if config else 1024
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    engine = FeatureEngine()
    
    for i in range(30):
        engine.add_tick(
            symbol="BTCUSDT",
            price=45000 + i * 10 + (i % 3) * 5,
            volume=100 + i * 5,
            bid=44990 + i * 10,
            ask=45010 + i * 10
        )
    
    features = engine.get_features("BTCUSDT")
    
    if features:
        print(f"Features for {features.symbol}:")
        print(f"  Price: {features.price_features}")
        print(f"  Technical: {features.technical_indicators}")
        print(f"  Microstructure: {features.microstructure_features}")
    
    print(f"\nStats: {engine.get_stats()}")
