"""
Binance Testnet Futures Client
==============================
Direct REST API client for Binance USDT-M Futures Testnet.
Uses HMAC-SHA256 signing for authenticated endpoints.

Testnet URLs:
  REST: https://testnet.binancefuture.com
  WebSocket: wss://fstream.binancefuture.com/ws

This client handles:
  - Account info and balance
  - Market orders (buy/sell)
  - Position queries
  - Order cancellation
  - Leverage settings
"""

import hmac
import hashlib
import time
import urllib.parse
from typing import Dict, Any, Optional, List, Union
from loguru import logger

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class BinanceTestnetClient:
    """Binance USDT-M Futures Testnet REST client."""

    BASE_URL = "https://testnet.binancefuture.com"

    def __init__(self, api_key: str, secret_key: str):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library is required")

        self.api_key = api_key
        self.secret_key = secret_key
        self.session = requests.Session()
        self.session.headers.update({
            "X-MBX-APIKEY": self.api_key,
            "Content-Type": "application/x-www-form-urlencoded",
        })

        self.hedge_mode = False
        self._check_connection()
        self._detect_position_mode()

        logger.info("BinanceTestnetClient initialized")

    def _check_connection(self) -> bool:
        """Verify testnet connectivity."""
        try:
            resp = self.session.get(f"{self.BASE_URL}/fapi/v1/time", timeout=10)
            if resp.status_code == 200:
                server_time = resp.json().get("serverTime", 0)
                local_time = int(time.time() * 1000)
                drift = abs(server_time - local_time)
                logger.info(f"Testnet connected. Server time drift: {drift}ms")
                if drift > 5000:
                    logger.warning(f"Clock drift {drift}ms may cause signature errors")
                return True
            else:
                logger.error(f"Testnet time check failed: {resp.status_code} {resp.text}")
                return False
        except Exception as e:
            logger.error(f"Testnet connection failed: {e}")
            return False

    def _detect_position_mode(self):
        """Detect if account is in hedge (dual) or one-way position mode."""
        try:
            resp = self._get("/fapi/v1/positionSide/dual", signed=True)
            self.hedge_mode = resp.get("dualSidePosition", False)
            mode_str = "hedge" if self.hedge_mode else "one-way"
            logger.info(f"Position mode: {mode_str}")
        except Exception as e:
            logger.warning(f"Could not detect position mode: {e}, defaulting to one-way")
            self.hedge_mode = False

    def _sign(self, params: Dict[str, Any]) -> str:
        """Create HMAC-SHA256 signature for authenticated requests."""
        query_string = urllib.parse.urlencode(params, doseq=True)
        signature = hmac.new(
            self.secret_key.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return query_string + "&signature=" + signature

    def _get(self, path: str, params: Dict[str, Any] = None, signed: bool = False) -> Dict[str, Any]:
        """Send authenticated or public GET request."""
        url = f"{self.BASE_URL}{path}"
        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query = self._sign(params)
            resp = self.session.get(f"{url}?{query}", timeout=10)
        else:
            resp = self.session.get(url, params=params, timeout=10)

        return self._handle_response(resp)

    def _post(self, path: str, params: Dict[str, Any] = None, signed: bool = False) -> Dict[str, Any]:
        """Send authenticated or public POST request."""
        url = f"{self.BASE_URL}{path}"
        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query = self._sign(params)
            resp = self.session.post(f"{url}?{query}", timeout=10)
        else:
            resp = self.session.post(url, data=params, timeout=10)

        return self._handle_response(resp)

    def _delete(self, path: str, params: Dict[str, Any] = None, signed: bool = False) -> Dict[str, Any]:
        """Send authenticated DELETE request."""
        url = f"{self.BASE_URL}{path}"
        if params is None:
            params = {}

        if signed:
            params["timestamp"] = int(time.time() * 1000)
            query = self._sign(params)
            resp = self.session.delete(f"{url}?{query}", timeout=10)
        else:
            resp = self.session.delete(url, params=params, timeout=10)

        return self._handle_response(resp)

    def _handle_response(self, resp: requests.Response) -> Dict[str, Any]:
        """Parse and validate API response."""
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError(f"Invalid JSON response: {resp.text}")

        if resp.status_code != 200:
            code = data.get("code", "unknown")
            msg = data.get("msg", "unknown error")
            raise RuntimeError(f"API error {resp.status_code}: [{code}] {msg}")

        return data

    # ─── Account ───────────────────────────────────────────────────────

    def get_account(self) -> Dict[str, Any]:
        """Get account information including balance and margins."""
        return self._get("/fapi/v2/account", signed=True)

    def get_balance(self) -> List[Dict[str, Any]]:
        """Get futures wallet balance."""
        return self._get("/fapi/v2/balance", signed=True)

    def get_position_risk(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get position risk (open positions)."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._get("/fapi/v2/positionRisk", params=params, signed=True)

    # ─── Market Data ───────────────────────────────────────────────────

    def get_price(self, symbol: str) -> float:
        """Get latest mark price for a symbol."""
        data = self._get("/fapi/v1/ticker/price", params={"symbol": symbol.upper()})
        return float(data["price"])

    def get_orderbook(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get order book snapshot."""
        return self._get("/fapi/v1/depth", params={"symbol": symbol.upper(), "limit": limit})

    def get_klines(self, symbol: str, interval: str = "1m", limit: int = 100) -> List[List]:
        """Get kline/candlestick data."""
        return self._get(
            "/fapi/v1/klines",
            params={"symbol": symbol.upper(), "interval": interval, "limit": limit},
        )

    # ─── Trading ───────────────────────────────────────────────────────

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol."""
        return self._post(
            "/fapi/v1/leverage",
            params={"symbol": symbol.upper(), "leverage": leverage},
            signed=True,
        )

    def set_margin_type(self, symbol: str, margin_type: str = "CROSSED") -> Dict[str, Any]:
        """Set margin type (CROSSED or ISOLATED)."""
        try:
            return self._post(
                "/fapi/v1/marginType",
                params={"symbol": symbol.upper(), "marginType": margin_type.upper()},
                signed=True,
            )
        except RuntimeError as e:
            if "-4046" in str(e):
                return {"note": "Margin type already set"}
            raise

    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: Union[float, str],
        position_side: str = None,
    ) -> Dict[str, Any]:
        """
        Place a market order.

        Args:
            symbol: Trading pair (e.g. BTCUSDT)
            side: BUY or SELL
            quantity: Order quantity (float or formatted string)
            position_side: LONG or SHORT (hedge mode only)
        """
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "MARKET",
            "quantity": self._format_quantity(symbol, quantity),
        }

        if position_side and self.hedge_mode:
            params["positionSide"] = position_side.upper()

        pos_side_str = f", positionSide={position_side}" if position_side else ""
        
        logger.info(
            f"Placing market order: {side.upper()} {quantity} {symbol} "
            f"(hedge_mode={self.hedge_mode}{pos_side_str})"
        )

        return self._post("/fapi/v1/order", params=params, signed=True)

    def place_limit_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        position_side: str = None,
        time_in_force: str = "GTC",
    ) -> Dict[str, Any]:
        """Place a limit order."""
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),
            "type": "LIMIT",
            "timeInForce": time_in_force,
            "quantity": self._format_quantity(symbol, quantity),
            "price": f"{price:.8f}",
        }

        if position_side:
            params["positionSide"] = position_side.upper()

        return self._post("/fapi/v1/order", params=params, signed=True)

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._delete(
            "/fapi/v1/order",
            params={"symbol": symbol.upper(), "orderId": order_id},
            signed=True,
        )

    def cancel_all_orders(self, symbol: str) -> Dict[str, Any]:
        """Cancel all open orders for a symbol."""
        return self._delete(
            "/fapi/v1/allOpenOrders",
            params={"symbol": symbol.upper()},
            signed=True,
        )

    def get_open_orders(self, symbol: str = None) -> List[Dict[str, Any]]:
        """Get open orders."""
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        return self._get("/fapi/v1/openOrders", params=params, signed=True)

    # ─── Helpers ───────────────────────────────────────────────────────

    def _get_symbol_precision(self, symbol: str) -> int:
        """Get quantity precision from exchange info."""
        try:
            info = self._get("/fapi/v1/exchangeInfo")
            for s in info.get("symbols", []):
                if s["symbol"] == symbol.upper():
                    return int(s.get("quantityPrecision", 3))
        except Exception:
            pass
        fallback = {"BTCUSDT": 3, "ETHUSDT": 3, "SOLUSDT": 2, "BNBUSDT": 3}
        return fallback.get(symbol.upper(), 3)

    def _format_quantity(self, symbol: str, quantity: float) -> str:
        """Format quantity to correct precision for the symbol."""
        precision = self._get_symbol_precision(symbol)
        return f"{quantity:.{precision}f}"

    def get_symbol_filters(self, symbol: str) -> Dict[str, Any]:
        """Get trading rules for a symbol (lot size, price precision, etc.)."""
        info = self._get("/fapi/v1/exchangeInfo")
        for s in info.get("symbols", []):
            if s["symbol"] == symbol.upper():
                filters = {}
                for f in s.get("filters", []):
                    filters[f["filterType"]] = f
                return {
                    "status": s["status"],
                    "baseAsset": s["baseAsset"],
                    "quoteAsset": s["quoteAsset"],
                    "filters": filters,
                }
        return {}

    def close(self):
        """Close the HTTP session."""
        self.session.close()
        logger.info("BinanceTestnetClient closed")
