"""
Layer 6: Integrated Self-Healing Manager
Connects HealthMonitor alerts to SelfAwarenessEngine healing actions.
"""

import time
from typing import Dict, Any, Optional, Callable
from loguru import logger

from ..event_bus import get_event_bus, EventType, publish_healing_action


class IntegratedHealingManager:
    """
    Bridges HealthMonitor alerts with healing actions.
    Maintains a registry of component health checks and restart functions.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        self.max_restarts = self.config.get('max_restarts', 3)
        
        # Component registry: name -> {check_func, restart_func, critical}
        self.components: Dict[str, Dict[str, Any]] = {}
        
        # Healing effectiveness tracker
        self.healing_stats: Dict[str, Dict[str, Any]] = {}
        
        # Subscribe to health alerts
        self.event_bus = get_event_bus()
        self.event_bus.subscribe(
            [EventType.HEALTH_ALERT],
            self._on_health_alert
        )
        
        logger.info("IntegratedHealingManager initialized")
    
    def register_component(self, name: str, check_func: Callable, 
                          restart_func: Callable, critical: bool = False):
        """Register a component for integrated healing."""
        self.components[name] = {
            'check_func': check_func,
            'restart_func': restart_func,
            'critical': critical,
            'last_health_check': None,
            'consecutive_failures': 0,
            'total_failures': 0,
            'total_restarts': 0,
            'successful_restarts': 0
        }
        
        self.healing_stats[name] = {
            'total_failures': 0,
            'healing_attempts': 0,
            'successful_healings': 0,
            'avg_recovery_time_ms': 0,
            'last_healing_action': None
        }
        
        logger.info(f"Registered for integrated healing: {name} (critical: {critical})")
    
    def _on_health_alert(self, event):
        """Handle health alert from event bus."""
        if not self.enabled:
            return
        
        component = getattr(event, 'component', '')
        status = getattr(event, 'status', '')
        failure_count = getattr(event, 'failure_count', 0)
        critical = getattr(event, 'critical', False)
        
        logger.warning(f"Integrated healing received alert: {component} - {status} "
                      f"(failures: {failure_count}, critical: {critical})")
        
        if component in self.components:
            self._handle_component_failure(component, failure_count, critical)
    
    def _handle_component_failure(self, component_name: str, 
                                   failure_count: int, critical: bool):
        """Handle component failure with intelligent healing."""
        comp = self.components[component_name]
        stats = self.healing_stats[component_name]
        
        comp['consecutive_failures'] = failure_count
        comp['total_failures'] += 1
        stats['total_failures'] += 1
        
        # Check max restarts
        if comp['total_restarts'] >= self.max_restarts:
            logger.error(f"Max restarts ({self.max_restarts}) reached for {component_name}")
            return
        
        # Determine healing action based on failure pattern
        healing_action = self._select_healing_action(component_name, failure_count, critical)
        
        if healing_action:
            self._execute_healing(component_name, healing_action)
    
    def _select_healing_action(self, component_name: str, 
                                failure_count: int, critical: bool) -> Optional[str]:
        """Select appropriate healing action based on failure pattern."""
        # First failure: simple restart
        if failure_count == 1:
            return 'restart'
        
        # Multiple failures: more aggressive
        if failure_count <= 3:
            return 'restart_with_reset'
        
        # Many failures: escalate
        if failure_count > 3 and critical:
            return 'escalate'
        
        return None
    
    def _execute_healing(self, component_name: str, action: str):
        """Execute healing action and track effectiveness."""
        comp = self.components[component_name]
        stats = self.healing_stats[component_name]
        
        start_time = time.time()
        success = False
        
        try:
            if action == 'restart':
                comp['restart_func']()
                success = True
            elif action == 'restart_with_reset':
                # Reset error count then restart
                comp['consecutive_failures'] = 0
                comp['restart_func']()
                success = True
            elif action == 'escalate':
                # For critical components with many failures
                comp['restart_func']()
                success = True
            
            comp['total_restarts'] += 1
            if success:
                comp['successful_restarts'] += 1
            
        except Exception as e:
            logger.error(f"Healing failed for {component_name}: {e}")
            success = False
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Track healing statistics
        stats['healing_attempts'] += 1
        if success:
            stats['successful_healings'] += 1
        stats['last_healing_action'] = {
            'action': action,
            'timestamp': time.time(),
            'success': success,
            'duration_ms': duration_ms
        }
        
        # Update average recovery time
        if success and stats['successful_healings'] > 0:
            total_time = stats.get('avg_recovery_time_ms', 0) * (stats['successful_healings'] - 1)
            stats['avg_recovery_time_ms'] = (total_time + duration_ms) / stats['successful_healings']
        
        # Publish healing event
        publish_healing_action(
            action=action,
            layer_id=component_name,
            reason=f"Health alert: {comp['consecutive_failures']} consecutive failures",
            success=success,
            duration_ms=duration_ms
        )
        
        logger.info(f"Healing action '{action}' for {component_name}: "
                   f"success={success}, duration={duration_ms:.1f}ms")
    
    def check_and_heal(self, component_name: str) -> bool:
        """Manually check and heal a component."""
        if component_name not in self.components:
            return False
        
        comp = self.components[component_name]
        
        try:
            is_healthy = comp['check_func']()
            
            if not is_healthy:
                self._execute_healing(component_name, 'restart')
                return True
            
            # Reset failure count if healthy
            comp['consecutive_failures'] = 0
            return True
            
        except Exception as e:
            logger.error(f"Check failed for {component_name}: {e}")
            self._execute_healing(component_name, 'restart')
            return False
    
    def get_healing_report(self) -> Dict[str, Any]:
        """Get comprehensive healing effectiveness report."""
        component_reports = {}
        
        for name, comp in self.components.items():
            stats = self.healing_stats[name]
            success_rate = (stats['successful_healings'] / max(stats['healing_attempts'], 1)) * 100
            
            component_reports[name] = {
                'critical': comp['critical'],
                'total_failures': comp['total_failures'],
                'total_restarts': comp['total_restarts'],
                'success_rate': round(success_rate, 1),
                'consecutive_failures': comp['consecutive_failures'],
                'avg_recovery_time_ms': round(stats['avg_recovery_time_ms'], 1),
                'last_healing': stats['last_healing_action']
            }
        
        return {
            'enabled': self.enabled,
            'components': component_reports,
            'total_failures': sum(s['total_failures'] for s in self.healing_stats.values()),
            'total_healings': sum(s['healing_attempts'] for s in self.healing_stats.values()),
            'overall_success_rate': self._calculate_overall_success_rate()
        }
    
    def _calculate_overall_success_rate(self) -> float:
        """Calculate overall healing success rate."""
        total_attempts = sum(s['healing_attempts'] for s in self.healing_stats.values())
        total_success = sum(s['successful_healings'] for s in self.healing_stats.values())
        
        if total_attempts == 0:
            return 0.0
        return round((total_success / total_attempts) * 100, 1)


# Singleton instance
_integrated_healing_manager: Optional[IntegratedHealingManager] = None


def get_integrated_healing_manager(config: Dict[str, Any] = None) -> IntegratedHealingManager:
    """Get singleton integrated healing manager."""
    global _integrated_healing_manager
    if _integrated_healing_manager is None:
        _integrated_healing_manager = IntegratedHealingManager(config)
    return _integrated_healing_manager


def reset_integrated_healing_manager():
    """Reset the integrated healing manager instance."""
    global _integrated_healing_manager
    _integrated_healing_manager = None
