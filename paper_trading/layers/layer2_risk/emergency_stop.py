"""
Layer 2: Emergency Stop
Kill switch for immediate trading halt.
Black Swan Resistant Execution Layer - Phase 1
"""

import time
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from loguru import logger


class EmergencyStop:
    """Emergency stop functionality for critical situations."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.enabled = True
        self.triggered = False
        self.triggered_at: Optional[float] = None
        self.trigger_reason: Optional[str] = None
        
        self.callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
        self.consecutive_losses = 0
        self.last_trade_pnl: Optional[float] = None
        self.last_metrics: Dict[str, Any] = {}
        self.metric_anomaly_count = 0
        self.data_gap_count = 0
        
        self.config = config or {}
        self.fail_safe_triggers = self.config.get('fail_safe_triggers', {
            'consecutive_losses': 10,  # Increased from 3 for model learning
            'metric_anomaly_threshold': 3,
            'data_gap_threshold': 3,
        })
    
    def trigger(self, reason: str = "Manual trigger"):
        """Trigger emergency stop."""
        with self._lock:
            if self.triggered:
                logger.warning("Emergency stop already triggered")
                return
            
            self.triggered = True
            self.triggered_at = time.time()
            self.trigger_reason = reason
            
            logger.critical(f"EMERGENCY STOP TRIGGERED: {reason}")
            
            self._execute_callbacks()
    
    def reset(self):
        """Reset emergency stop."""
        with self._lock:
            self.triggered = False
            self.triggered_at = None
            self.trigger_reason = None
            logger.info("Emergency stop reset")
    
    def is_triggered(self) -> bool:
        """Check if emergency stop is triggered."""
        return self.triggered
    
    def add_callback(self, callback: Callable):
        """Add callback to execute on emergency stop."""
        self.callbacks.append(callback)
    
    def _execute_callbacks(self):
        """Execute all registered callbacks."""
        for callback in self.callbacks:
            try:
                callback(self.trigger_reason)
            except Exception as e:
                logger.error(f"Error in emergency stop callback: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get emergency stop status."""
        return {
            'enabled': self.enabled,
            'triggered': self.triggered,
            'triggered_at': self.triggered_at,
            'reason': self.trigger_reason,
            'datetime': datetime.fromtimestamp(self.triggered_at).isoformat() if self.triggered_at else None,
            'consecutive_losses': self.consecutive_losses,
            'metric_anomaly_count': self.metric_anomaly_count,
            'data_gap_count': self.data_gap_count
        }
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 1 (Feature 10: Fail-Safe Mode)
    # =========================================================================
    
    def record_trade_pnl(self, pnl: float) -> bool:
        """
        Record trade PnL and check for consecutive loss trigger.
        Returns True if fail-safe should activate.
        """
        self.last_trade_pnl = pnl
        
        if pnl < 0:
            self.consecutive_losses += 1
            logger.warning(f"Consecutive loss: {self.consecutive_losses}")
            
            if self.consecutive_losses >= self.fail_safe_triggers['consecutive_losses']:
                self.trigger(f"Consecutive losses: {self.consecutive_losses}")
                return True
        else:
            if self.consecutive_losses > 0:
                logger.info(f"Consecutive losses reset (was {self.consecutive_losses})")
            self.consecutive_losses = 0
        
        return False
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        """
        Feature 10: Check for metric inconsistencies.
        Monitor: win rate, P&L, drawdown for anomalies.
        """
        if not metrics:
            return False
        
        expected_keys = ['win_rate', 'daily_pnl', 'drawdown']
        has_anomaly = False
        
        for key in expected_keys:
            if key not in metrics:
                continue
            
            current = metrics[key]
            previous = self.last_metrics.get(key)
            
            if previous is not None:
                if key == 'win_rate':
                    if abs(current - previous) > 30:
                        self.metric_anomaly_count += 1
                        has_anomaly = True
                        logger.warning(f"Win rate anomaly: {previous:.1f}% -> {current:.1f}%")
                
                elif key == 'daily_pnl':
                    if previous > 0 and current < -100:
                        self.metric_anomaly_count += 1
                        has_anomaly = True
                        logger.warning(f"PnL anomaly: ${previous:.2f} -> ${current:.2f}")
                
                elif key == 'drawdown':
                    if current > 15 and previous < 10:
                        self.metric_anomaly_count += 1
                        has_anomaly = True
                        logger.warning(f"Drawdown spike: {previous:.1f}% -> {current:.1f}%")
        
        self.last_metrics = metrics.copy()
        
        if has_anomaly and self.metric_anomaly_count >= self.fail_safe_triggers['metric_anomaly_threshold']:
            self.trigger(f"Metric anomalies detected: {self.metric_anomaly_count}")
            return True
        
        return False
    
    def check_data_feed(self, data_valid: bool) -> bool:
        """
        Feature 10: Check for data feed anomalies.
        Trigger if data gaps exceed threshold.
        """
        if not data_valid:
            self.data_gap_count += 1
            logger.warning(f"Data gap detected: {self.data_gap_count}")
            
            if self.data_gap_count >= self.fail_safe_triggers['data_gap_threshold']:
                self.trigger(f"Data feed failures: {self.data_gap_count}")
                return True
        else:
            if self.data_gap_count > 0:
                logger.info(f"Data gap count reset (was {self.data_gap_count})")
            self.data_gap_count = 0
        
        return False


class EmergencyStopManager:
    """Manages multiple emergency stop conditions."""
    
    def __init__(self):
        self.main_stop = EmergencyStop()
        self.risk_stop = EmergencyStop()
        self.data_stop = EmergencyStop()
        self.system_stop = EmergencyStop()
        
        self._setup_callbacks()
    
    def _setup_callbacks(self):
        """Setup default callbacks."""
        self.main_stop.add_callback(self._log_stop)
        self.risk_stop.add_callback(self._log_stop)
        self.data_stop.add_callback(self._log_stop)
        self.system_stop.add_callback(self._log_stop)
    
    def _log_stop(self, reason: str):
        """Log emergency stop."""
        logger.critical(f"Emergency stop activated: {reason}")
    
    def trigger_risk_stop(self, reason: str):
        """Trigger risk-based emergency stop."""
        self.risk_stop.trigger(reason)
    
    def trigger_data_stop(self, reason: str):
        """Trigger data-related emergency stop."""
        self.data_stop.trigger(reason)
    
    def trigger_system_stop(self, reason: str):
        """Trigger system-related emergency stop."""
        self.system_stop.trigger(reason)
    
    def is_any_triggered(self) -> bool:
        """Check if any emergency stop is triggered."""
        return any([
            self.main_stop.is_triggered(),
            self.risk_stop.is_triggered(),
            self.data_stop.is_triggered(),
            self.system_stop.is_triggered()
        ])
    
    def get_active_reason(self) -> Optional[str]:
        """Get the reason for active stop."""
        for stop, name in [
            (self.main_stop, "Manual"),
            (self.risk_stop, "Risk"),
            (self.data_stop, "Data"),
            (self.system_stop, "System")
        ]:
            if stop.is_triggered():
                return f"{name}: {stop.trigger_reason}"
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get all emergency stop statuses."""
        return {
            'any_triggered': self.is_any_triggered(),
            'active_reason': self.get_active_reason(),
            'main': self.main_stop.get_status(),
            'risk': self.risk_stop.get_status(),
            'data': self.data_stop.get_status(),
            'system': self.system_stop.get_status()
        }
    
    def reset_all(self):
        """Reset all emergency stops."""
        self.main_stop.reset()
        self.risk_stop.reset()
        self.data_stop.reset()
        self.system_stop.reset()
        logger.info("All emergency stops reset")


emergency_manager = EmergencyStopManager()


def trigger_emergency_stop(reason: str):
    """Convenience function to trigger emergency stop."""
    emergency_manager.main_stop.trigger(reason)


def is_emergency_stopped() -> bool:
    """Check if emergency stop is active."""
    return emergency_manager.is_any_triggered()
