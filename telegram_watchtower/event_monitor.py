#!/usr/bin/env python3
"""
Event Monitor for Telegram Watch Tower
Monitors system events and triggers notifications
"""

import os
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Callable
from collections import deque

logger = logging.getLogger('EventMonitor')

class EventType:
    SYSTEM_HEALTH = "system_health"
    WORKFLOW_EVENT = "workflow_event"
    AGENT_EVENT = "agent_event"
    RISK_ALERT = "risk_alert"
    SECURITY_EVENT = "security_event"
    ERROR_EVENT = "error_event"

class EventMonitor:
    def __init__(self, config: Dict):
        self.config = config
        self.events_config = config.get('watchtower', {}).get('events', {})
        self.resource_limits = config.get('watchtower', {}).get('resource_limits', {})
        
        self.monitoring_active = False
        self.monitor_thread = None
        self.event_callbacks: List[Callable] = []
        
        self.event_history = deque(maxlen=1000)
        self.alert_count = {
            EventType.RISK_ALERT: 0,
            EventType.ERROR_EVENT: 0,
            EventType.WORKFLOW_EVENT: 0,
            EventType.AGENT_EVENT: 0,
            EventType.SECURITY_EVENT: 0
        }
        self.processed_log_lines: set = set()
        self.last_log_size = 0
        
    def start(self):
        """Start event monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("Event monitoring started")
    
    def stop(self):
        """Stop event monitoring"""
        self.monitoring_active = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Event monitoring stopped")
    
    def register_callback(self, callback: Callable):
        """Register a callback for event notifications"""
        self.event_callbacks.append(callback)
    
    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                if self.events_config.get('system_health', True):
                    self._check_system_health()
                
                if self.events_config.get('risk_alerts', True):
                    self._check_risk_alerts()
                
                time.sleep(10)
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                time.sleep(5)
    
    def _check_system_health(self):
        """Check system health metrics"""
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            
            mem_info = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1])
                    mem_info[key] = value
            
            total = mem_info.get('MemTotal', 0) / (1024**2)
            available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0)) / (1024**2)
            used = total - available
            usage_percent = (used / total * 100) if total > 0 else 0
            
            memory_threshold = self.resource_limits.get('memory_threshold_percent', 85)
            
            if usage_percent > memory_threshold:
                self.record_event(
                    EventType.SYSTEM_HEALTH,
                    f"High memory usage: {usage_percent:.1f}%",
                    severity="warning"
                )
        except Exception as e:
            logger.error(f"System health check error: {e}")
    
    def _check_risk_alerts(self):
        """Check for risk alerts in log files"""
        try:
            risk_log = '/home/ubuntu/financial_orchestrator/logs/risk_monitor.log'
            if not os.path.exists(risk_log):
                return
                
            current_size = os.path.getsize(risk_log)
            if current_size == self.last_log_size:
                return
            
            with open(risk_log, 'r') as f:
                lines = f.readlines()
            
            self.last_log_size = current_size
            new_lines = [l for l in lines if l.strip() and hash(l.strip()) not in self.processed_log_lines]
            
            for line in new_lines[-20:]:
                line_hash = hash(line.strip())
                self.processed_log_lines.add(line_hash)
                
                if len(self.processed_log_lines) > 10000:
                    self.processed_log_lines = set(list(self.processed_log_lines)[-5000:])
                
                if 'CRITICAL' in line:
                    self.record_event(EventType.RISK_ALERT, line.strip(), severity="critical")
                elif 'WARNING' in line:
                    self.record_event(EventType.RISK_ALERT, line.strip(), severity="warning")
                elif 'ALERT' in line:
                    self.record_event(EventType.RISK_ALERT, line.strip(), severity="warning")
        except Exception as e:
            logger.error(f"Risk alert check error: {e}")
    
    def record_event(self, event_type: str, message: str, severity: str = "info") -> Dict:
        """Record a new event"""
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'message': message,
            'severity': severity
        }
        
        self.event_history.append(event)
        
        if event_type in self.alert_count:
            self.alert_count[event_type] += 1
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error: {e}")
        
        return event
    
    def get_recent_events(self, event_type: str = None, limit: int = 10) -> List[Dict]:
        """Get recent events"""
        events = list(self.event_history)
        if event_type:
            events = [e for e in events if e['type'] == event_type]
        return events[-limit:]
    
    def get_event_summary(self) -> Dict:
        """Get event summary statistics"""
        return {
            'total_events': len(self.event_history),
            'alert_counts': dict(self.alert_count),
            'recent_events': self.get_recent_events(limit=5),
            'monitoring_active': self.monitoring_active
        }
    
    def format_alert_message(self, event: Dict) -> str:
        """Format an alert message for Telegram"""
        emoji = {
            'critical': '\u26a0\ufe0f',
            'warning': '\u1f7e1',
            'info': '\u2139\ufe0f'
        }.get(event.get('severity', 'info'), '\u2139\ufe0f')
        
        return f"{emoji} *{event['type'].upper()}*\n" \
               f"_{event['timestamp']}_\n" \
               f"{event['message']}"
