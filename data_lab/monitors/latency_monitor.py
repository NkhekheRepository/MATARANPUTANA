#!/usr/bin/env python3
"""
Latency Monitor
Monitors tick and order book processing latency
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any
from collections import deque
from dataclasses import dataclass
from datetime import datetime

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('LatencyMonitor')


@dataclass
class LatencySample:
    """Latency measurement sample"""
    operation: str
    latency_ms: float
    timestamp: float
    details: Dict[str, Any] = None


class LatencyMonitor:
    """
    Monitors system latency for ticks, order book, and processing.
    Tracks P50, P95, P99 percentiles.
    """
    
    def __init__(
        self,
        max_samples: int = 10000,
        p50_warning_ms: float = 100,
        p95_warning_ms: float = 300,
        p99_warning_ms: float = 500
    ):
        self.max_samples = max_samples
        self.p50_warning_ms = p50_warning_ms
        self.p95_warning_ms = p95_warning_ms
        self.p99_warning_ms = p99_warning_ms
        
        self._samples: Dict[str, deque] = {
            'tick_ingestion': deque(maxlen=max_samples),
            'orderbook_update': deque(maxlen=max_samples),
            'feature_generation': deque(maxlen=max_samples),
            'storage_write': deque(maxlen=max_samples),
            'total_pipeline': deque(maxlen=max_samples)
        }
        
        self._last_sample_time: Dict[str, float] = {}
        self._lock = threading.Lock()
        
        self._alert_callbacks: List[callable] = []
    
    def record_latency(
        self,
        operation: str,
        latency_ms: float,
        details: Optional[Dict] = None
    ):
        """Record a latency measurement"""
        sample = LatencySample(
            operation=operation,
            latency_ms=latency_ms,
            timestamp=time.time(),
            details=details or {}
        )
        
        with self._lock:
            if operation not in self._samples:
                self._samples[operation] = deque(maxlen=self.max_samples)
                
            self._samples[operation].append(sample)
            self._last_sample_time[operation] = time.time()
        
        self._check_thresholds(operation, latency_ms)
    
    def _check_thresholds(self, operation: str, latency_ms: float):
        """Check if latency exceeds warning thresholds"""
        if operation == 'tick_ingestion':
            threshold = self.p50_warning_ms
        elif operation == 'orderbook_update':
            threshold = self.p95_warning_ms
        elif operation == 'feature_generation':
            threshold = self.p95_warning_ms
        else:
            threshold = self.p99_warning_ms
            
        if latency_ms > threshold:
            for callback in self._alert_callbacks:
                try:
                    callback({
                        'operation': operation,
                        'latency_ms': latency_ms,
                        'threshold': threshold,
                        'timestamp': time.time()
                    })
                except Exception as e:
                    logger.error(f"Latency alert callback error: {e}")
    
    def get_percentiles(self, operation: str) -> Dict[str, float]:
        """Get P50, P95, P99 for an operation"""
        with self._lock:
            samples = self._samples.get(operation, [])
            if not samples:
                return {'p50': 0, 'p95': 0, 'p99': 0, 'count': 0}
            
            latencies = sorted([s.latency_ms for s in samples])
            count = len(latencies)
            
            return {
                'p50': latencies[int(count * 0.5)] if count > 0 else 0,
                'p95': latencies[int(count * 0.95)] if count > 0 else 0,
                'p99': latencies[int(count * 0.99)] if count > 0 else 0,
                'count': count,
                'avg': sum(latencies) / count,
                'max': max(latencies) if latencies else 0
            }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get statistics for all operations"""
        stats = {}
        
        with self._lock:
            for operation in self._samples.keys():
                stats[operation] = self.get_percentiles(operation)
                stats[operation]['last_update'] = self._last_sample_time.get(operation)
        
        return stats
    
    def register_alert_callback(self, callback: callable):
        """Register alert callback"""
        self._alert_callbacks.append(callback)
    
    def reset(self, operation: Optional[str] = None):
        """Reset latency samples"""
        with self._lock:
            if operation:
                if operation in self._samples:
                    self._samples[operation].clear()
            else:
                for samples in self._samples.values():
                    samples.clear()
