"""
Smart Order Routing Module
==========================
Routes orders to the correct gateway (spot vs futures) based on symbol type.
Supports market and limit order types with automatic fallback.
"""

import os
import time
from enum import Enum
from typing import Dict, Any, Optional, Tuple
from loguru import logger


class MarketType(Enum):
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"


GATEWAY_MAP = {
    MarketType.SPOT: "BINANCE_SPOT",
    MarketType.LINEAR: "BINANCE_LINEAR",
    MarketType.INVERSE: "BINANCE_INVERSE",
}


class OrderRouter:
    def __init__(self):
        self._gateways: Dict[str, Dict[str, Any]] = {}
        self._default_order_type = OrderType(
            os.getenv("DEFAULT_ORDER_TYPE", "limit").lower()
        )

    def register_gateway(
        self, name: str, market_type: MarketType, connected: bool = False
    ):
        self._gateways[name] = {
            "name": name,
            "market_type": market_type,
            "connected": connected,
            "last_error": None,
            "registered_at": time.time(),
        }
        logger.info(f"Registered gateway: {name} ({market_type.value})")

    def update_gateway_status(self, name: str, connected: bool):
        if name in self._gateways:
            self._gateways[name]["connected"] = connected
            if not connected:
                self._gateways[name]["last_error"] = "disconnected"

    def select_gateway(
        self, symbol: str, order_type: Optional[OrderType] = None
    ) -> Tuple[str, MarketType, OrderType]:
        market_type = self._detect_market_type(symbol)
        gateway_name = GATEWAY_MAP.get(market_type, GATEWAY_MAP[MarketType.SPOT])

        if gateway_name in self._gateways:
            if self._gateways[gateway_name]["connected"]:
                effective_type = order_type or self._default_order_type
                return gateway_name, market_type, effective_type

            logger.warning(
                f"Primary gateway {gateway_name} down for {symbol}, "
                f"falling back to paper mode"
            )
            return "paper", market_type, order_type or self._default_order_type

        logger.warning(
            f"No gateway registered for {market_type.value}, "
            f"defaulting to spot for {symbol}"
        )
        fallback = GATEWAY_MAP[MarketType.SPOT]
        if fallback in self._gateways and self._gateways[fallback]["connected"]:
            return fallback, MarketType.SPOT, order_type or self._default_order_type

        return "paper", MarketType.SPOT, order_type or self._default_order_type

    def _detect_market_type(self, symbol: str) -> MarketType:
        symbol_upper = symbol.upper()

        if any(
            suffix in symbol_upper
            for suffix in ["-PERP", "_PERP", ":USDT", "/USDT:USDT"]
        ):
            return MarketType.LINEAR

        if any(
            suffix in symbol_upper
            for suffix in ["-INV", "_INV", ":BTC", "/BTC:BTC"]
        ):
            return MarketType.INVERSE

        spot_pairs = ["USDT", "BUSD", "USDC", "BTC", "ETH", "BNB"]
        if any(symbol_upper.endswith(pair) for pair in spot_pairs):
            return MarketType.SPOT

        if len(symbol_upper) >= 6 and not any(
            c in symbol_upper for c in ["-", "_", ":"]
        ):
            return MarketType.SPOT

        logger.warning(f"Could not detect market type for {symbol}, defaulting to spot")
        return MarketType.SPOT

    def get_gateway_info(self) -> Dict[str, Any]:
        return {
            name: {
                "market_type": info["market_type"].value,
                "connected": info["connected"],
                "last_error": info["last_error"],
            }
            for name, info in self._gateways.items()
        }

    @property
    def default_order_type(self) -> OrderType:
        return self._default_order_type


order_router = OrderRouter()
