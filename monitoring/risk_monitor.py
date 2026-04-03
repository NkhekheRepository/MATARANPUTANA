#!/usr/bin/env python3
"""
Risk Monitoring System for Financial Orchestrator
Monitors risk scores and triggers alerts based on configured policies
"""

import yaml
import time
import logging
import threading
from datetime import datetime, timedelta
from enum import Enum
import json
import os
import sys

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')
try:
    from telegram_notify import (
        send_startup_notification, 
        send_shutdown_notification,
        send_risk_alert,
        send_to_admin
    )
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[WARN] Telegram notifications not available")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/home/ubuntu/financial_orchestrator/logs/risk_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RiskMonitor')

class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskMonitor:
    def __init__(self, config_path='/home/ubuntu/financial_orchestrator/configs/risk_scoring.yaml'):
        self.config_path = config_path
        self.config = self.load_config()
        self.current_risk_score = 0.0
        self.risk_level = RiskLevel.LOW
        self.alert_history = []
        self.monitoring_active = False
        self.monitor_thread = None
        
    def load_config(self):
        """Load risk scoring configuration"""
        try:
            with open(self.config_path, 'r') as file:
                return yaml.safe_load(file)
        except Exception as e:
            logger.error(f"Failed to load risk config: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Return default configuration if file loading fails"""
        return {
            'risk_scoring_enabled': True,
            'risk_thresholds': {'low': 0.3, 'medium': 0.6, 'high': 0.8, 'critical': 0.95},
            'kill_switch_policies': {'enabled': True}
        }
    
    def calculate_risk_score(self):
        """
        Calculate current risk score based on various factors
        In a real implementation, this would query actual metrics
        For now, we'll simulate based on time of day and random factors
        """
        # Simulate risk factors (in reality, these would come from actual monitoring)
        reliability = 0.9  # High reliability
        criticality = 0.3  # Low criticality during normal ops
        resource_usage = 0.4  # Moderate resource usage
        historical_performance = 0.85  # Good historical performance
        external_anomalies = 0.2  # Low external anomalies
        
        # Apply weights from config
        weights = self.config.get('risk_factor_weights', {
            'reliability': 0.25,
            'criticality': 0.20,
            'resource_usage': 0.15,
            'historical_performance': 0.20,
            'external_anomalies': 0.20
        })
        
        # Calculate weighted risk score (lower values = lower risk)
        # We invert some factors since high reliability = low risk
        risk_score = (
            (1 - reliability) * weights.get('reliability', 0.25) +
            criticality * weights.get('criticality', 0.20) +
            resource_usage * weights.get('resource_usage', 0.15) +
            (1 - historical_performance) * weights.get('historical_performance', 0.20) +
            external_anomalies * weights.get('external_anomalies', 0.20)
        )
        
        # Add some time-based variation for demonstration
        hour = datetime.now().hour
        if 9 <= hour <= 16:  # Market hours
            risk_score *= 1.2  # Slightly higher risk during market hours
        elif 22 <= hour or hour <= 6:  # Overnight
            risk_score *= 0.8  # Lower risk overnight
            
        # Ensure score is between 0 and 1
        risk_score = max(0.0, min(1.0, risk_score))
        
        return risk_score
    
    def get_risk_level(self, score):
        """Convert numeric score to risk level"""
        thresholds = self.config.get('risk_thresholds', {
            'low': 0.3,
            'medium': 0.6,
            'high': 0.8,
            'critical': 0.95
        })
        
        if score >= thresholds['critical']:
            return RiskLevel.CRITICAL
        elif score >= thresholds['high']:
            return RiskLevel.HIGH
        elif score >= thresholds['medium']:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def check_kill_switch_conditions(self, risk_score, risk_level):
        """Check if kill-switch conditions are met"""
        if not self.config.get('kill_switch_policies', {}).get('enabled', False):
            return False, None
            
        policies = self.config.get('kill_switch_policies', {}).get('automatic_triggers', [])
        
        for policy in policies:
            condition = policy.get('condition')
            action = policy.get('action')
            
            if condition == "risk_score > 0.95" and risk_score > 0.95:
                return True, action
            elif condition == "consecutive_failures > 3":
                # In real implementation, check actual failure count
                pass
                
        return False, None
    
    def trigger_alert(self, risk_score, risk_level, action=None):
        """Trigger an alert based on risk level"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'risk_score': risk_score,
            'risk_level': risk_level.value,
            'action': action,
            'message': f"Risk level elevated to {risk_level.value} (score: {risk_score:.3f})"
        }
        
        self.alert_history.append(alert)
        
        # Log the alert
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            logger.warning(alert['message'])
        else:
            logger.info(alert['message'])
            
        # Send Telegram alert for high/critical levels
        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] and TELEGRAM_AVAILABLE:
            try:
                send_risk_alert(
                    risk_score=risk_score,
                    risk_level=risk_level.value,
                    message=alert['message']
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram alert: {e}")
        
        print(f"ALERT: {alert['message']}")
        
        return alert
    
    def monitoring_loop(self):
        """Main monitoring loop"""
        logger.info("Starting risk monitoring loop")
        consecutive_high_risk = 0
        
        while self.monitoring_active:
            try:
                # Calculate current risk score
                self.current_risk_score = self.calculate_risk_score()
                self.risk_level = self.get_risk_level(self.current_risk_score)
                
                # Check for kill-switch conditions
                kill_switch_triggered, action = self.check_kill_switch_conditions(
                    self.current_risk_score, self.risk_level
                )
                
                # Trigger alerts based on risk level changes
                if self.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL] or kill_switch_triggered:
                    self.trigger_alert(self.current_risk_score, self.risk_level, action)
                    if kill_switch_triggered:
                        consecutive_high_risk += 1
                        if consecutive_high_risk >= 3:  # Multiple consecutive high-risk readings
                            logger.critical(f"KILL SWITCH TRIGGERED: {action}")
                            # In real implementation, this would trigger actual kill-switch
                else:
                    consecutive_high_risk = 0  # Reset counter
                
                # Log regular updates
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    logger.info(f"Risk score: {self.current_risk_score:.3f} ({self.risk_level.value})")
                
                # Sleep until next check
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(5)
    
    def start_monitoring(self):
        """Start the risk monitoring system"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitor_thread = threading.Thread(target=self.monitoring_loop, daemon=True)
            self.monitor_thread.start()
            logger.info("Risk monitoring started")
            return True
        else:
            logger.warning("Risk monitoring already active")
            return False
    
    def stop_monitoring(self):
        """Stop the risk monitoring system"""
        if self.monitoring_active:
            self.monitoring_active = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=5)
            logger.info("Risk monitoring stopped")
            return True
        else:
            logger.warning("Risk monitoring not active")
            return False
    
    def get_current_status(self):
        """Get current monitoring status"""
        return {
            'monitoring_active': self.monitoring_active,
            'current_risk_score': self.current_risk_score,
            'current_risk_level': self.risk_level.value if self.risk_level else None,
            'last_update': datetime.now().isoformat(),
            'alert_count': len(self.alert_history)
        }

# Example usage
if __name__ == "__main__":
    print("Starting Risk Monitor...")
    
    # Send startup notification
    if TELEGRAM_AVAILABLE:
        send_startup_notification("Risk Monitor")
    
    monitor = RiskMonitor()
    
    # Start monitoring
    monitor.start_monitoring()
    
    try:
        # Run indefinitely until interrupted
        while True:
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\nShutting down Risk Monitor...")
    finally:
        monitor.stop_monitoring()
        if TELEGRAM_AVAILABLE:
            send_shutdown_notification("Risk Monitor")