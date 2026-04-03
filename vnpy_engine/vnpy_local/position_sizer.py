"""
Dynamic Position Sizing Module
==============================
Calculates optimal order sizes based on account equity, volatility, and risk parameters.
"""

import os
import math
from typing import Dict, Any, Optional
from loguru import logger


class PositionSizer:
    def __init__(self):
        self.risk_per_trade_pct = float(os.getenv("RISK_PER_TRADE_PCT", "1.0")) / 100.0
        self.max_position_pct = float(os.getenv("MAX_POSITION_PCT", "10.0")) / 100.0
        self.min_size = float(os.getenv("MIN_ORDER_SIZE", "0.001"))
        self.default_atr_pct = float(os.getenv("DEFAULT_ATR_PCT", "2.0")) / 100.0

    def calculate_size(
        self,
        equity: float,
        current_price: float,
        symbol: str,
        atr_pct: Optional[float] = None,
        current_position: float = 0.0,
    ) -> float:
        if current_price <= 0:
            logger.warning(f"Invalid price for {symbol}: {current_price}")
            return 0.0

        volatility = atr_pct if atr_pct is not None else self.default_atr_pct
        if volatility <= 0:
            volatility = self.default_atr_pct

        risk_amount = equity * self.risk_per_trade_pct

        stop_distance = current_price * volatility
        if stop_distance <= 0:
            stop_distance = current_price * 0.01

        size = risk_amount / stop_distance

        max_position_value = equity * self.max_position_pct
        max_size = max_position_value / current_price
        size = min(size, max_size)

        size = max(size, self.min_size)

        size = self._round_to_increment(symbol, size, current_price)

        logger.info(
            f"Position size for {symbol}: {size:.6f} "
            f"(equity={equity:.0f}, price={current_price:.2f}, "
            f"risk={self.risk_per_trade_pct:.1%}, vol={volatility:.1%})"
        )
        return size

    def _round_to_increment(self, symbol: str, size: float, price: float) -> float:
        if price >= 10000:
            increment = 0.001
        elif price >= 100:
            increment = 0.01
        elif price >= 1:
            increment = 0.1
        else:
            increment = 1.0

        return math.floor(size / increment) * increment

    def get_risk_adjusted_action(
        self,
        action: str,
        equity: float,
        current_price: float,
        symbol: str,
        atr_pct: Optional[float] = None,
        current_position: float = 0.0,
    ) -> Dict[str, Any]:
        if action == "close":
            return {"action": action, "size": abs(current_position), "reason": "close_position"}

        size = self.calculate_size(
            equity, current_price, symbol, atr_pct, current_position
        )

        if action == "sell" and current_position > 0:
            size = min(size, abs(current_position))

        if size <= 0:
            return {"action": "hold", "size": 0, "reason": "size_too_small"}

        return {
            "action": action,
            "size": size,
            "equity": equity,
            "price": current_price,
            "risk_pct": self.risk_per_trade_pct,
        }


position_sizer = PositionSizer()
