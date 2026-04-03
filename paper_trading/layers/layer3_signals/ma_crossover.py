"""
Layer 3: Moving Average Crossover Strategy
"""

from typing import Dict, Any, List, Optional
from loguru import logger


class MACrossoverStrategy:
    """Moving Average Crossover signal generator."""
    
    def __init__(self, fast_window: int = 10, slow_window: int = 30):
        self.fast_window = fast_window
        self.slow_window = slow_window
        
        self.price_history: List[float] = []
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        """Update with new price and generate signal."""
        self.price_history.append(price)
        
        if len(self.price_history) < self.slow_window:
            return None
        
        fast_ma = sum(self.price_history[-self.fast_window:]) / self.fast_window
        slow_ma = sum(self.price_history[-self.slow_window:]) / self.slow_window
        
        signal = None
        if fast_ma > slow_ma:
            signal = 'bullish'
        elif fast_ma < slow_ma:
            signal = 'bearish'
        
        prev_fast = sum(self.price_history[-self.fast_window-1:-1]) / self.fast_window
        prev_slow = sum(self.price_history[-self.slow_window-1:-1]) / self.slow_window
        
        if prev_fast <= prev_slow and fast_ma > slow_ma:
            signal = 'buy'
        elif prev_fast >= prev_slow and fast_ma < slow_ma:
            signal = 'sell'
        
        return {
            'signal': signal,
            'fast_ma': fast_ma,
            'slow_ma': slow_ma,
            'price': price,
            'strategy': 'ma_crossover'
        }
    
    def reset(self):
        """Reset strategy state."""
        self.price_history = []


class EMACrossoverStrategy:
    """Exponential Moving Average Crossover strategy."""
    
    def __init__(self, fast_window: int = 10, slow_window: int = 30):
        self.fast_window = fast_window
        self.slow_window = slow_window
        
        self.prices: List[float] = []
        self.fast_ema = 0.0
        self.slow_ema = 0.0
        self.alpha_fast = 2 / (fast_window + 1)
        self.alpha_slow = 2 / (slow_window + 1)
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        """Update with new price and generate signal."""
        self.prices.append(price)
        
        if len(self.prices) < self.slow_window:
            return None
        
        if self.fast_ema == 0:
            self.fast_ema = sum(self.prices[-self.fast_window:]) / self.fast_window
            self.slow_ema = sum(self.prices[-self.slow_window:]) / self.slow_window
            return None
        
        prev_fast = self.fast_ema
        prev_slow = self.slow_ema
        
        self.fast_ema = self.alpha_fast * price + (1 - self.alpha_fast) * self.fast_ema
        self.slow_ema = self.alpha_slow * price + (1 - self.alpha_slow) * self.slow_ema
        
        signal = None
        
        if prev_fast <= prev_slow and self.fast_ema > self.slow_ema:
            signal = 'buy'
        elif prev_fast >= prev_slow and self.fast_ema < self.slow_ema:
            signal = 'sell'
        
        return {
            'signal': signal,
            'fast_ema': self.fast_ema,
            'slow_ema': self.slow_ema,
            'price': price,
            'strategy': 'ema_crossover'
        }
    
    def reset(self):
        """Reset strategy state."""
        self.prices = []
        self.fast_ema = 0.0
        self.slow_ema = 0.0
