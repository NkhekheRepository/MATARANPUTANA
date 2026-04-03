"""
Telegram Alert Handler
======================
Subscribes to risk and circuit-breaker events via the event bus
and dispatches Telegram notifications. Decouples alerting from the engine.
"""

from typing import Any, Dict
from loguru import logger

from ..event_bus import (
    get_event_bus,
    EventType,
    BaseEvent,
    RiskCheckEvent,
)

try:
    import telegram_notify
    _TELEGRAM_AVAILABLE = True
except ImportError:
    _TELEGRAM_AVAILABLE = False


class TelegramAlertHandler:
    """Listens for risk/circuit-breaker events and sends Telegram alerts."""

    def __init__(self):
        self._subscribed = False

    def subscribe(self) -> bool:
        """Subscribe to relevant event types on the singleton event bus."""
        if self._subscribed:
            return True
        try:
            bus = get_event_bus()
            bus.subscribe(
                [
                    EventType.RISK_LIMIT_BREACH,
                    EventType.CIRCUIT_BREAKER_TRIGGERED,
                    EventType.EMERGENCY_STOP_ACTIVATED,
                    EventType.ORDER_EXECUTED,
                ],
                self._on_event,
            )
            self._subscribed = True
            logger.info("TelegramAlertHandler subscribed to risk/circuit-breaker events")
            return True
        except Exception as e:
            logger.error(f"Failed to subscribe TelegramAlertHandler: {e}")
            return False

    def _on_event(self, event: BaseEvent) -> None:
        """Handle incoming events and dispatch Telegram messages."""
        if not _TELEGRAM_AVAILABLE:
            logger.warning("telegram_notify module not available, skipping alert")
            return

        event_type = event.event_type if hasattr(event, 'event_type') else None
        if event_type is None:
            return

        event_type_val = event_type.value if hasattr(event_type, 'value') else str(event_type)

        if event_type_val == EventType.RISK_LIMIT_BREACH.value:
            self._handle_risk_breach(event)
        elif event_type_val in (
            EventType.CIRCUIT_BREAKER_TRIGGERED.value,
            EventType.EMERGENCY_STOP_ACTIVATED.value,
        ):
            self._handle_circuit_breaker(event)
        elif event_type_val == EventType.ORDER_EXECUTED.value:
            self._handle_order_executed(event)

    def _handle_risk_breach(self, event: BaseEvent) -> None:
        """Format and send a risk-limit-breach alert."""
        risk_score = getattr(event, 'risk_score', 0)
        reason = getattr(event, 'reason', 'Unknown')
        capital = getattr(event, 'capital', 0)
        daily_pnl = getattr(event, 'daily_pnl', 0)

        level = "critical" if risk_score >= 80 else "high" if risk_score >= 60 else "medium"

        message = (
            f"RISK LIMIT BREACH\n"
            f"Score: {risk_score:.1f} | Level: {level.upper()}\n"
            f"Capital: ${capital:,.2f} | Daily PnL: ${daily_pnl:,.2f}\n"
            f"Reason: {reason}"
        )

        try:
            if _TELEGRAM_AVAILABLE:
                import telegram_notify as _tn
                _tn.send_risk_alert(
                    risk_score=risk_score,
                    risk_level=level,
                    message=message,
                )
                logger.info(f"Telegram risk alert sent: {level} (score={risk_score:.1f})")
            else:
                logger.info(f"[DRY-RUN] Telegram risk alert: {level} (score={risk_score:.1f})")
        except Exception as e:
            logger.error(f"Failed to send Telegram risk alert: {e}")

    def _handle_circuit_breaker(self, event: BaseEvent) -> None:
        """Format and send a circuit-breaker/emergency-stop alert."""
        component = getattr(event, 'component', 'Unknown')
        status = getattr(event, 'status', 'unknown')

        message = (
            f"CIRCUIT BREAKER TRIGGERED\n"
            f"Component: {component}\n"
            f"Status: {status}"
        )

        try:
            if _TELEGRAM_AVAILABLE:
                import telegram_notify as _tn2
                _tn2.send_alert(
                    component_name="Circuit Breaker",
                    level="CRITICAL",
                    message=message,
                )
                logger.info("Telegram circuit-breaker alert sent")
            else:
                logger.info("[DRY-RUN] Telegram circuit-breaker alert")
        except Exception as e:
            logger.error(f"Failed to send Telegram circuit-breaker alert: {e}")
    
    def _handle_order_executed(self, event: BaseEvent) -> None:
        """Send notification for executed trades."""
        try:
            symbol = getattr(event, 'symbol', 'UNKNOWN')
            action = getattr(event, 'action', 'UNKNOWN').upper()
            quantity = getattr(event, 'quantity', 0)
            price = getattr(event, 'price', 0)
            order_id = getattr(event, 'order_id', '')
            
            message = (
                f"TRADE EXECUTED\n"
                f"{action} {symbol}\n"
                f"Qty: {quantity} @ ${price:,.2f}\n"
                f"Order ID: {order_id}"
            )
            
            if _TELEGRAM_AVAILABLE:
                import telegram_notify as _tn3
                _tn3.send_alert(
                    component_name="Trading",
                    level="INFO",
                    message=message,
                )
                logger.info(f"Telegram trade alert sent: {action} {symbol}")
            else:
                logger.info(f"[DRY-RUN] Telegram trade alert: {action} {symbol} {quantity}")
        except Exception as e:
            logger.error(f"Failed to send Telegram trade alert: {e}")
