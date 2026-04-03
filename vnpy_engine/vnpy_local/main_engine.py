"""
Main Engine Module
=================
VN.PY MainEngine wrapper with CTA Strategy integration.
"""

import os
import time
import json
import threading
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine as VnpyMainEngine

from vnpy_ctastrategy import CtaStrategyApp

from .shared_state import shared_state
from .rl_module import get_rl_agent
from .market_data import get_market_data_instance
from .strategies import CTA_STRATEGY_REGISTRY
from .risk_manager import risk_manager
from .order_tracker import order_tracker
from .position_sizer import position_sizer
from .order_router import order_router, MarketType, OrderType as RouterOrderType
from .atr_calculator import atr_calculator, KlineBar


TRADING_MODE = os.getenv("TRADING_MODE", "paper")
CONFIG_DIR = Path("/vnpy/config")
MEMORY_DIR = Path("/vnpy/memory")


class CtaStrategyManager:
    def __init__(self, cta_engine, trading_engine):
        self.cta_engine = cta_engine
        self.trading_engine = trading_engine
        self.cta_strategies: Dict[str, Any] = {}
        self.strategy_vt_symbols: Dict[str, str] = {}

    def add_strategy(self, strategy_name: str, class_name: str, vt_symbol: str, parameters: Dict) -> bool:
        if class_name not in CTA_STRATEGY_REGISTRY:
            logger.error(f"Strategy class {class_name} not found in registry")
            return False

        strategy_class = CTA_STRATEGY_REGISTRY[class_name]

        try:
            self.cta_engine.add_strategy(
                strategy_class,
                strategy_name,
                vt_symbol,
                parameters
            )
            self.cta_strategies[strategy_name] = {
                "class": class_name,
                "vt_symbol": vt_symbol,
                "parameters": parameters
            }
            self.strategy_vt_symbols[strategy_name] = vt_symbol
            logger.info(f"Added CTA strategy: {strategy_name} ({class_name})")
            return True
        except Exception as e:
            logger.error(f"Failed to add strategy {strategy_name}: {e}")
            return False

    def init_strategy(self, strategy_name: str) -> bool:
        try:
            self.cta_engine.init_strategy(strategy_name)
            logger.info(f"Initialized CTA strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to init strategy {strategy_name}: {e}")
            return False

    def start_strategy(self, strategy_name: str) -> bool:
        try:
            self.cta_engine.start_strategy(strategy_name)
            logger.info(f"Started CTA strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to start strategy {strategy_name}: {e}")
            return False

    def stop_strategy(self, strategy_name: str) -> bool:
        try:
            self.cta_engine.stop_strategy(strategy_name)
            logger.info(f"Stopped CTA strategy: {strategy_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop strategy {strategy_name}: {e}")
            return False

    def get_strategy_status(self, strategy_name: str) -> Dict[str, Any]:
        strategy_data = self.cta_engine.get_strategy_data(strategy_name)
        return {
            "inited": strategy_data.get("inited", False),
            "trading": strategy_data.get("trading", False),
            "pos": strategy_data.get("pos", 0)
        }

    def get_all_strategy_status(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: self.get_strategy_status(name)
            for name in self.cta_strategies.keys()
        }

    def remove_strategy(self, strategy_name: str) -> bool:
        try:
            self.cta_engine.remove_strategy(strategy_name)
            if strategy_name in self.cta_strategies:
                del self.cta_strategies[strategy_name]
            if strategy_name in self.strategy_vt_symbols:
                del self.strategy_vt_symbols[strategy_name]
            return True
        except Exception as e:
            logger.error(f"Failed to remove strategy {strategy_name}: {e}")
            return False


class TradingEngine:
    def __init__(self):
        self.running = False
        self.strategies: Dict[str, Any] = {}
        self.cta_strategies: Dict[str, Any] = {}
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.gateways: Dict[str, Any] = {}

        self.rl_agent = None
        self.strategy_config = self._load_strategies()
        self.market_data = None

        self._init_vnpy_engine()
        self._init_gateways()
        self._init_market_data()

    def _init_vnpy_engine(self):
        try:
            self.event_engine = EventEngine()
            self.vnpy_main_engine = VnpyMainEngine(self.event_engine)
            self.cta_app = self.vnpy_main_engine.add_app(CtaStrategyApp)
            self.cta_engine = self.vnpy_main_engine.get_engine("CtaStrategyApp")
            self.cta_manager = CtaStrategyManager(self.cta_engine, self)
            logger.info("VN.PY CtaEngine initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VN.PY CtaEngine: {e}")
            self.cta_engine = None
            self.cta_manager = None

    def _load_strategies(self) -> Dict[str, Any]:
        config_file = CONFIG_DIR / "strategies.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load strategies: {e}")

        return {
            "strategies": [
                {
                    "name": "RL_Strategy",
                    "symbol": "BTCUSDT",
                    "enabled": True,
                    "mode": TRADING_MODE,
                    "parameters": {
                        "window_size": 50,
                        "risk_threshold": 0.1
                    }
                }
            ]
        }

    def _init_gateways(self):
        api_key = os.getenv("BINANCE_API_KEY", "")
        secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        server_type = os.getenv("BINANCE_SERVER", "REAL").upper()

        if api_key and secret_key:
            logger.info(f"Binance gateway configured for live trading (Server: {server_type})")
            try:
                from vnpy_binance import BinanceLinearGateway
                self.vnpy_main_engine.add_gateway(BinanceLinearGateway)
                order_router.register_gateway("BINANCE_LINEAR", MarketType.LINEAR)

                try:
                    from vnpy_binance import BinanceSpotGateway
                    self.vnpy_main_engine.add_gateway(BinanceSpotGateway)
                    order_router.register_gateway("BINANCE_SPOT", MarketType.SPOT)
                except ImportError:
                    logger.warning("BinanceSpotGateway not available, spot trading disabled")

                self.gateways["binance_linear"] = {
                    "type": "binance_linear",
                    "mode": TRADING_MODE,
                    "server": server_type,
                    "connected": True
                }
                self.gateways["binance_spot"] = {
                    "type": "binance_spot",
                    "mode": TRADING_MODE,
                    "server": server_type,
                    "connected": True
                }

                setting = {
                    "API Key": api_key,
                    "API Secret": secret_key,
                    "Server": server_type,
                    "Kline Stream": "False",
                    "Proxy Host": "",
                    "Proxy Port": 0
                }
                self.vnpy_main_engine.connect(setting, gateway_name=BinanceLinearGateway.default_name)
                logger.info(f"Binance gateway connected successfully ({server_type})")
            except Exception as e:
                logger.error(f"Failed to add Binance gateway: {e}")
                self.gateways["sandbox"] = {
                    "type": "sandbox",
                    "mode": "paper",
                    "connected": True
                }
        else:
            logger.info("Running in sandbox/paper mode")
            self.gateways["sandbox"] = {
                "type": "sandbox",
                "mode": "paper",
                "connected": True
            }

    def _init_market_data(self):
        symbols = []
        for strategy in self.strategy_config.get("strategies", []):
            if strategy.get("enabled"):
                symbol = strategy.get("symbol", "BTCUSDT")
                if symbol not in symbols:
                    symbols.append(symbol)

        if not symbols:
            symbols = ["BTCUSDT"]

        self.market_data = get_market_data_instance(symbols)

        for symbol in symbols:
            if hasattr(self.market_data, 'subscribe_ticker'):
                self.market_data.subscribe_ticker(
                    lambda data, s=symbol: self._on_market_data(s, data),
                    symbol=symbol
                )
            elif hasattr(self.market_data, 'subscribe'):
                self.market_data.subscribe(
                    lambda data, s=symbol: self._on_market_data(s, data),
                    symbol=symbol
                )

        logger.info(f"Market data initialized for symbols: {symbols}")

    def _convert_to_bar(self, market_data: Dict[str, Any]) -> Optional[Any]:
        try:
            from vnpy.trader.object import BarData
            from datetime import datetime

            return BarData(
                symbol=market_data.get("symbol", "UNKNOWN"),
                exchange=None,
                datetime=datetime.fromtimestamp(market_data.get("timestamp", time.time())),
                open_price=market_data.get("open", market_data.get("price", 0)),
                high_price=market_data.get("high", market_data.get("price", 0)),
                low_price=market_data.get("low", market_data.get("price", 0)),
                close_price=market_data.get("price", 0),
                volume=market_data.get("volume", 0),
                turnover=0,
                open_interest=0
            )
        except Exception as e:
            logger.error(f"Failed to convert market data to bar: {e}")
            return None

    def start(self):
        global TRADING_MODE

        if self.running:
            logger.warning("Engine already running")
            return

        self.running = True
        logger.info("Trading Engine started")

        self.rl_agent = get_rl_agent()

        if self.market_data:
            self.market_data.start()

        order_tracker.register_event_handlers(self.event_engine)

        if TRADING_MODE == "live":
            preflight = self._preflight_check()
            if not preflight["ready"]:
                logger.warning("Pre-flight checks failed, falling back to paper mode")
                TRADING_MODE = "paper"
            else:
                self._sync_account_from_exchange()
                self._start_periodic_sync()

        self._load_positions_from_state()
        self._start_strategies()
        self._init_cta_strategies()

        shared_state.set_system_status("engine", {
            "status": "running",
            "mode": TRADING_MODE,
            "timestamp": time.time()
        })

    def stop(self):
        self.running = False
        logger.info("Trading Engine stopped")

        self._stop_cta_strategies()

        if self.market_data:
            self.market_data.stop()

        self._save_positions_to_state()

        if self.rl_agent:
            self.rl_agent.save_checkpoint()

        try:
            order_tracker.flush_to_disk()
        except Exception as e:
            logger.error(f"Failed to flush order tracker: {e}")

        if hasattr(self, 'vnpy_main_engine'):
            try:
                self.vnpy_main_engine.close()
            except Exception as e:
                logger.error(f"Error closing VN.PY main engine: {e}")

        shared_state.set_system_status("engine", {
            "status": "stopped",
            "timestamp": time.time()
        })

    def _load_positions_from_state(self):
        saved_positions = shared_state.get_all_positions()
        self.positions = saved_positions
        logger.info(f"Loaded {len(self.positions)} positions from state")

    def _save_positions_to_state(self):
        for symbol, position in self.positions.items():
            shared_state.set_position(symbol, position)
        logger.info(f"Saved {len(self.positions)} positions to state")

    def _start_strategies(self):
        for strategy_cfg in self.strategy_config.get("strategies", []):
            strategy_type = strategy_cfg.get("type", "rl")

            if not strategy_cfg.get("enabled", False):
                continue

            if strategy_type in ["cta", "cta_rl"]:
                self.cta_strategies[strategy_cfg["name"]] = {
                    "config": strategy_cfg,
                    "running": False,
                    "pnl": 0.0,
                    "trades": 0
                }
            else:
                self.strategies[strategy_cfg["name"]] = {
                    "config": strategy_cfg,
                    "running": True,
                    "pnl": 0.0,
                    "trades": 0
                }
                logger.info(f"Started strategy: {strategy_cfg['name']}")

    def _init_cta_strategies(self):
        if not self.cta_manager:
            logger.warning("CtaEngine not available, skipping CTA strategy initialization")
            return

        for strategy_cfg in self.strategy_config.get("strategies", []):
            strategy_type = strategy_cfg.get("type", "rl")

            if strategy_type not in ["cta", "cta_rl"]:
                continue

            if not strategy_cfg.get("enabled", False):
                continue

            strategy_name = strategy_cfg.get("name")
            class_name = strategy_cfg.get("class", "MomentumCtaStrategy")
            vt_symbol = strategy_cfg.get("vt_symbol", f"{strategy_cfg.get('symbol', 'BTCUSDT')}.BINANCE")
            parameters = strategy_cfg.get("parameters", {})

            success = self.cta_manager.add_strategy(
                strategy_name,
                class_name,
                vt_symbol,
                parameters
            )

            if success:
                self.cta_manager.init_strategy(strategy_name)
                self.cta_manager.start_strategy(strategy_name)

                if strategy_name in self.cta_strategies:
                    self.cta_strategies[strategy_name]["running"] = True

                logger.info(f"Started CTA strategy: {strategy_name}")

    def _stop_cta_strategies(self):
        if not self.cta_manager:
            return

        for strategy_name in list(self.cta_strategies.keys()):
            self.cta_manager.stop_strategy(strategy_name)
            logger.info(f"Stopped CTA strategy: {strategy_name}")

    def process_market_data(self, symbol: str, data: Dict[str, Any]):
        if not self.running:
            return

        market_state = {
            symbol: {
                "price": data.get("price", 0),
                "volume": data.get("volume", 0),
                "position": self.positions.get(symbol, {}).get("size", 0),
                "pnl": self.positions.get(symbol, {}).get("pnl", 0),
                "volatility": data.get("volatility", 0.5),
                "trend": data.get("trend", 0)
            }
        }

        if self.rl_agent and "RL_Strategy" in self.strategies:
            decision = self.rl_agent.get_action_with_risk(market_state)

            shared_state.log_rl_decision({
                "symbol": symbol,
                "action": decision["action"],
                "expected_pnl": decision["evaluation"].get("expected_pnl", 0),
                "risk_metrics": decision["evaluation"].get("risk_metrics", {}),
                "timestamp": time.time()
            })

            if decision["action"] != "hold":
                self._execute_action(symbol, decision["action"], data.get("price", 0))

        if self.cta_engine and self.rl_agent:
            self._process_cta_with_rl(symbol, data, market_state)

    def _process_cta_with_rl(self, symbol: str, data: Dict[str, Any], market_state: Dict):
        bar = self._convert_to_bar(data)
        if not bar:
            return

        for strategy_name, strategy_info in self.cta_strategies.items():
            config = strategy_info.get("config", {})
            if config.get("type") == "cta_rl" and config.get("parameters", {}).get("rl_enabled", True):
                try:
                    vt_symbol = config.get("vt_symbol", f"{symbol}.BINANCE")
                    if symbol in vt_symbol or vt_symbol.split(".")[0] in symbol:
                        strategy_data = self.cta_engine.get_strategy_data(strategy_name)
                        pos = strategy_data.get("pos", 0)

                        rl_decision = self.rl_agent.get_action_with_risk(market_state)

                        shared_state.log_rl_decision({
                            "symbol": symbol,
                            "strategy": strategy_name,
                            "cta_action": "signal_generated",
                            "rl_action": rl_decision["action"],
                            "rl_approved": rl_decision["action"] != "hold",
                            "timestamp": time.time()
                        })
                except Exception as e:
                    logger.error(f"Error in CTA+RL hybrid processing: {e}")

    def _on_market_data(self, symbol: str, data: Dict[str, Any]):
        if "high" in data and "low" in data and "open" in data:
            bar = KlineBar(
                open=data["open"],
                high=data["high"],
                low=data["low"],
                close=data.get("price", data.get("close", data["open"])),
                volume=data.get("volume", 0),
                timestamp=data.get("timestamp", time.time()),
            )
            atr_calculator.update(symbol, bar)

        self.process_market_data(symbol, data)

    def _execute_action(self, symbol: str, action: str, price: float, size: float = 0):
        if TRADING_MODE != "live":
            effective_size = max(int(size), 1) if size > 0 else 1
            return self._execute_paper_order(symbol, action, price, effective_size)

        risk_result = risk_manager.validate_order(
            symbol, action, size, self.positions, price
        )
        if not risk_result["allowed"]:
            logger.warning(f"Order rejected by risk manager: {symbol} {action} x{size} - {risk_result['reason']}")
            order_id = f"ord_{int(time.time() * 1000)}"
            rejected_order = {
                "order_id": order_id,
                "symbol": symbol,
                "action": action,
                "size": size,
                "price": price,
                "status": "rejected",
                "reason": risk_result["reason"],
                "timestamp": time.time(),
                "mode": TRADING_MODE
            }
            self.orders[order_id] = rejected_order
            shared_state.set_order(order_id, rejected_order)
            return rejected_order

        equity = risk_manager.current_equity
        current_pos = self.positions.get(symbol, {}).get("size", 0)
        atr_pct = atr_calculator.get_atr_pct(symbol) if atr_calculator.has_data(symbol) else None
        sizing = position_sizer.get_risk_adjusted_action(
            action, equity, price, symbol, atr_pct=atr_pct, current_position=current_pos
        )
        effective_size = sizing.get("size", 1)

        if sizing["action"] == "hold":
            logger.info(f"Position sizing returned hold for {symbol}")
            return None

        return self._execute_live_order(symbol, sizing["action"], price, effective_size)

    def _execute_paper_order(self, symbol: str, action: str, price: float, size: float = 1):
        order_id = f"ord_{int(time.time() * 1000)}"
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "size": size,
            "price": price,
            "status": "filled",
            "timestamp": time.time(),
            "mode": TRADING_MODE
        }
        self.orders[order_id] = order

        if symbol not in self.positions:
            self.positions[symbol] = {"size": 0, "pnl": 0, "avg_price": price}

        pos = self.positions[symbol]

        if action == "buy":
            pos["size"] = pos.get("size", 0) + size
        elif action == "sell":
            pos["size"] = pos.get("size", 0) - size
        elif action == "close":
            pos["size"] = 0

        pos["avg_price"] = price
        self.positions[symbol] = pos

        shared_state.set_order(order_id, order)
        shared_state.set_position(symbol, pos)

        logger.info(f"Paper order executed: {action} {symbol} x{size} @ {price}")
        return order

    def _execute_live_order(self, symbol: str, action: str, price: float, size: float = 1,
                            order_type: Optional[str] = None):
        order_id = f"ord_{int(time.time() * 1000)}"

        if not self._check_rate_limit():
            logger.warning(f"Rate limit exceeded, rejecting order: {symbol} {action}")
            return self._create_rejected_order(order_id, symbol, action, size, price, "rate_limit_exceeded")

        router_order_type = RouterOrderType(order_type) if order_type else None
        gateway_name, market_type, effective_order_type = order_router.select_gateway(
            symbol, router_order_type
        )

        if gateway_name == "paper":
            logger.warning(f"No live gateway available for {symbol}, falling back to paper")
            return self._execute_paper_order(symbol, action, price, size)

        retry_count = 0
        max_retries = int(os.getenv("ORDER_MAX_RETRIES", "3"))
        base_delay = float(os.getenv("ORDER_RETRY_BASE_DELAY", "1.0"))

        while retry_count <= max_retries:
            try:
                from vnpy.trader.object import OrderRequest
                from vnpy.trader.constant import Direction, Offset, Exchange
                from vnpy.trader.constant import OrderType as VnpyOrderType

                direction = Direction.LONG if action in ["buy", "close_short"] else Direction.SHORT
                offset = Offset.OPEN if action in ["buy", "close_short"] else Offset.CLOSE

                exchange = Exchange.GLOBAL

                vnpy_order_type = (
                    VnpyOrderType.MARKET
                    if effective_order_type == RouterOrderType.MARKET
                    else VnpyOrderType.LIMIT
                )

                order_req = OrderRequest(
                    symbol=symbol,
                    exchange=exchange,
                    direction=direction,
                    offset=offset,
                    type=vnpy_order_type,
                    price=price if effective_order_type == RouterOrderType.LIMIT else 0,
                    volume=size,
                    reference=f"rl_{order_id}"
                )

                vt_orderid = self.vnpy_main_engine.send_order(order_req, gateway_name=gateway_name)

                order = {
                    "order_id": order_id,
                    "vt_orderid": vt_orderid,
                    "symbol": symbol,
                    "action": action,
                    "size": size,
                    "price": price,
                    "order_type": effective_order_type.value,
                    "gateway": gateway_name,
                    "status": "submitted",
                    "timestamp": time.time(),
                    "mode": TRADING_MODE
                }
                self.orders[order_id] = order
                shared_state.set_order(order_id, order)

                order_tracker.track_order(order_id, vt_orderid, order_req)
                order_tracker._persist_order(order_id, order)

                logger.info(
                    f"Live order submitted: {action} {symbol} x{size} @ {price} "
                    f"[{effective_order_type.value}] via {gateway_name} -> {vt_orderid}"
                )
                return order

            except Exception as e:
                error_str = str(e)
                if "rate" in error_str.lower() or "limit" in error_str.lower():
                    retry_count += 1
                    if retry_count > max_retries:
                        logger.error(f"Order rejected after {max_retries} retries: {symbol} {action}")
                        return self._create_rejected_order(order_id, symbol, action, size, price, f"rate_limit_after_retries: {error_str}")

                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.warning(f"Rate limited, retrying in {delay}s (attempt {retry_count}/{max_retries})")
                    time.sleep(delay)
                else:
                    logger.error(f"Live order submission failed: {symbol} {action} x{size} - {error_str}")
                    order_router.update_gateway_status(gateway_name, False)
                    return self._create_rejected_order(order_id, symbol, action, size, price, error_str)

        return self._create_rejected_order(order_id, symbol, action, size, price, "max_retries_exceeded")

    def _check_rate_limit(self) -> bool:
        now = time.time()
        if not hasattr(self, '_order_timestamps'):
            self._order_timestamps = []

        window = 60
        max_orders_per_minute = int(os.getenv("MAX_ORDERS_PER_MINUTE", "60"))

        self._order_timestamps = [t for t in self._order_timestamps if now - t < window]

        if len(self._order_timestamps) >= max_orders_per_minute:
            return False

        self._order_timestamps.append(now)
        return True

    def _create_rejected_order(self, order_id: str, symbol: str, action: str, size: float, price: float, reason: str):
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "action": action,
            "size": size,
            "price": price,
            "status": "rejected",
            "reason": reason,
            "timestamp": time.time(),
            "mode": TRADING_MODE
        }
        self.orders[order_id] = order
        shared_state.set_order(order_id, order)
        return order

    def _close_position(self, symbol: str):
        if symbol not in self.positions:
            logger.warning(f"No position to close for {symbol}")
            return None

        pos = self.positions[symbol]
        current_size = pos.get("size", 0)

        if current_size == 0:
            logger.info(f"No open position for {symbol}")
            return None

        action = "sell" if current_size > 0 else "buy"
        price = self.market_data.get_price(symbol) if self.market_data else pos.get("avg_price", 0)

        logger.info(f"Closing position: {symbol} size={current_size}")
        return self._execute_action(symbol, action, price, abs(current_size))

    def _sync_account_from_exchange(self):
        if TRADING_MODE != "live":
            return

        try:
            from vnpy.trader.constant import Direction
            accounts = self.vnpy_main_engine.get_all_accounts()
            for account in accounts:
                balance = getattr(account, "balance", 0)
                available = getattr(account, "available", 0)
                frozen = getattr(account, "frozen", 0)
                risk_manager.update_equity(balance)
                shared_state.set_system_status("account", {
                    "balance": balance,
                    "available": available,
                    "frozen": frozen,
                    "timestamp": time.time()
                })
            logger.info(f"Account synced: balance={balance}, available={available}")

            positions = self.vnpy_main_engine.get_all_positions()
            exchange_positions = {}
            for pos in positions:
                symbol = getattr(pos, "symbol", "UNKNOWN")
                direction = getattr(pos, "direction", None)
                size = getattr(pos, "volume", 0)
                price = getattr(pos, "price", 0)

                if direction == Direction.LONG:
                    net_size = size
                elif direction == Direction.SHORT:
                    net_size = -size
                else:
                    net_size = size

                exchange_positions[symbol] = {
                    "size": net_size,
                    "avg_price": price,
                    "source": "exchange"
                }

            self._reconcile_positions(exchange_positions)

        except Exception as e:
            logger.error(f"Failed to sync account from exchange: {e}")
            self._handle_gateway_failure("sync_account", e)

    def _reconcile_positions(self, exchange_positions: Dict[str, Dict[str, Any]]):
        discrepancies = []
        for symbol, exchange_pos in exchange_positions.items():
            local_pos = self.positions.get(symbol, {})
            local_size = local_pos.get("size", 0)
            exchange_size = exchange_pos.get("size", 0)

            if abs(local_size - exchange_size) > 0.001:
                discrepancies.append({
                    "symbol": symbol,
                    "local_size": local_size,
                    "exchange_size": exchange_size,
                    "diff": exchange_size - local_size
                })
                logger.warning(
                    f"Position discrepancy: {symbol} local={local_size} "
                    f"exchange={exchange_size}"
                )
                self.positions[symbol] = {
                    "size": exchange_size,
                    "avg_price": exchange_pos.get("avg_price", local_pos.get("avg_price", 0)),
                    "pnl": local_pos.get("pnl", 0),
                    "last_sync": time.time()
                }

        if discrepancies:
            logger.warning(f"Reconciled {len(discrepancies)} position discrepancies")
            shared_state.set_system_status("reconciliation", {
                "discrepancies": discrepancies,
                "timestamp": time.time()
            })
        else:
            logger.info("Position reconciliation: no discrepancies")

    def _start_periodic_sync(self):
        sync_interval = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))

        def _sync_loop():
            while self.running:
                try:
                    time.sleep(sync_interval)
                    if self.running and TRADING_MODE == "live":
                        self._sync_account_from_exchange()
                        self._check_gateway_health()
                except Exception as e:
                    logger.error(f"Periodic sync error: {e}")

        self._sync_thread = threading.Thread(target=_sync_loop, daemon=True)
        self._sync_thread.start()
        logger.info(f"Periodic account sync started (interval={sync_interval}s)")

    def emergency_stop(self):
        logger.critical("EMERGENCY STOP TRIGGERED")

        self.running = False

        if TRADING_MODE == "live":
            try:
                active_orders = order_tracker.get_active_orders()
                for order_id, order in active_orders.items():
                    try:
                        vt_orderid = order.get("vt_orderid")
                        if vt_orderid:
                            self.vnpy_main_engine.cancel_order(vt_orderid)
                            logger.info(f"Cancelled active order: {order_id}")
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order_id}: {e}")
            except Exception as e:
                logger.error(f"Error during emergency order cancellation: {e}")

        for symbol in list(self.positions.keys()):
            try:
                self._close_position(symbol)
            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")

        self._stop_cta_strategies()

        if self.market_data:
            self.market_data.stop()

        shared_state.set_system_status("emergency_stop", {
            "triggered_at": time.time(),
            "mode": TRADING_MODE,
            "positions_closed": len(self.positions),
            "orders_cancelled": len(order_tracker.get_active_orders())
        })

        logger.critical("Emergency stop completed. All positions closed, orders cancelled.")

    def switch_strategy(self, strategy_name: str, action: str) -> bool:
        if action == "stop":
            if strategy_name in self.strategies:
                self.strategies[strategy_name]["running"] = False
                logger.info(f"Strategy stopped: {strategy_name}")
                return True
            if strategy_name in self.cta_strategies:
                self.cta_manager.stop_strategy(strategy_name)
                self.cta_strategies[strategy_name]["running"] = False
                logger.info(f"CTA strategy stopped: {strategy_name}")
                return True
            logger.warning(f"Unknown strategy: {strategy_name}")
            return False

        elif action == "start":
            if strategy_name in self.strategies:
                self.strategies[strategy_name]["running"] = True
                logger.info(f"Strategy started: {strategy_name}")
                return True
            if strategy_name in self.cta_strategies:
                self.cta_manager.start_strategy(strategy_name)
                self.cta_strategies[strategy_name]["running"] = True
                logger.info(f"CTA strategy started: {strategy_name}")
                return True
            logger.warning(f"Unknown strategy: {strategy_name}")
            return False

        elif action == "reload":
            self.strategy_config = self._load_strategies()
            logger.info(f"Strategy config reloaded for: {strategy_name}")
            return True

        logger.warning(f"Unknown action: {action}")
        return False

    def _check_gateway_health(self):
        for gw_name, gw_info in self.gateways.items():
            try:
                if gw_info.get("type") in ["binance_linear", "binance_spot"] and TRADING_MODE == "live":
                    accounts = self.vnpy_main_engine.get_all_accounts()
                    if not accounts:
                        logger.warning(f"Gateway {gw_name} appears disconnected")
                        self._handle_gateway_failure(gw_name, Exception("no_account_data"))
                    else:
                        if gw_info.get("connected") == False:
                            logger.info(f"Gateway {gw_name} reconnected")
                            gw_info["connected"] = True
                            gw_info["last_health_check"] = time.time()
            except Exception as e:
                logger.error(f"Gateway health check failed for {gw_name}: {e}")
                self._handle_gateway_failure(gw_name, e)

    def _handle_gateway_failure(self, gateway_name: str, error: Exception):
        if gateway_name in self.gateways:
            self.gateways[gateway_name]["connected"] = False
            self.gateways[gateway_name]["last_error"] = str(error)
            self.gateways[gateway_name]["last_error_time"] = time.time()

        logger.critical(f"Gateway failure: {gateway_name} - {error}. Falling back to paper mode.")

        global TRADING_MODE
        TRADING_MODE = "paper"

        shared_state.set_system_status("gateway_failure", {
            "gateway": gateway_name,
            "error": str(error),
            "fallback_mode": "paper",
            "timestamp": time.time()
        })

    def _preflight_check(self) -> Dict[str, Any]:
        checks = {
            "trading_mode": TRADING_MODE,
            "engine_running": self.running,
            "gateways_connected": all(g.get("connected", False) for g in self.gateways.values()),
            "market_data_active": self.market_data is not None,
            "risk_manager_active": risk_manager is not None,
            "order_tracker_active": order_tracker is not None,
        }

        if TRADING_MODE == "live":
            api_key = os.getenv("BINANCE_API_KEY", "")
            secret_key = os.getenv("BINANCE_SECRET_KEY", "")
            checks["api_key_configured"] = bool(api_key and secret_key)
            checks["gateways_connected"] = self.gateways.get("binance", {}).get("connected", False)

        all_passed = all(checks.values())
        checks["ready"] = all_passed

        if not all_passed:
            failed = [k for k, v in checks.items() if not v]
            logger.warning(f"Pre-flight checks failed: {failed}")

        return checks

    def get_status(self) -> Dict[str, Any]:
        cta_status = {}
        if self.cta_manager:
            cta_status = self.cta_manager.get_all_strategy_status()

        return {
            "running": self.running,
            "mode": TRADING_MODE,
            "positions": self.positions,
            "orders": len(self.orders),
            "rl_strategies": {name: {"running": s["running"], "pnl": s["pnl"]}
                             for name, s in self.strategies.items()},
            "cta_strategies": cta_status,
            "gateways": list(self.gateways.keys()),
            "execution_summary": order_tracker.get_execution_summary(),
            "risk_status": risk_manager.get_risk_status(),
            "timestamp": time.time()
        }

    def get_positions(self) -> Dict[str, Dict[str, Any]]:
        return self.positions

    def get_pnl(self) -> Dict[str, Any]:
        total_pnl = sum(p.get("pnl", 0) for p in self.positions.values())
        return {
            "total": float(total_pnl),
            "by_symbol": {s: float(p.get("pnl", 0)) for s, p in self.positions.items()}
        }

    def set_position_target(self, symbol: str, target_size: int) -> bool:
        current = self.positions.get(symbol, {}).get("size", 0)
        diff = target_size - current

        if diff > 0:
            self._execute_action(symbol, "buy", 0)
        elif diff < 0:
            self._execute_action(symbol, "sell", 0)

        return True


engine: Optional[TradingEngine] = None


def get_engine() -> TradingEngine:
    global engine
    if engine is None:
        engine = TradingEngine()
    return engine
