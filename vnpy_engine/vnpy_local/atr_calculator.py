"""
ATR (Average True Range) Calculator Module
==========================================
Calculates real-time ATR from kline data for volatility-based position sizing.
"""

import os
from collections import deque
from typing import Dict, Optional
from loguru import logger


class KlineBar:
    __slots__ = ["open", "high", "low", "close", "volume", "timestamp"]

    def __init__(self, open: float, high: float, low: float, close: float,
                 volume: float, timestamp: float):
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
        self.timestamp = timestamp


class ATRCalculator:
    def __init__(self):
        self.default_period = int(os.getenv("ATR_PERIOD", "14"))
        self._bars: Dict[str, deque] = {}
        self._atr_values: Dict[str, float] = {}
        self._prev_close: Dict[str, float] = {}
        self._max_bars = 500

    def update(self, symbol: str, bar: KlineBar) -> Optional[float]:
        if symbol not in self._bars:
            self._bars[symbol] = deque(maxlen=self._max_bars)

        self._bars[symbol].append(bar)

        if len(self._bars[symbol]) < 2:
            self._prev_close[symbol] = bar.close
            return None

        true_range = self._calc_true_range(symbol, bar)

        period = self.default_period
        if len(self._bars[symbol]) == 2:
            atr = true_range
        elif len(self._bars[symbol]) <= period:
            prev_atr = self._atr_values.get(symbol, 0)
            if prev_atr > 0:
                atr = (prev_atr * (len(self._bars[symbol]) - 1) + true_range) / len(self._bars[symbol])
            else:
                atr = true_range
        else:
            prev_atr = self._atr_values.get(symbol, 0)
            atr = (prev_atr * (period - 1) + true_range) / period

        self._atr_values[symbol] = atr
        self._prev_close[symbol] = bar.close
        return atr

    def _calc_true_range(self, symbol: str, bar: KlineBar) -> float:
        prev_close = self._prev_close.get(symbol, bar.open)
        high_low = bar.high - bar.low
        high_prevclose = abs(bar.high - prev_close)
        low_prevclose = abs(bar.low - prev_close)
        return max(high_low, high_prevclose, low_prevclose)

    def get_atr(self, symbol: str, period: Optional[int] = None) -> float:
        return self._atr_values.get(symbol, 0.0)

    def get_atr_pct(self, symbol: str, period: Optional[int] = None) -> float:
        atr = self._atr_values.get(symbol, 0.0)
        if symbol in self._prev_close and self._prev_close[symbol] > 0:
            return atr / self._prev_close[symbol]
        return 0.0

    def has_data(self, symbol: str, min_bars: int = 14) -> bool:
        return len(self._bars.get(symbol, [])) >= min_bars

    def get_status(self) -> Dict[str, Dict[str, float]]:
        result = {}
        for symbol in self._atr_values:
            result[symbol] = {
                "atr": self._atr_values[symbol],
                "atr_pct": self.get_atr_pct(symbol),
                "bars": len(self._bars.get(symbol, [])),
                "price": self._prev_close.get(symbol, 0),
            }
        return result


atr_calculator = ATRCalculator()
