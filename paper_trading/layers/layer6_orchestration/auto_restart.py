"""
Layer 6: Auto-Restart
Self-healing: automatic restart on component failures.
"""

import time
import threading
from typing import Dict, Any, Optional, Callable
from datetime import datetime
from loguru import logger


class AutoRestart:
    """Auto-restart functionality for failed components."""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('auto_restart', True)
        self.restart_delay = config.get('restart_delay', 10)
        self.max_restarts = config.get('max_restarts', 3)
        
        self.restart_history: list = []
        
        self.component_managers: Dict[str, Callable] = {}
        self.restart_counts: Dict[str, int] = {}
    
    def register_component(self, name: str, restart_func: Callable, 
                          check_func: Callable = None):
        """Register a component for auto-restart."""
        self.component_managers[name] = {
            'restart_func': restart_func,
            'check_func': check_func or (lambda: True),
            'last_restart': None,
            'restart_count': 0
        }
        
        self.restart_counts[name] = 0
        
        logger.info(f"Registered for auto-restart: {name}")
    
    def handle_failure(self, component_name: str) -> bool:
        """Handle component failure and attempt restart."""
        if not self.enabled:
            logger.warning(f"Auto-restart disabled, not restarting {component_name}")
            return False
        
        if component_name not in self.component_managers:
            logger.warning(f"Component {component_name} not registered for auto-restart")
            return False
        
        manager = self.component_managers[component_name]
        
        if self.restart_counts[component_name] >= self.max_restarts:
            logger.error(f"Max restarts reached for {component_name}, not restarting")
            return False
        
        logger.info(f"Attempting auto-restart for {component_name}")
        
        time.sleep(self.restart_delay)
        
        try:
            restart_func = manager['restart_func']
            restart_func()
            
            manager['last_restart'] = time.time()
            manager['restart_count'] += 1
            self.restart_counts[component_name] += 1
            
            self.restart_history.append({
                'component': component_name,
                'timestamp': datetime.now().isoformat(),
                'restart_number': self.restart_counts[component_name]
            })
            
            logger.info(f"Restarted {component_name} successfully")
            
            if len(self.restart_history) > 100:
                self.restart_history = self.restart_history[-100:]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart {component_name}: {e}")
            return False
    
    def reset_restart_count(self, component_name: str):
        """Reset restart count for component."""
        if component_name in self.restart_counts:
            self.restart_counts[component_name] = 0
            logger.info(f"Reset restart count for {component_name}")
    
    def get_restart_status(self, component_name: str) -> Dict[str, Any]:
        """Get restart status for component."""
        if component_name not in self.component_managers:
            return {'registered': False}
        
        manager = self.component_managers[component_name]
        
        return {
            'registered': True,
            'restart_count': self.restart_counts[component_name],
            'max_restarts': self.max_restarts,
            'last_restart': manager['last_restart']
        }
    
    def get_history(self, limit: int = 10) -> list:
        """Get recent restart history."""
        return self.restart_history[-limit:]


class SelfHealingManager:
    """Manages self-healing across all components."""
    
    def __init__(self, config: Dict[str, Any]):
        self.auto_restart = AutoRestart(config)
        
        self.health_callbacks: Dict[str, Callable] = {}
    
    def register_for_healing(self, component_name: str, 
                           restart_func: Callable,
                           check_func: Callable = None,
                           health_callback: Callable = None):
        """Register component for self-healing."""
        self.auto_restart.register_component(
            component_name, restart_func, check_func
        )
        
        if health_callback:
            self.health_callbacks[component_name] = health_callback
    
    def on_health_alert(self, alert: Dict[str, Any]):
        """Handle health alert and trigger healing."""
        component_name = alert.get('component')
        
        if not component_name:
            return
        
        if alert.get('critical'):
            logger.critical(f"Critical failure detected: {component_name}")
            
            if component_name in self.health_callbacks:
                callback = self.health_callbacks[component_name]
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Health callback error: {e}")
            
            success = self.auto_restart.handle_failure(component_name)
            
            if not success and self.auto_restart.enabled:
                logger.error(f"Self-healing failed for {component_name}")
    
    def check_and_heal(self, component_name: str) -> bool:
        """Manually check and heal component."""
        if component_name not in self.auto_restart.component_managers:
            return False
        
        manager = self.auto_restart.component_managers[component_name]
        
        try:
            is_healthy = manager['check_func']()
            
            if not is_healthy:
                return self.auto_restart.handle_failure(component_name)
            
            self.auto_restart.reset_restart_count(component_name)
            
            return True
            
        except Exception as e:
            logger.error(f"Check failed for {component_name}: {e}")
            return self.auto_restart.handle_failure(component_name)
    
    def get_status(self) -> Dict[str, Any]:
        """Get self-healing status."""
        component_status = {}
        
        for name in self.auto_restart.component_managers:
            component_status[name] = self.auto_restart.get_restart_status(name)
        
        return {
            'enabled': self.auto_restart.enabled,
            'max_restarts': self.auto_restart.max_restarts,
            'components': component_status,
            'recent_restarts': self.auto_restart.get_history(5)
        }


auto_restart = AutoRestart({'auto_restart': True, 'restart_delay': 10, 'max_restarts': 3})


def auto_restart_component(name: str, restart_func: Callable) -> bool:
    """Convenience function to register and trigger auto-restart."""
    auto_restart.register_component(name, restart_func)
    return auto_restart.handle_failure(name)
