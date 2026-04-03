"""
Layer 3: RSI (Relative Strength Index) Strategy
"""

from typing import Dict, Any, List, Optional
from loguru import logger


class RSIStrategy:
    """RSI-based signal generator."""
    
    def __init__(self, period: int = 14, overbought: float = 70, oversold: float = 30):
        self.period = period
        self.overbought = overbought
        self.oversold = oversold
        
        self.prices: List[float] = []
        self.rsi = 50.0
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        """Update with new price and generate signal."""
        self.prices.append(price)
        
        if len(self.prices) < self.period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(-self.period, 0):
            change = self.prices[i + 1] - self.prices[i]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            self.rsi = 100
        else:
            rs = avg_gain / avg_loss
            self.rsi = 100 - (100 / (1 + rs))
        
        prev_rsi = self._calculate_prev_rsi()
        
        signal = None
        
        if self.rsi < self.oversold:
            signal = 'buy'
        elif self.rsi > self.overbought:
            signal = 'sell'
        elif self.rsi < 45:
            signal = 'bullish'
        elif self.rsi > 55:
            signal = 'bearish'
        
        return {
            'signal': signal,
            'rsi': self.rsi,
            'price': price,
            'overbought': self.overbought,
            'oversold': self.oversold,
            'strategy': 'rsi'
        }
    
    def _calculate_prev_rsi(self) -> float:
        """Calculate previous RSI value."""
        if len(self.prices) < self.period + 2:
            return 50.0
        
        gains = []
        losses = []
        
        for i in range(-self.period - 1, -1):
            change = self.prices[i + 1] - self.prices[i]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / self.period
        avg_loss = sum(losses) / self.period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def get_current_rsi(self) -> float:
        """Get current RSI value."""
        return self.rsi
    
    def reset(self):
        """Reset strategy state."""
        self.prices = []
        self.rsi = 50.0


class RSIDivergenceStrategy:
    """RSI with divergence detection."""
    
    def __init__(self, period: int = 14):
        self.period = period
        self.rsi_strategy = RSIStrategy(period)
        
        self.price_history: List[float] = []
        self.rsi_history: List[float] = []
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        """Update with new price."""
        result = self.rsi_strategy.update(price)
        
        if result:
            self.price_history.append(price)
            self.rsi_history.append(self.rsi_strategy.rsi)
            
            result['divergence'] = self._detect_divergence()
        
        return result
    
    def _detect_divergence(self) -> Optional[str]:
        """Detect bullish or bearish divergence."""
        if len(self.price_history) < self.period * 2:
            return None
        
        recent_prices = self.price_history[-self.period:]
        recent_rsi = self.rsi_history[-self.period:]
        
        price_trend = recent_prices[-1] - recent_prices[0]
        rsi_trend = recent_rsi[-1] - recent_rsi[0]
        
        if price_trend < 0 and rsi_trend > 0:
            return 'bullish'
        elif price_trend > 0 and rsi_trend < 0:
            return 'bearish'
        
        return None
    
    def reset(self):
        """Reset strategy state."""
        self.rsi_strategy.reset()
        self.price_history = []
        self.rsi_history = []
