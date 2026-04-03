"""
Layer 6: Config Reload
Hot-reload configuration without restarting.
"""

import time
import threading
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from loguru import logger


class ConfigReload:
    """Hot-reload configuration functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('config_reload', True)
        self.watch_interval = config.get('config_watch_interval', 30)
        
        self.config_path: Optional[Path] = None
        self.config: Dict[str, Any] = {}
        
        self.watch_thread: Optional[threading.Thread] = None
        self.running = False
        
        self.last_modified = 0
        
        self.config_callbacks: List[Callable] = []
        
        self.reload_count = 0
    
    def load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from file."""
        self.config_path = Path(config_path)
        
        if not self.config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            return {}
        
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            self.config = config
            self.last_modified = self.config_path.stat().st_mtime
            
            logger.info(f"Loaded config from {config_path}")
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def start_watching(self):
        """Start watching config file for changes."""
        if not self.enabled or not self.config_path:
            return
        
        self.running = True
        
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()
        
        logger.info("Config watching started")
    
    def stop_watching(self):
        """Stop watching config file."""
        self.running = False
        
        if self.watch_thread:
            self.watch_thread.join(timeout=5)
        
        logger.info("Config watching stopped")
    
    def _watch_loop(self):
        """Watch loop for config changes."""
        while self.running:
            try:
                self._check_for_changes()
            except Exception as e:
                logger.error(f"Config watch error: {e}")
            
            time.sleep(self.watch_interval)
    
    def _check_for_changes(self):
        """Check if config file has changed."""
        if not self.config_path or not self.config_path.exists():
            return
        
        current_mtime = self.config_path.stat().st_mtime
        
        if current_mtime > self.last_modified:
            logger.info("Config file changed, reloading...")
            
            self.reload_config()
    
    def reload_config(self) -> bool:
        """Reload configuration from file."""
        if not self.config_path:
            return False
        
        try:
            with open(self.config_path, 'r') as f:
                new_config = yaml.safe_load(f)
            
            old_config = self.config.copy()
            self.config = new_config
            self.last_modified = self.config_path.stat().st_mtime
            
            self.reload_count += 1
            
            logger.info(f"Config reloaded ({self.reload_count} reloads)")
            
            for callback in self.config_callbacks:
                try:
                    callback(new_config, old_config)
                except Exception as e:
                    logger.error(f"Config callback error: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to reload config: {e}")
            return False
    
    def add_reload_callback(self, callback: Callable):
        """Add callback to be notified on config reload."""
        self.config_callbacks.append(callback)
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration."""
        return self.config.copy()
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get config value by key."""
        keys = key.split('.')
        
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_reload_status(self) -> Dict[str, Any]:
        """Get reload status."""
        return {
            'enabled': self.enabled,
            'watching': self.running,
            'reload_count': self.reload_count,
            'config_path': str(self.config_path) if self.config_path else None,
            'last_modified': self.last_modified
        }


class ConfigManager:
    """Manages configuration across the system."""
    
    def __init__(self):
        self.config_reload = ConfigReload({'config_reload': True, 'config_watch_interval': 30})
        
        self.component_configs: Dict[str, Dict[str, Any]] = {}
    
    def load_from_file(self, config_path: str):
        """Load config from file."""
        return self.config_reload.load_config(config_path)
    
    def start_reload_watcher(self):
        """Start config reload watcher."""
        self.config_reload.start_watching()
    
    def stop_reload_watcher(self):
        """Stop config reload watcher."""
        self.config_reload.stop_watching()
    
    def register_component_config(self, component_name: str, 
                                  config_keys: List[str],
                                  apply_func: Callable):
        """Register component for config updates."""
        self.component_configs[component_name] = {
            'keys': config_keys,
            'apply_func': apply_func
        }
        
        self.config_reload.add_reload_callback(
            lambda new, old: self._apply_component_config(component_name, new, old)
        )
    
    def _apply_component_config(self, component_name: str, 
                                new_config: Dict[str, Any], 
                                old_config: Dict[str, Any]):
        """Apply config changes to component."""
        if component_name not in self.component_configs:
            return
        
        component = self.component_configs[component_name]
        
        for key in component['keys']:
            new_value = new_config
            old_value = old_config
            
            for k in key.split('.'):
                new_value = new_value.get(k, {}) if isinstance(new_value, dict) else {}
                old_value = old_value.get(k, {}) if isinstance(old_value, dict) else {}
            
            if new_value != old_value:
                try:
                    component['apply_func'](key, new_value, old_value)
                    logger.info(f"Applied config change for {component_name}: {key}")
                except Exception as e:
                    logger.error(f"Failed to apply config for {component_name}: {e}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current config."""
        return self.config_reload.get_config()
    
    def get_status(self) -> Dict[str, Any]:
        """Get config status."""
        return self.config_reload.get_reload_status()


config_manager = ConfigManager()


def reload_config() -> bool:
    """Convenience function to reload config."""
    return config_manager.config_reload.reload_config()
