"""
Layer 3: Bollinger Bands Strategy
"""

from typing import Dict, Any, List, Optional
from loguru import logger
import math


class BollingerBandsStrategy:
    """Bollinger Bands mean reversion strategy."""
    
    def __init__(self, window: int = 20, num_std: float = 2.0):
        self.window = window
        self.num_std = num_std
        
        self.prices: List[float] = []
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        """Generate signal based on Bollinger Bands."""
        self.prices.append(price)
        
        if len(self.prices) < self.window:
            return None
        
        recent = self.prices[-self.window:]
        mean = sum(recent) / len(recent)
        
        variance = sum((p - mean) ** 2 for p in recent) / len(recent)
        std = math.sqrt(variance)
        
        upper_band = mean + (self.num_std * std)
        lower_band = mean - (self.num_std * std)
        
        position = (price - lower_band) / (upper_band - lower_band) if upper_band != lower_band else 0.5
        
        signal = None
        if price <= lower_band:
            signal = 'buy'
        elif price >= upper_band:
            signal = 'sell'
        elif position < 0.3:
            signal = 'bullish'
        elif position > 0.7:
            signal = 'bearish'
        else:
            signal = 'hold'
        
        return {
            'signal': signal,
            'middle_band': mean,
            'upper_band': upper_band,
            'lower_band': lower_band,
            'price': price,
            'position': (price - lower_band) / (upper_band - lower_band) if upper_band != lower_band else 0.5,
            'strategy': 'bollinger_bands'
        }
    
    def reset(self):
        self.prices = []


class MACDStrategy:
    """MACD (Moving Average Convergence Divergence) strategy."""
    
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        
        self.prices: List[float] = []
        self.fast_ema = 0.0
        self.slow_ema = 0.0
        self.macd_line = 0.0
        self.signal_line = 0.0
        self.prev_macd = 0.0
        self.prev_signal = 0.0
        
        self.alpha_fast = 2 / (fast + 1)
        self.alpha_slow = 2 / (slow + 1)
        self.alpha_signal = 2 / (signal + 1)
    
    def update(self, price: float) -> Optional[Dict[str, Any]]:
        self.prices.append(price)
        
        if len(self.prices) < self.slow:
            return None
        
        if self.fast_ema == 0:
            self.fast_ema = sum(self.prices[-self.fast:]) / self.fast
            self.slow_ema = sum(self.prices[-self.slow:]) / self.slow
            return None
        
        prev_fast = self.fast_ema
        prev_slow = self.slow_ema
        
        self.fast_ema = self.alpha_fast * price + (1 - self.alpha_fast) * self.fast_ema
        self.slow_ema = self.alpha_slow * price + (1 - self.alpha_slow) * self.slow_ema
        
        self.prev_macd = self.macd_line
        self.prev_signal = self.signal_line
        
        self.macd_line = self.fast_ema - self.slow_ema
        
        if self.signal_line == 0:
            self.signal_line = self.macd_line
        else:
            self.signal_line = self.alpha_signal * self.macd_line + (1 - self.alpha_signal) * self.signal_line
        
        signal = 'hold'
        if self.macd_line > self.signal_line:
            signal = 'bullish'
        elif self.macd_line < self.signal_line:
            signal = 'bearish'
        
        if self.prev_macd <= self.prev_signal and self.macd_line > self.signal_line:
            signal = 'buy'
        elif self.prev_macd >= self.prev_signal and self.macd_line < self.signal_line:
            signal = 'sell'
        
        return {
            'signal': signal,
            'macd': self.macd_line,
            'signal_line': self.signal_line,
            'histogram': self.macd_line - self.signal_line,
            'price': price,
            'strategy': 'macd'
        }
    
    def reset(self):
        self.prices = []
        self.fast_ema = 0.0
        self.slow_ema = 0.0
        self.macd_line = 0.0
        self.signal_line = 0.0


class VWAPStrategy:
    """Volume Weighted Average Price strategy."""
    
    def __init__(self, window: int = 20):
        self.window = window
        
        self.prices: List[float] = []
        self.volumes: List[float] = []
    
    def update(self, price: float, volume: float = 1.0) -> Optional[Dict[str, Any]]:
        self.prices.append(price)
        self.volumes.append(volume)
        
        if len(self.prices) < 2:
            return None
        
        recent_prices = self.prices[-self.window:]
        recent_volumes = self.volumes[-self.window:]
        
        vwap = sum(p * v for p, v in zip(recent_prices, recent_volumes)) / sum(recent_volumes)
        
        signal = None
        
        if len(self.prices) >= 2:
            if price > vwap and self.prices[-2] <= vwap:
                signal = 'buy'
            elif price < vwap and self.prices[-2] >= vwap:
                signal = 'sell'
        
        return {
            'signal': signal,
            'vwap': vwap,
            'price': price,
            'deviation': (price - vwap) / vwap if vwap != 0 else 0,
            'strategy': 'vwap'
        }
    
    def reset(self):
        self.prices = []
        self.volumes = []


class SupertrendStrategy:
    """Supertrend indicator strategy."""
    
    def __init__(self, period: int = 10, multiplier: float = 3.0):
        self.period = period
        self.multiplier = multiplier
        
        self.highs: List[float] = []
        self.lows: List[float] = []
        self.closes: List[float] = []
        
        self.up_trend: float = 0.0
        self.down_trend: float = 0.0
    
    def update(self, high: float, low: float, close: float) -> Optional[Dict[str, Any]]:
        self.highs.append(high)
        self.lows.append(low)
        self.closes.append(close)
        
        if len(self.closes) < self.period:
            return None
        
        recent_high = max(self.highs[-self.period:])
        recent_low = min(self.lows[-self.period:])
        
        hl_avg = (recent_high + recent_low) / 2
        
        atr = sum(abs(self.highs[i] - self.lows[i]) for i in range(-self.period, 0)) / self.period
        
        up = hl_avg + (self.multiplier * atr)
        down = hl_avg - (self.multiplier * atr)
        
        prev_up = self.up_trend
        prev_down = self.down_trend
        
        if self.closes[-2] > prev_up:
            self.up_trend = up
        else:
            self.up_trend = max(up, prev_up)
        
        if self.closes[-2] < prev_down:
            self.down_trend = down
        else:
            self.down_trend = min(down, prev_down)
        
        signal = None
        
        if self.closes[-2] <= prev_down and close > self.down_trend:
            signal = 'buy'
        elif self.closes[-2] >= prev_up and close < self.up_trend:
            signal = 'sell'
        
        return {
            'signal': signal,
            'up_trend': self.up_trend,
            'down_trend': self.down_trend,
            'close': close,
            'strategy': 'supertrend'
        }
    
    def reset(self):
        self.highs = []
        self.lows = []
        self.closes = []
        self.up_trend = 0.0
        self.down_trend = 0.0
