#!/usr/bin/env python3
"""
Backpressure Alert Handler
Sends Telegram alerts when queues reach critical thresholds
"""

import os
import sys
import logging
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

try:
    from telegram_notify import send_alert, send_to_admin
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] Telegram notifications not available")

logger = logging.getLogger('BackpressureAlerts')


class BackpressureAlertHandler:
    """
    Handles backpressure alerts and notifications.
    Sends Telegram messages when queues reach critical thresholds.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.alert_cooldown = 60
        self._last_alert_time: Dict[str, float] = {}
        self._alert_count = 0
        self._alert_history = []
        self._enabled = True
        
        self._initialized = True
        
    def handle_alert(self, bp_result: Dict[str, Any]) -> None:
        """Handle a backpressure alert"""
        if not self._enabled:
            return
            
        stream = bp_result.get('stream', 'unknown')
        status = bp_result.get('status', 'unknown')
        percent = bp_result.get('percent', 0)
        action = bp_result.get('action', 'none')
        current_length = bp_result.get('current_length', 0)
        max_length = bp_result.get('max_length', 10000)
        
        if not self._should_alert(stream):
            return
            
        self._last_alert_time[stream] = time.time()
        self._alert_count += 1
        
        alert_entry = {
            'timestamp': datetime.now().isoformat(),
            'stream': stream,
            'status': status,
            'percent': percent,
            'action': action,
            'current_length': current_length,
            'max_length': max_length
        }
        
        self._alert_history.append(alert_entry)
        
        if len(self._alert_history) > 100:
            self._alert_history = self._alert_history[-100:]
        
        message = self._format_alert_message(alert_entry)
        
        if status == 'critical':
            level = 'CRITICAL'
            logger.critical(f"BACKPRESSURE ALERT: {message}")
        else:
            level = 'WARNING'
            logger.warning(f"BACKPRESSURE WARNING: {message}")
        
        if TELEGRAM_AVAILABLE:
            try:
                send_alert(
                    component_name=f"Backpressure:{stream}",
                    level=level,
                    message=message,
                    details=f"Action: {action}, Queue: {current_length}/{max_length}"
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
    
    def _should_alert(self, stream: str) -> bool:
        """Check if we should alert (cooldown)"""
        last_time = self._last_alert_time.get(stream, 0)
        return (time.time() - last_time) >= self.alert_cooldown
    
    def _format_alert_message(self, alert: Dict) -> str:
        """Format alert message"""
        status_emoji = {
            'warning': '⚠️',
            'critical': '🚨'
        }
        
        emoji = status_emoji.get(alert['status'], '•')
        
        return (
            f"{emoji} Stream `{alert['stream']}` at "
            f"{alert['percent']:.1f}% capacity "
            f"({alert['current_length']}/{alert['max_length']})"
        )
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get summary of recent alerts"""
        return {
            'total_alerts': self._alert_count,
            'recent_alerts': self._alert_history[-10:],
            'enabled': self._enabled
        }
    
    def enable(self):
        """Enable alerts"""
        self._enabled = True
        logger.info("Backpressure alerts enabled")
    
    def disable(self):
        """Disable alerts"""
        self._enabled = False
        logger.info("Backpressure alerts disabled")


def get_alert_handler() -> BackpressureAlertHandler:
    """Get singleton instance"""
    return BackpressureAlertHandler()


def default_backpressure_callback(bp_result: Dict[str, Any]):
    """Default callback for backpressure alerts"""
    handler = get_alert_handler()
    handler.handle_alert(bp_result)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    handler = BackpressureAlertHandler()
    
    test_result = {
        'stream': 'market_data',
        'status': 'critical',
        'percent': 96.5,
        'action': 'drop_oldest',
        'current_length': 9650,
        'max_length': 10000
    }
    
    handler.handle_alert(test_result)
    
    print(f"Alert summary: {handler.get_alert_summary()}")
