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
        # Store strategy classes, not instances - create per-symbol instances as needed
        self.strategy_classes = {
            'ma_crossover': MACrossoverStrategy,
            'ema_crossover': EMACrossoverStrategy,
            'rsi': RSIStrategy,
            'bollinger_bands': BollingerBandsStrategy,
            'macd': MACDStrategy,
            'vwap': VWAPStrategy,
            'supertrend': SupertrendStrategy,
        }
        
        # Per-symbol strategy instances
        self.strategies: Dict[str, Dict[str, Any]] = {}
        
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
    
    def _prime_strategies_with_history(self, symbol: str):
        """Prime strategies with available historical data."""
        try:
            # Try to get historical data from data bridge
            from ..layer1_data.vnpy_bridge import get_data_bridge
            data_bridge = get_data_bridge()
            if data_bridge and hasattr(data_bridge, 'get_buffer'):
                buffer_data = data_bridge.get_buffer(symbol, 20)  # Get last 20 bars
                if buffer_data and len(buffer_data) >= 5:  # Need at least 5 data points
                    logger.debug(f"Priming {symbol} strategies with {len(buffer_data)} historical bars")
                    
                    for bar in buffer_data[-15:]:  # Use last 15 bars to avoid overloading
                        bar_price = bar.get('close', bar.get('price', 0))
                        bar_high = bar.get('high', bar_price * 1.001)
                        bar_low = bar.get('low', bar_price * 0.999)
                        bar_volume = bar.get('volume', 1.0)
                        
                        if bar_price > 0:
                            for name, strategy in self.strategies[symbol].items():
                                try:
                                    if name == 'supertrend':
                                        strategy.update(bar_high, bar_low, bar_price)
                                    elif name == 'vwap':
                                        strategy.update(bar_price, bar_volume)
                                    else:
                                        strategy.update(bar_price)
                                except Exception:
                                    pass  # Ignore priming errors
        except Exception as e:
            logger.debug(f"Could not prime strategies for {symbol}: {e}")
            # Fallback: prime with current price variations
            try:
                # Get current price and create synthetic history
                from ..layer1_data.vnpy_bridge import get_data_bridge
                data_bridge = get_data_bridge()
                current_data = data_bridge.get_latest_data(symbol) if data_bridge else {}
                base_price = current_data.get('close', current_data.get('price', 1000.0))
                
                if base_price > 0:
                    # Create 10 synthetic price points with small variations
                    import random
                    for i in range(10):
                        variation = random.uniform(-0.005, 0.005)  # ±0.5%
                        synth_price = base_price * (1 + variation)
                        synth_high = synth_price * 1.002
                        synth_low = synth_price * 0.998
                        
                        for name, strategy in self.strategies[symbol].items():
                            try:
                                if name == 'supertrend':
                                    strategy.update(synth_high, synth_low, synth_price)
                                elif name == 'vwap':
                                    strategy.update(synth_price, 100.0)
                                else:
                                    strategy.update(synth_price)
                            except Exception:
                                pass
                    logger.debug(f"Primed {symbol} strategies with synthetic historical data")
            except Exception:
                pass  # Silent failure for priming
    
    def generate(self, market_data: Dict[str, Any], 
                  strategy_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate aggregated signal from market data."""
        price = market_data.get('close', market_data.get('price', 0))
        volume = market_data.get('volume', 1.0)
        high = market_data.get('high', price * 1.001)
        low = market_data.get('low', price * 0.999)
        symbol = market_data.get('symbol', 'BTCUSDT')
        
        if price == 0:
            return {'action': None, 'reason': 'No price data'}
        
        # Initialize strategies for this symbol if not exists
        if symbol not in self.strategies:
            self.strategies[symbol] = {
                'ma_crossover': self.strategy_classes['ma_crossover'](fast_window=5, slow_window=15),  # Reduced windows
                'ema_crossover': self.strategy_classes['ema_crossover'](fast_window=5, slow_window=15),
                'rsi': self.strategy_classes['rsi'](period=5),  # Reduced from 14 to 5
                'bollinger_bands': self.strategy_classes['bollinger_bands'](window=10, num_std=2.0),  # Reduced window
                'macd': self.strategy_classes['macd'](fast=6, slow=13, signal=4),  # Reduced periods
                'vwap': self.strategy_classes['vwap'](window=10),
                'supertrend': self.strategy_classes['supertrend'](period=5, multiplier=3.0),  # Reduced period
            }
            logger.debug(f"Initialized strategies for symbol: {symbol}")
            
            # Prime strategies with historical data if available
            self._prime_strategies_with_history(symbol)
        
        signals = {}
        
        for name in self.enabled_strategies:
            if name not in self.strategies[symbol]:
                continue
            
            strategy = self.strategies[symbol][name]
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
                logger.warning(f"Strategy {name} error for {symbol}: {e}")
        
        if not signals:
            return {'action': None, 'reason': 'No signals generated'}
        
        return self._combine_signals(signals)
    
    def _prime_strategies_with_history(self, symbol: str):
        """Prime strategies with available historical data."""
        try:
            # Try to get historical data from data bridge
            from ..layer1_data.vnpy_bridge import get_data_bridge
            data_bridge = get_data_bridge()
            if data_bridge and hasattr(data_bridge, 'get_buffer'):
                buffer_data = data_bridge.get_buffer(symbol, 20)  # Get last 20 bars
                if buffer_data and len(buffer_data) >= 5:  # Need at least 5 data points
                    logger.debug(f"Priming {symbol} strategies with {len(buffer_data)} historical bars")
                    
                    for bar in buffer_data[-15:]:  # Use last 15 bars to avoid overloading
                        bar_price = bar.get('close', bar.get('price', 0))
                        bar_high = bar.get('high', bar_price * 1.001)
                        bar_low = bar.get('low', bar_price * 0.999)
                        bar_volume = bar.get('volume', 1.0)
                        
                        if bar_price > 0:
                            for name, strategy in self.strategies[symbol].items():
                                try:
                                    if name == 'supertrend':
                                        strategy.update(bar_high, bar_low, bar_price)
                                    elif name == 'vwap':
                                        strategy.update(bar_price, bar_volume)
                                    else:
                                        strategy.update(bar_price)
                                except Exception:
                                    pass  # Ignore priming errors
        except Exception as e:
            logger.debug(f"Could not prime strategies for {symbol}: {e}")
            # Fallback: prime with current price variations
            try:
                # Get current price and create synthetic history
                from ..layer1_data.vnpy_bridge import get_data_bridge
                data_bridge = get_data_bridge()
                current_data = data_bridge.get_latest_data(symbol) if data_bridge else {}
                base_price = current_data.get('close', current_data.get('price', 1000.0))
                
                if base_price > 0:
                    # Create 10 synthetic price points with small variations
                    import random
                    for i in range(10):
                        variation = random.uniform(-0.005, 0.005)  # ±0.5%
                        synth_price = base_price * (1 + variation)
                        synth_high = synth_price * 1.002
                        synth_low = synth_price * 0.998
                        
                        for name, strategy in self.strategies[symbol].items():
                            try:
                                if name == 'supertrend':
                                    strategy.update(synth_high, synth_low, synth_price)
                                elif name == 'vwap':
                                    strategy.update(synth_price, 100.0)
                                else:
                                    strategy.update(synth_price)
                            except Exception:
                                pass
                    logger.debug(f"Primed {symbol} strategies with synthetic historical data")
            except Exception:
                pass  # Silent failure for priming

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
        
        threshold = 0.45  # Lowered for faster signal generation
        min_confidence = 0.40  # Lowered for faster signal generation
        
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
        """Reset all strategies for all symbols."""
        for symbol_strategies in self.strategies.values():
            for strategy in symbol_strategies.values():
                strategy.reset()
    
    def get_signal_status(self) -> Dict[str, Any]:
        """Get status of all strategies for all symbols."""
        status = {
            'enabled': self.enabled_strategies.copy(),
            'weights': self.weights.copy(),
            'symbols': list(self.strategies.keys()),
        }
        
        # Add status for each symbol
        for symbol, symbol_strategies in self.strategies.items():
            status[symbol] = {}
            for name, strategy in symbol_strategies.items():
                if hasattr(strategy, 'rsi'):
                    status[symbol][name] = {'rsi': strategy.get_current_rsi()}
                elif hasattr(strategy, 'fast_ma'):
                    status[symbol][name] = {
                        'fast_ma': strategy.fast_ma,
                        'slow_ma': strategy.slow_ma
                    }
                else:
                    status[symbol][name] = {'status': 'active'}
        
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
