"""
Layer 6: Health Monitor
Self-healing: monitors system health and detects failures.
"""

import time
import threading
import psutil
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from loguru import logger


class HealthMonitor:
    """Monitors system and component health."""
    
    def __init__(self, config: Dict[str, Any]):
        self.check_interval = config.get('health_check_interval', 60)
        self.enabled = True
        
        self.running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.components: Dict[str, Dict[str, Any]] = {}
        
        self.alert_callbacks: List[Callable] = []
        
        self.start_time = time.time()
        self.check_count = 0
    
    def register_component(self, name: str, check_func: Callable, 
                         critical: bool = False):
        """Register a component to monitor."""
        self.components[name] = {
            'check_func': check_func,
            'critical': critical,
            'last_check': None,
            'last_status': 'unknown',
            'failure_count': 0
        }
        logger.info(f"Registered component: {name} (critical: {critical})")
    
    def start(self):
        """Start health monitoring."""
        if self.running:
            return
        
        self.running = True
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("Health monitor started")
    
    def stop(self):
        """Stop health monitoring."""
        self.running = False
        
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Health monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                self._perform_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            time.sleep(self.check_interval)
    
    def _perform_health_check(self):
        """Perform health check on all components."""
        self.check_count += 1
        
        system_health = self._check_system_resources()
        
        for name, component in self.components.items():
            try:
                check_func = component['check_func']
                result = check_func()
                
                component['last_check'] = time.time()
                
                if result is True:
                    component['last_status'] = 'healthy'
                    component['failure_count'] = 0
                else:
                    component['failure_count'] += 1
                    component['last_status'] = 'unhealthy'
                    
                    if component['failure_count'] >= 3:
                        self._trigger_alert(name, component)
                        
            except Exception as e:
                logger.error(f"Component {name} check error: {e}")
                component['failure_count'] += 1
                component['last_status'] = 'error'
    
    def _check_system_resources(self) -> Dict[str, Any]:
        """Check system resources."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            health = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': disk.percent
            }
            
            if cpu_percent > 90:
                logger.warning(f"High CPU usage: {cpu_percent}%")
            
            if memory.percent > 90:
                logger.warning(f"High memory usage: {memory.percent}%")
            
            return health
            
        except Exception as e:
            logger.error(f"System resource check error: {e}")
            return {}
    
    def _trigger_alert(self, component_name: str, component: Dict[str, Any]):
        """Trigger alert for component failure."""
        from ..event_bus import publish_health_alert
        
        alert = {
            'component': component_name,
            'status': component['last_status'],
            'failure_count': component['failure_count'],
            'critical': component['critical'],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.warning(f"Health alert: {alert}")
        
        # Publish to event bus for cross-layer propagation
        publish_health_alert(
            component=component_name,
            status=component['last_status'],
            failure_count=component['failure_count'],
            critical=component['critical'],
            alert_data=alert
        )
        
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """Add alert callback."""
        self.alert_callbacks.append(callback)
    
    def check_component(self, name: str) -> Optional[bool]:
        """Manually check a component."""
        if name in self.components:
            try:
                return self.components[name]['check_func']()
            except Exception:
                return False
        return None
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get overall health report."""
        uptime = time.time() - self.start_time
        
        component_status = {}
        for name, component in self.components.items():
            component_status[name] = {
                'status': component['last_status'],
                'failure_count': component['failure_count'],
                'critical': component['critical'],
                'last_check': component['last_check']
            }
        
        healthy_components = sum(1 for c in component_status.values() 
                                if c['status'] == 'healthy')
        
        return {
            'uptime_seconds': uptime,
            'check_count': self.check_count,
            'components': component_status,
            'total_components': len(self.components),
            'healthy_components': healthy_components,
            'overall_status': 'healthy' if healthy_components == len(self.components) else 'degraded'
        }
    
    def force_health_check(self):
        """Force immediate health check."""
        self._perform_health_check()


class ComponentHealth:
    """Base class for component health checks."""
    
    @staticmethod
    def check_data_client(client) -> bool:
        """Check if data client is connected."""
        if hasattr(client, 'is_connected'):
            return client.is_connected()
        return True
    
    @staticmethod
    def check_risk_engine(engine) -> bool:
        """Check if risk engine is responsive."""
        if hasattr(engine, 'get_risk_status'):
            try:
                engine.get_risk_status()
                return True
            except Exception:
                return False
        return True
    
    @staticmethod
    def check_order_manager(manager) -> bool:
        """Check if order manager is responsive."""
        if hasattr(manager, 'get_all_positions'):
            try:
                manager.get_all_positions()
                return True
            except Exception:
                return False
        return True


health_monitor = HealthMonitor({'health_check_interval': 60})


def check_health() -> Dict[str, Any]:
    """Convenience function to check health."""
    return health_monitor.get_health_report()
