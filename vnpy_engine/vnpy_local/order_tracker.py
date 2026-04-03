"""
Order Tracker Module
====================
Full lifecycle order management with VN.PY event callbacks.
Tracks orders from submission → filled/cancelled/rejected.
"""

import os
import time
import json
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from pathlib import Path
from loguru import logger

from vnpy.event import Event, EventEngine
from vnpy.trader.event import (
    EVENT_ORDER,
    EVENT_TRADE,
    EVENT_POSITION,
    EVENT_ACCOUNT,
    EVENT_LOG,
)

PERSISTENCE_DIR = Path(os.getenv("ORDER_TRACKER_DIR", "/vnpy/memory/orders"))


class OrderTracker:
    def __init__(self):
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.completed_orders: Dict[str, Dict[str, Any]] = {}
        self.order_to_vt: Dict[str, str] = {}
        self.vt_to_order: Dict[str, str] = {}
        self.order_callbacks: Dict[str, Callable] = {}
        self._lock = threading.Lock()
        self._event_handlers_registered = False
        self._persistence_dir = PERSISTENCE_DIR
        self._persistence_dir.mkdir(parents=True, exist_ok=True)
        self._load_from_disk()

    def register_event_handlers(self, event_engine: EventEngine):
        if self._event_handlers_registered:
            return

        event_engine.register(EVENT_ORDER, self._on_order_event)
        event_engine.register(EVENT_TRADE, self._on_trade_event)
        event_engine.register(EVENT_LOG, self._on_log_event)

        self._event_handlers_registered = True
        logger.info("OrderTracker event handlers registered")

    def track_order(self, order_id: str, vt_orderid: str, order_request: Any):
        with self._lock:
            self.active_orders[order_id] = {
                "order_id": order_id,
                "vt_orderid": vt_orderid,
                "symbol": order_request.symbol,
                "direction": order_request.direction.value if hasattr(order_request.direction, 'value') else str(order_request.direction),
                "offset": order_request.offset.value if hasattr(order_request.offset, 'value') else str(order_request.offset),
                "price": order_request.price,
                "volume": order_request.volume,
                "status": "submitted",
                "submitted_at": time.time(),
                "updated_at": time.time(),
                "trades": [],
                "filled_volume": 0,
                "filled_price": 0.0,
                "commission": 0.0,
                "slippage": 0.0,
            }
            self.order_to_vt[order_id] = vt_orderid
            self.vt_to_order[vt_orderid] = order_id

        logger.info(f"Tracking order: {order_id} -> {vt_orderid}")

    def _on_order_event(self, event: Event):
        try:
            order = event.data
            vt_orderid = getattr(order, "vt_orderid", None) or getattr(order, "orderid", None)

            if not vt_orderid:
                return

            order_id = self.vt_to_order.get(vt_orderid)
            if not order_id:
                logger.debug(f"Unknown order event: {vt_orderid}")
                return

            with self._lock:
                if order_id not in self.active_orders:
                    return

                tracked = self.active_orders[order_id]
                status = getattr(order, "status", None)
                if hasattr(status, 'value'):
                    status = status.value

                tracked["status"] = status
                tracked["updated_at"] = time.time()

                if getattr(order, "msg", None):
                    tracked["message"] = order.msg

                if status in ["allTraded", "fully_filled", "filled"]:
                    tracked["status"] = "filled"
                    self._complete_order(order_id)

                elif status in ["cancelled", "canceled", "rejected", "error"]:
                    tracked["status"] = status
                    self._complete_order(order_id)

                elif status in ["partTradedNotQueueing", "partially_filled"]:
                    tracked["filled_volume"] = getattr(order, "traded", 0)
                    tracked["filled_price"] = getattr(order, "price", 0)

            logger.info(f"Order update: {order_id} status={status}")

            if order_id in self.order_callbacks:
                self.order_callbacks[order_id](tracked)

        except Exception as e:
            logger.error(f"Error processing order event: {e}")

    def _on_trade_event(self, event: Event):
        try:
            trade = event.data
            vt_orderid = getattr(trade, "vt_orderid", None) or getattr(trade, "orderid", None)

            if not vt_orderid:
                return

            order_id = self.vt_to_order.get(vt_orderid)
            if not order_id:
                logger.debug(f"Unknown trade event for order: {vt_orderid}")
                return

            with self._lock:
                if order_id not in self.active_orders:
                    return

                tracked = self.active_orders[order_id]
                trade_record = {
                    "tradeid": getattr(trade, "tradeid", ""),
                    "price": getattr(trade, "price", 0),
                    "volume": getattr(trade, "volume", 0),
                    "direction": getattr(trade, "direction", ""),
                    "offset": getattr(trade, "offset", ""),
                    "datetime": getattr(trade, "datetime", datetime.now()),
                    "commission": getattr(trade, "commission", 0),
                }

                tracked["trades"].append(trade_record)
                tracked["filled_volume"] += trade_record["volume"]
                tracked["commission"] += trade_record["commission"]

                if tracked["filled_volume"] > 0:
                    total_cost = sum(t["price"] * t["volume"] for t in tracked["trades"])
                    tracked["filled_price"] = total_cost / tracked["filled_volume"]

                tracked["updated_at"] = time.time()

            logger.info(
                f"Trade fill: {order_id} price={trade_record['price']} "
                f"volume={trade_record['volume']}"
            )

            if order_id in self.order_callbacks:
                self.order_callbacks[order_id](tracked)

        except Exception as e:
            logger.error(f"Error processing trade event: {e}")

    def _on_log_event(self, event: Event):
        try:
            log = event.data
            msg = getattr(log, "msg", "")
            if "order" in msg.lower() and ("reject" in msg.lower() or "error" in msg.lower()):
                logger.warning(f"Order-related log: {msg}")
        except Exception as e:
            logger.error(f"Error processing log event: {e}")

    def _complete_order(self, order_id: str):
        if order_id in self.active_orders:
            order = self.active_orders.pop(order_id)
            self.completed_orders[order_id] = order
            logger.info(
                f"Order completed: {order_id} status={order['status']} "
                f"filled={order['filled_volume']}/{order['volume']}"
            )

    def register_callback(self, order_id: str, callback: Callable):
        self.order_callbacks[order_id] = callback

    def get_order_status(self, order_id: str) -> Optional[Dict[str, Any]]:
        if order_id in self.active_orders:
            return self.active_orders[order_id].copy()
        if order_id in self.completed_orders:
            return self.completed_orders[order_id].copy()
        return None

    def get_active_orders(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: v.copy() for k, v in self.active_orders.items()}

    def get_completed_orders(self, limit: int = 50) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            items = list(self.completed_orders.items())[-limit:]
            return dict(items)

    def cancel_order(self, order_id: str, cancel_func: Callable):
        order = self.get_order_status(order_id)
        if not order:
            logger.warning(f"Cannot cancel unknown order: {order_id}")
            return False

        if order["status"] not in ["submitted", "partially_filled", "not_traded"]:
            logger.warning(f"Cannot cancel order in status: {order['status']}")
            return False

        try:
            vt_orderid = order.get("vt_orderid")
            if vt_orderid:
                cancel_func(vt_orderid)
                logger.info(f"Cancel requested for order: {order_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
        return False

    def get_execution_summary(self) -> Dict[str, Any]:
        with self._lock:
            total_submitted = len(self.completed_orders) + len(self.active_orders)
            total_filled = sum(
                1 for o in self.completed_orders.values() if o["status"] == "filled"
            )
            total_rejected = sum(
                1 for o in self.completed_orders.values() if o["status"] == "rejected"
            )
            total_cancelled = sum(
                1 for o in self.completed_orders.values() if o["status"] in ["cancelled", "canceled"]
            )
            total_commission = sum(o.get("commission", 0) for o in self.completed_orders.values())

            return {
                "total_orders": total_submitted,
                "active_orders": len(self.active_orders),
                "filled": total_filled,
                "rejected": total_rejected,
                "cancelled": total_cancelled,
                "fill_rate": total_filled / max(total_submitted, 1),
                "total_commission": total_commission,
            }

    def _persist_order(self, order_id: str, order_data: Dict[str, Any]):
        try:
            filepath = self._persistence_dir / f"{order_id}.json"
            with open(filepath, "w") as f:
                json.dump(order_data, f, default=str)
        except Exception as e:
            logger.error(f"Failed to persist order {order_id}: {e}")

    def _load_from_disk(self):
        try:
            for filepath in self._persistence_dir.glob("*.json"):
                try:
                    with open(filepath) as f:
                        order_data = json.load(f)
                    order_id = order_data.get("order_id")
                    status = order_data.get("status")
                    if status in ["submitted", "partially_filled", "not_traded"]:
                        self.active_orders[order_id] = order_data
                        logger.warning(f"Loaded in-flight order from disk: {order_id}")
                    else:
                        self.completed_orders[order_id] = order_data
                except Exception as e:
                    logger.error(f"Failed to load order from {filepath}: {e}")
            if self.active_orders:
                logger.warning(f"Recovered {len(self.active_orders)} in-flight orders from disk")
        except Exception as e:
            logger.error(f"Failed to load orders from disk: {e}")

    def flush_to_disk(self):
        with self._lock:
            for order_id, order_data in {**self.active_orders, **self.completed_orders}.items():
                self._persist_order(order_id, order_data)
        logger.info(f"Flushed {len(self.active_orders) + len(self.completed_orders)} orders to disk")


order_tracker = OrderTracker()
