#!/usr/bin/env python3
"""
Queue Monitor
Monitors Redis queue depth and processing lag
"""

import time
import logging
import threading
from typing import Dict, List, Optional, Any
from collections import deque

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('QueueMonitor')


class QueueMonitor:
    """
    Monitors Redis stream queue health.
    Tracks depth, lag, and processing rates.
    """
    
    def __init__(
        self,
        check_interval_seconds: int = 10,
        warning_threshold: float = 0.8,
        critical_threshold: float = 0.95
    ):
        self.check_interval_seconds = check_interval_seconds
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        self._stream_info: Dict[str, Dict] = {}
        self._history: deque = deque(maxlen=100)
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        
        self._alert_callbacks: List[callable] = []
        
        self._lock = threading.Lock()
    
    def start(self):
        """Start monitoring"""
        if self._running:
            return
            
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Queue monitor started")
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Queue monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self._running:
            try:
                self._check_queues()
                time.sleep(self.check_interval_seconds)
            except Exception as e:
                logger.error(f"Queue monitor error: {e}")
    
    def _check_queues(self):
        """Check all queue depths"""
        from data_lab import get_stream_manager
        
        try:
            manager = get_stream_manager()
            stream_info = manager.get_all_stream_info()
            
            with self._lock:
                self._stream_info = stream_info
                
                for stream, info in stream_info.items():
                    utilization = info.get('utilization_percent', 0) / 100
                    
                    if utilization >= self.critical_threshold:
                        self._trigger_alert(stream, 'critical', utilization, info)
                    elif utilization >= self.warning_threshold:
                        self._trigger_alert(stream, 'warning', utilization, info)
                
                self._history.append({
                    'timestamp': time.time(),
                    'streams': stream_info
                })
                
        except Exception as e:
            logger.error(f"Failed to check queues: {e}")
    
    def _trigger_alert(self, stream: str, level: str, utilization: float, info: Dict):
        """Trigger queue alert"""
        for callback in self._alert_callbacks:
            try:
                callback({
                    'stream': stream,
                    'level': level,
                    'utilization': utilization,
                    'length': info.get('length', 0),
                    'max_length': info.get('max_length', 0),
                    'timestamp': time.time()
                })
            except Exception as e:
                logger.error(f"Queue alert callback error: {e}")
    
    def register_alert_callback(self, callback: callable):
        """Register alert callback"""
        self._alert_callbacks.append(callback)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status"""
        with self._lock:
            return {
                'streams': self._stream_info,
                'history_length': len(self._history)
            }
    
    def get_stream_utilization(self, stream: str) -> float:
        """Get utilization for a stream"""
        with self._lock:
            info = self._stream_info.get(stream, {})
            return info.get('utilization_percent', 0) / 100
    
    def get_all_utilizations(self) -> Dict[str, float]:
        """Get all stream utilizations"""
        with self._lock:
            return {
                stream: info.get('utilization_percent', 0) / 100
                for stream, info in self._stream_info.items()
            }
