"""
Layer 3: Signal Aggregator
Combines multiple signals into unified trading decision.
Black Swan Resistant Execution Layer - Phase 2
"""

import time
import math
from typing import Dict, Any, List, Optional
from loguru import logger

from .ma_crossover import MACrossoverStrategy, EMACrossoverStrategy
from .rsi import RSIStrategy
from .bollinger_bands import BollingerBandsStrategy, MACDStrategy, VWAPStrategy, SupertrendStrategy


class SignalAggregator:
    """Aggregates signals from multiple strategies."""
    
    def __init__(self):
        self.strategies = {
            'ma_crossover': MACrossoverStrategy(fast_window=10, slow_window=30),
            'ema_crossover': EMACrossoverStrategy(fast_window=10, slow_window=30),
            'rsi': RSIStrategy(period=14),
            'bollinger_bands': BollingerBandsStrategy(window=20, num_std=2.0),
            'macd': MACDStrategy(fast=12, slow=26, signal=9),
            'vwap': VWAPStrategy(window=20),
            'supertrend': SupertrendStrategy(period=10, multiplier=3.0),
        }
        
        self.weights = {
            'ma_crossover': 0.25,
            'ema_crossover': 0.20,
            'rsi': 0.25,
            'bollinger_bands': 0.15,
            'macd': 0.10,
            'vwap': 0.03,
            'supertrend': 0.02,
        }
        
        self.enabled_strategies = ['ma_crossover', 'rsi', 'bollinger_bands', 'macd']
        
        self.last_signal_time: float = 0
        self.last_signal: Optional[Dict[str, Any]] = None
        
        self.edge_decay_lambda = 0.1
        self.edge_threshold = 0.01
    
    def generate(self, market_data: Dict[str, Any], 
                 strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate aggregated signal from market data."""
        price = market_data.get('close', market_data.get('price', 0))
        volume = market_data.get('volume', 1.0)
        high = market_data.get('high', price * 1.001)
        low = market_data.get('low', price * 0.999)
        
        if price == 0:
            return {'action': None, 'reason': 'No price data'}
        
        signals = {}
        
        for name in self.enabled_strategies:
            if name not in self.strategies:
                continue
            
            strategy = self.strategies[name]
            try:
                if name == 'supertrend':
                    result = strategy.update(high, low, price)
                elif name == 'vwap':
                    result = strategy.update(price, volume)
                else:
                    result = strategy.update(price)
                
                if result:
                    signals[name] = result
            except Exception as e:
                logger.warning(f"Strategy {name} error: {e}")
        
        if not signals:
            return {'action': None, 'reason': 'No signals generated'}
        
        return self._combine_signals(signals)
    
    def _combine_signals(self, signals: Dict[str, Any]) -> Dict[str, Any]:
        """Combine individual signals into final decision."""
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        
        for name, signal_data in signals.items():
            weight = self.weights.get(name, 0.0)
            signal = signal_data.get('signal')
            
            if signal == 'buy':
                buy_score += weight
                total_weight += weight
            elif signal == 'sell':
                sell_score += weight
                total_weight += weight
            elif signal == 'bullish':
                buy_score += weight * 0.6
                total_weight += weight
            elif signal == 'bearish':
                sell_score += weight * 0.6
                total_weight += weight
        
        if total_weight == 0:
            return {'action': None, 'reason': 'No consensus', 'signals': signals}
        
        buy_ratio = buy_score / total_weight if total_weight > 0 else 0
        sell_ratio = sell_score / total_weight if total_weight > 0 else 0
        
        threshold = 0.65  # Raised to reduce overtrading - require stronger consensus
        min_confidence = 0.60  # Minimum confidence required to act
        
        if buy_ratio >= threshold and buy_ratio >= min_confidence:
            return {
                'action': 'buy',
                'confidence': buy_ratio,
                'signals': signals,
                'reason': f'Buy consensus: {buy_ratio:.1%}'
            }
        elif sell_ratio >= threshold and sell_ratio >= min_confidence:
            return {
                'action': 'sell',
                'confidence': sell_ratio,
                'signals': signals,
                'reason': f'Sell consensus: {sell_ratio:.1%}'
            }
        
        return {
            'action': None,
            'confidence': max(buy_ratio, sell_ratio),
            'signals': signals,
            'reason': 'No consensus or low confidence'
        }
    
    def enable_strategy(self, name: str):
        """Enable a strategy."""
        if name in self.strategies and name not in self.enabled_strategies:
            self.enabled_strategies.append(name)
    
    def disable_strategy(self, name: str):
        """Disable a strategy."""
        if name in self.enabled_strategies:
            self.enabled_strategies.remove(name)
    
    def set_weight(self, name: str, weight: float):
        """Set weight for a strategy."""
        if name in self.weights:
            self.weights[name] = weight
    
    def reset_all(self):
        """Reset all strategies."""
        for strategy in self.strategies.values():
            strategy.reset()
    
    def get_signal_status(self) -> Dict[str, Any]:
        """Get status of all strategies."""
        status = {
            'enabled': self.enabled_strategies.copy(),
            'weights': self.weights.copy()
        }
        
        for name, strategy in self.strategies.items():
            if hasattr(strategy, 'rsi'):
                status[name] = {'rsi': strategy.get_current_rsi()}
            elif hasattr(strategy, 'fast_ma'):
                status[name] = {
                    'fast_ma': strategy.fast_ma,
                    'slow_ma': strategy.slow_ma
                }
        
        return status
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 2 (Feature 3: Edge Decay)
    # =========================================================================
    
    def apply_edge_decay(self, signal: Dict[str, Any], signal_time: float) -> Dict[str, Any]:
        """
        Feature 3: Edge Decay Function
        E_time_adjusted = E_adjusted × exp(-λ × time_since_signal)
        Reject if signal too old and edge decays below threshold.
        """
        if not signal or signal.get('action') is None:
            return signal
        
        current_time = time.time()
        time_since_signal = current_time - signal_time
        
        original_confidence = signal.get('confidence', 0)
        
        decay_factor = math.exp(-self.edge_decay_lambda * time_since_signal)
        decayed_confidence = original_confidence * decay_factor
        
        signal['original_confidence'] = original_confidence
        signal['decay_factor'] = decay_factor
        signal['time_since_signal'] = time_since_signal
        signal['confidence'] = decayed_confidence
        
        if decayed_confidence < self.edge_threshold:
            logger.warning(
                f"Signal rejected: Edge decayed {decayed_confidence:.3f} < threshold {self.edge_threshold} "
                f"(age: {time_since_signal:.1f}s)"
            )
            return {
                'action': None,
                'reason': f'Signal too old: edge {decayed_confidence:.3f} < {self.edge_threshold}',
                'original_signal': signal
            }
        
        return signal
    
    def check_signal_staleness(self, signal: Dict[str, Any], 
                                max_age_seconds: float = 60.0) -> Dict[str, Any]:
        """Check if signal is too stale for execution."""
        if not signal or signal.get('action') is None:
            return {'allowed': True, 'reason': 'No signal'}
        
        age = signal.get('time_since_signal', 0)
        
        if age > max_age_seconds:
            return {
                'allowed': False,
                'reason': f'Signal stale: {age:.1f}s > {max_age_seconds}s',
                'action': 'reject'
            }
        
        return {'allowed': True, 'reason': 'Signal fresh', 'action': 'proceed'}


aggregator = SignalAggregator()


def generate_signal(market_data: Dict[str, Any], 
                    strategy_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to generate signal."""
    return aggregator.generate(market_data, strategy_config or {})
