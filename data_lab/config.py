#!/usr/bin/env python3
"""
Data Lab Configuration
Central configuration for all Phase 1 components
"""

import os
import yaml
from typing import Dict, Any, Optional

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'configs', 'data_lab_config.yaml')


class DataLabConfig:
    """Configuration manager for Data Lab"""
    
    _instance = None
    _config: Dict[str, Any] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._config:
            self.load()
    
    def load(self, config_path: Optional[str] = None):
        """Load configuration from file"""
        path = config_path or CONFIG_PATH
        
        try:
            with open(path, 'r') as f:
                self._config = yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
            self._config = self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'data_lab': {
                'version': '1.0.0',
                'enabled': True,
                'memory_limits': {
                    'data_ingestion': 500,
                    'feature_lab': 1024,
                    'redis_buffer': 500,
                    'monitoring': 200,
                    'total_max': 6650
                },
                'redis': {
                    'host': 'localhost',
                    'port': 6379,
                    'db': 0
                },
                'streams': {
                    'market_data': {
                        'name': 'market_data',
                        'max_length': 10000
                    },
                    'system_alerts': {
                        'name': 'system_alerts',
                        'max_length': 5000
                    },
                    'feature_output': {
                        'name': 'feature_output',
                        'max_length': 5000
                    }
                },
                'backpressure': {
                    'enabled': True,
                    'warning_threshold': 0.8,
                    'critical_threshold': 0.95
                },
                'monitoring': {
                    'enabled': True,
                    'cpu_threshold_percent': 70,
                    'ram_threshold_mb': 6650,
                    'latency_threshold_ms': 500
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
                
        return value
    
    def get_all(self) -> Dict[str, Any]:
        """Get full configuration"""
        return self._config


def get_config() -> DataLabConfig:
    """Get singleton config instance"""
    return DataLabConfig()
