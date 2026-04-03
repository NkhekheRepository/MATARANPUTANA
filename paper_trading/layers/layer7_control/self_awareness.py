"""
Layer 7: Command & Control
==========================
Self-aware command and control layer with health monitoring,
auto-healing capabilities, and system introspection.
"""

import os
import time
import threading
import json
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from loguru import logger

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from paper_trading.layers.event_bus import (
    get_event_bus, EventType, BaseEvent,
    publish_health_check, publish_command_received
)


class SystemStatus(Enum):
    """Overall system status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    EMERGENCY = "emergency"


class HealingAction(Enum):
    """Auto-healing actions that can be triggered."""
    RESTART_LAYER = "restart_layer"
    RELOAD_CONFIG = "reload_config"
    RETRAIN_MODEL = "retrain_model"
    RESET_CIRCUIT_BREAKER = "reset_circuit_breaker"
    SWITCH_STRATEGY = "switch_strategy"
    REDUCE_POSITIONS = "reduce_positions"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class LayerHealth:
    """Health status of a layer."""
    layer_id: str
    layer_name: str
    status: SystemStatus
    last_check: float
    error_count: int = 0
    warning_count: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


@dataclass
class HealingActionRecord:
    """Record of a healing action taken."""
    action: HealingAction
    layer_id: str
    timestamp: float
    reason: str
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)


class SelfAwarenessEngine:
    """
    Self-awareness engine that monitors system health and triggers healing.
    Provides introspection and adaptive behavior.
    """
    
    def __init__(self, config: Dict[str, Any] = None, engine_ref=None):
        self.config = config or {}
        self.engine_ref = engine_ref
        
        # Health monitoring configuration
        self.health_check_interval = self.config.get('health_check_interval', 30)
        self.max_errors_before_action = self.config.get('max_errors_before_action', 5)
        self.max_warnings_before_degraded = self.config.get('max_warnings_before_degraded', 10)
        
        # Model retraining configuration
        self.model_retrain_interval = self.config.get('model_retrain_interval', 3600)  # 1 hour
        self.min_trades_for_retrain = self.config.get('min_trades_for_retrain', 50)
        self.model_decay_threshold = self.config.get('model_decay_threshold', 0.15)  # 15% decay
        
        # Circuit breaker configuration
        self.circuit_breaker_cooldown = self.config.get('circuit_breaker_cooldown', 300)  # 5 minutes
        
        # State
        self.system_status = SystemStatus.HEALTHY
        self.layer_health: Dict[str, LayerHealth] = {}
        self.healing_history: List[HealingActionRecord] = []
        self.last_health_check = 0
        self.last_model_retrain = time.time()
        
        # Model performance tracking
        self.model_performance_history: List[Dict[str, Any]] = []
        self.trade_count_since_retrain = 0
        
        # Circuit breaker states
        self.circuit_breakers: Dict[str, Dict[str, Any]] = {}
        
        # Thread control
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        # Use the singleton event bus — shared with engine
        self.event_bus = get_event_bus()
        
        # Initialize layer health tracking
        self._init_layer_health()
        
        logger.info("SelfAwarenessEngine initialized")
    
    def _init_layer_health(self):
        """Initialize health tracking for all layers."""
        layers = [
            ("layer1", "Data & Connectivity"),
            ("layer2", "Risk Management"),
            ("layer3", "Signal Generation"),
            ("layer4", "Intelligence"),
            ("layer5", "Execution"),
            ("layer6", "Orchestration"),
            ("layer7", "Command & Control"),
        ]
        
        for layer_id, layer_name in layers:
            self.layer_health[layer_id] = LayerHealth(
                layer_id=layer_id,
                layer_name=layer_name,
                status=SystemStatus.HEALTHY,
                last_check=time.time()
            )
    
    def start(self):
        """Start the self-awareness engine."""
        if self._running:
            logger.warning("SelfAwarenessEngine already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info("SelfAwarenessEngine started")
    
    def stop(self):
        """Stop the self-awareness engine."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        
        logger.info("SelfAwarenessEngine stopped")
    
    def _monitoring_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                self._perform_health_check()
                self._check_model_performance()
                self._check_circuit_breakers()
                self._update_system_status()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
            
            time.sleep(self.health_check_interval)
    
    def _perform_health_check(self):
        """Perform health check on all layers."""
        self.last_health_check = time.time()
        
        for layer_id, health in self.layer_health.items():
            try:
                # Simulate health check (in real implementation, would call layer health endpoint)
                health.last_check = time.time()
                
                # Update health check event
                publish_health_check(
                    component=layer_id,
                    status=health.status.value,
                    checks={
                        "error_count": str(health.error_count),
                        "warning_count": str(health.warning_count)
                    }
                )
                
            except Exception as e:
                logger.error(f"Health check failed for {layer_id}: {e}")
                self._record_layer_error(layer_id, f"Health check failed: {e}")
    
    def _check_model_performance(self):
        """Check model performance and trigger retraining if needed."""
        if time.time() - self.last_model_retrain > self.model_retrain_interval:
            logger.info("Model retrain interval reached")
            self._trigger_healing(HealingAction.RETRAIN_MODEL, "system", "Scheduled retrain interval")
        
        if self.trade_count_since_retrain >= self.min_trades_for_retrain:
            # Check for performance decay
            if self._detect_model_decay():
                logger.warning("Model performance decay detected")
                self._trigger_healing(HealingAction.RETRAIN_MODEL, "layer4", "Performance decay detected")
    
    def _detect_model_decay(self) -> bool:
        """Detect if model performance has degraded significantly."""
        if len(self.model_performance_history) < 10:
            return False
        
        # Calculate average performance over recent window
        recent = self.model_performance_history[-10:]
        historical = self.model_performance_history[:-10] if len(self.model_performance_history) > 10 else []
        
        if not historical:
            return False
        
        recent_avg = sum(p.get('win_rate', 0.5) for p in recent) / len(recent)
        historical_avg = sum(p.get('win_rate', 0.5) for p in historical) / len(historical)
        
        decay = historical_avg - recent_avg
        return decay > self.model_decay_threshold
    
    def _check_circuit_breakers(self):
        """Check and reset circuit breakers after cooldown."""
        current_time = time.time()
        
        for cb_id, cb_state in list(self.circuit_breakers.items()):
            if cb_state.get('tripped', False):
                tripped_at = cb_state.get('tripped_at', 0)
                if current_time - tripped_at > self.circuit_breaker_cooldown:
                    # Reset circuit breaker
                    self.circuit_breakers[cb_id] = {'tripped': False, 'tripped_at': 0}
                    logger.info(f"Circuit breaker {cb_id} reset after cooldown")
    
    def _update_system_status(self):
        """Update overall system status based on layer health."""
        layer_statuses = [h.status for h in self.layer_health.values()]
        
        if any(s == SystemStatus.EMERGENCY for s in layer_statuses):
            self.system_status = SystemStatus.EMERGENCY
        elif any(s == SystemStatus.UNHEALTHY for s in layer_statuses):
            self.system_status = SystemStatus.UNHEALTHY
        elif any(s == SystemStatus.RECOVERING for s in layer_statuses):
            self.system_status = SystemStatus.RECOVERING
        elif any(s == SystemStatus.DEGRADED for s in layer_statuses):
            self.system_status = SystemStatus.DEGRADED
        else:
            self.system_status = SystemStatus.HEALTHY
    
    def _record_layer_error(self, layer_id: str, error_message: str):
        """Record an error for a layer and potentially trigger healing."""
        if layer_id not in self.layer_health:
            return
        
        health = self.layer_health[layer_id]
        health.error_count += 1
        health.issues.append(error_message)
        
        # Keep only last 100 issues
        if len(health.issues) > 100:
            health.issues = health.issues[-100:]
        
        logger.warning(f"Layer {layer_id} error #{health.error_count}: {error_message}")
        
        # Check if we need to trigger healing
        if health.error_count >= self.max_errors_before_action:
            self._trigger_healing(
                HealingAction.RESTART_LAYER,
                layer_id,
                f"Too many errors: {health.error_count}"
            )
    
    def _record_layer_warning(self, layer_id: str, warning_message: str):
        """Record a warning for a layer."""
        if layer_id not in self.layer_health:
            return
        
        health = self.layer_health[layer_id]
        health.warning_count += 1
        health.issues.append(f"WARNING: {warning_message}")
        
        # Update layer status based on warnings
        if health.warning_count >= self.max_warnings_before_degraded:
            health.status = SystemStatus.DEGRADED
    
    def _trigger_healing(self, action: HealingAction, layer_id: str, reason: str):
        """Trigger a healing action."""
        logger.warning(f"Triggering healing action: {action.value} for {layer_id}: {reason}")
        
        success = False
        details = {}
        
        try:
            if action == HealingAction.RESTART_LAYER:
                success = self._healing_restart_layer(layer_id)
            elif action == HealingAction.RELOAD_CONFIG:
                success = self._healing_reload_config()
            elif action == HealingAction.RETRAIN_MODEL:
                success = self._healing_retrain_model(layer_id)
            elif action == HealingAction.RESET_CIRCUIT_BREAKER:
                success = self._healing_reset_circuit_breaker(layer_id)
            elif action == HealingAction.SWITCH_STRATEGY:
                success = self._healing_switch_strategy()
            elif action == HealingAction.REDUCE_POSITIONS:
                success = self._healing_reduce_positions()
            elif action == HealingAction.EMERGENCY_STOP:
                success = self._healing_emergency_stop(layer_id)
        except Exception as e:
            logger.error(f"Healing action failed: {e}")
            details["error"] = str(e)
        
        # Record healing action
        record = HealingActionRecord(
            action=action,
            layer_id=layer_id,
            timestamp=time.time(),
            reason=reason,
            success=success,
            details=details
        )
        self.healing_history.append(record)
        
        # Keep only last 1000 healing records
        if len(self.healing_history) > 1000:
            self.healing_history = self.healing_history[-1000:]
        
        return success
    
    def _healing_restart_layer(self, layer_id: str) -> bool:
        """Healing action: Restart a layer."""
        logger.info(f"Healing: Restarting layer {layer_id}")
        if layer_id in self.layer_health:
            self.layer_health[layer_id].error_count = 0
            self.layer_health[layer_id].status = SystemStatus.RECOVERING
        
        if self.engine_ref:
            if layer_id == 'layer1':
                try:
                    self.engine_ref.data_bridge.disconnect()
                    self.engine_ref.data_bridge.connect()
                    logger.info("Healing: Layer 1 (data) reconnected")
                except Exception as e:
                    logger.error(f"Healing: Layer 1 reconnect failed: {e}")
                    return False
            elif layer_id == 'layer4':
                try:
                    self.engine_ref.intelligence.hmm.model_trained = False
                    self.engine_ref.intelligence.hmm._last_train_bar = 0
                    logger.info("Healing: Layer 4 (intelligence) model reset for retrain")
                except Exception as e:
                    logger.error(f"Healing: Layer 4 reset failed: {e}")
                    return False
        
        return True
    
    def _healing_reload_config(self) -> bool:
        """Healing action: Reload configuration."""
        logger.info("Healing: Reloading configuration")
        if self.engine_ref:
            try:
                self.engine_ref.config = self.engine_ref._load_config()
                logger.info("Healing: Configuration reloaded from disk")
                return True
            except Exception as e:
                logger.error(f"Healing: Config reload failed: {e}")
                return False
        return True
    
    def _healing_retrain_model(self, layer_id: str) -> bool:
        """Healing action: Retrain ML model."""
        logger.info(f"Healing: Triggering model retrain for {layer_id}")
        if self.engine_ref:
            try:
                prices = self.engine_ref.intelligence.hmm.price_history
                if len(prices) >= 100:
                    self.engine_ref.intelligence.hmm.train(prices)
                    logger.info("Healing: HMM model retrained")
                else:
                    logger.warning(f"Healing: Not enough data for retrain ({len(prices)} bars)")
            except Exception as e:
                logger.error(f"Healing: Model retrain failed: {e}")
                return False
        self.last_model_retrain = time.time()
        self.trade_count_since_retrain = 0
        return True
    
    def _healing_reset_circuit_breaker(self, layer_id: str) -> bool:
        """Healing action: Reset circuit breaker."""
        logger.info(f"Healing: Resetting circuit breaker for {layer_id}")
        self.circuit_breakers[layer_id] = {'tripped': False, 'tripped_at': 0}
        if layer_id in self.layer_health:
            self.layer_health[layer_id].status = SystemStatus.HEALTHY
        return True
    
    def _healing_switch_strategy(self) -> bool:
        """Healing action: Switch to fallback strategy."""
        logger.info("Healing: Switching to fallback strategy")
        if self.engine_ref:
            try:
                fallback = self.engine_ref.config.get('intelligence', {}).get('adaptive', {}).get('regime_strategy_map', {}).get('sideways')
                if fallback and fallback in self.engine_ref.strategies:
                    self.engine_ref.active_strategy = fallback
                    logger.info(f"Healing: Switched to fallback strategy: {fallback}")
                    return True
            except Exception as e:
                logger.error(f"Healing: Strategy switch failed: {e}")
                return False
        return True
    
    def _healing_reduce_positions(self) -> bool:
        """Healing action: Close all open positions."""
        logger.info("Healing: Closing all positions")
        if self.engine_ref:
            try:
                self.engine_ref._close_all_positions()
                logger.info("Healing: All positions closed")
                return True
            except Exception as e:
                logger.error(f"Healing: Position reduction failed: {e}")
                return False
        return True
    
    def _healing_emergency_stop(self, layer_id: str) -> bool:
        """Healing action: Emergency stop."""
        logger.critical(f"Healing: Emergency stop triggered by {layer_id}")
        self.system_status = SystemStatus.EMERGENCY
        if self.engine_ref:
            try:
                self.engine_ref.emergency_stop()
                logger.info("Healing: Engine emergency stop executed")
                return True
            except Exception as e:
                logger.error(f"Healing: Emergency stop failed: {e}")
                return False
        return True
    
    def record_trade(self, trade_data: Dict[str, Any]):
        """Record a trade for model performance tracking."""
        self.trade_count_since_retrain += 1
        self.model_performance_history.append({
            'timestamp': time.time(),
            'win_rate': trade_data.get('win_rate', 0.5),
            'pnl': trade_data.get('pnl', 0),
            'trade_count': self.trade_count_since_retrain
        })
        
        # Keep only last 1000 performance records
        if len(self.model_performance_history) > 1000:
            self.model_performance_history = self.model_performance_history[-1000:]
    
    def trip_circuit_breaker(self, layer_id: str, reason: str):
        """Trip a circuit breaker for a layer."""
        self.circuit_breakers[layer_id] = {
            'tripped': True,
            'tripped_at': time.time(),
            'reason': reason
        }
        
        if layer_id in self.layer_health:
            self.layer_health[layer_id].status = SystemStatus.UNHEALTHY
        
        logger.critical(f"Circuit breaker tripped for {layer_id}: {reason}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'system_status': self.system_status.value,
            'layers': {
                layer_id: {
                    'name': health.layer_name,
                    'status': health.status.value,
                    'error_count': health.error_count,
                    'warning_count': health.warning_count,
                    'last_check': health.last_check,
                    'issues': health.issues[-10:]  # Last 10 issues
                }
                for layer_id, health in self.layer_health.items()
            },
            'circuit_breakers': self.circuit_breakers,
            'healing_history': [
                {
                    'action': r.action.value,
                    'layer': r.layer_id,
                    'timestamp': r.timestamp,
                    'reason': r.reason,
                    'success': r.success
                }
                for r in self.healing_history[-20:]  # Last 20 healing actions
            ],
            'model_performance': {
                'trade_count_since_retrain': self.trade_count_since_retrain,
                'last_retrain': self.last_model_retrain,
                'performance_records': len(self.model_performance_history)
            },
            'last_health_check': self.last_health_check,
            'timestamp': time.time()
        }
    
    def get_introspection(self) -> Dict[str, Any]:
        """Get system introspection data."""
        return {
            'config': self.config,
            'health_check_interval': self.health_check_interval,
            'max_errors_before_action': self.max_errors_before_action,
            'model_retrain_interval': self.model_retrain_interval,
            'circuit_breaker_cooldown': self.circuit_breaker_cooldown,
            'total_healing_actions': len(self.healing_history),
            'total_model_records': len(self.model_performance_history),
            'uptime': time.time() - self.last_model_retrain
        }


# Singleton instance
_self_awareness_engine: Optional[SelfAwarenessEngine] = None


def get_self_awareness_engine(config: Dict[str, Any] = None) -> SelfAwarenessEngine:
    """Get singleton self-awareness engine instance."""
    global _self_awareness_engine
    if _self_awareness_engine is None:
        _self_awareness_engine = SelfAwarenessEngine(config)
    return _self_awareness_engine


def reset_self_awareness_engine():
    """Reset the self-awareness engine instance."""
    global _self_awareness_engine
    if _self_awareness_engine:
        _self_awareness_engine.stop()
    _self_awareness_engine = None


if __name__ == "__main__":
    # Test the self-awareness engine
    print("Testing SelfAwarenessEngine...")
    
    engine = SelfAwarenessEngine({
        'health_check_interval': 5,
        'max_errors_before_action': 3
    })
    
    engine.start()
    
    # Simulate some errors
    engine._record_layer_error("layer1", "Test error 1")
    engine._record_layer_error("layer1", "Test error 2")
    engine._record_layer_error("layer1", "Test error 3")
    
    # Get status
    status = engine.get_system_status()
    print(f"System status: {status['system_status']}")
    print(f"Layer 1 errors: {status['layers']['layer1']['error_count']}")
    
    # Get introspection
    introspection = engine.get_introspection()
    print(f"Total healing actions: {introspection['total_healing_actions']}")
    
    engine.stop()
    print("SelfAwarenessEngine test complete!")