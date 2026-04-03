#!/usr/bin/env python3
"""
Telegram Notification Module for Financial Orchestrator
Provides centralized notification functionality for all system components
"""

import os
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TelegramNotifier')

CONFIG_PATH = '/home/ubuntu/financial_orchestrator/telegram_watchtower/config.yaml'
ADMIN_CHAT_ID = 7361240735

def load_config() -> Dict[str, Any]:
    """Load bot configuration"""
    try:
        import yaml
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"Could not load config: {e}")
    return {}

def get_bot_token() -> str:
    """Get bot token from config"""
    config = load_config()
    return config.get('telegram', {}).get('bot_token', '')

def send_message(chat_id: int, text: str, parse_mode: str = None) -> bool:
    """Send a message to a Telegram chat"""
    bot_token = get_bot_token()
    
    if not bot_token or bot_token == 'YOUR_BOT_TOKEN_HERE':
        logger.info(f"[DRY-RUN] Would send to {chat_id}: {text[:100]}...")
        return True
    
    if not REQUESTS_AVAILABLE:
        logger.warning("requests library not available")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        safe_text = text.encode('utf-8', errors='replace').decode('utf-8')
        data = {'chat_id': chat_id, 'text': safe_text}
        if parse_mode:
            data['parse_mode'] = parse_mode
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Message sent to {chat_id}")
            return True
        else:
            logger.error(f"Failed to send: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return False

def send_to_admin(message: str, parse_mode: str = None) -> bool:
    """Send message to admin (chat_id 7361240735)"""
    return send_message(ADMIN_CHAT_ID, message, parse_mode)

def get_status_emoji(status: str) -> str:
    """Get emoji for status"""
    status_map = {
        'started': '🟢',
        'running': '✅',
        'stopped': '🔴',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'pending': '⏳',
    }
    return status_map.get(status.lower(), '•')

def format_timestamp() -> str:
    """Get current timestamp formatted"""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def send_startup_notification(component_name: str) -> bool:
    """Send startup notification for a component"""
    message = f"""
🚀 *{component_name} Started*

Status: Running
Time: {format_timestamp()}
"""
    return send_to_admin(message)

def send_shutdown_notification(component_name: str, reason: str = "Manual shutdown") -> bool:
    """Send shutdown notification for a component"""
    message = f"""
🛑 *{component_name} Stopped*

Reason: {reason}
Time: {format_timestamp()}
"""
    return send_to_admin(message)

def send_alert(component_name: str, level: str, message: str, details: str = "") -> bool:
    """Send alert notification"""
    level_emojis = {
        'CRITICAL': '🚨',
        'ERROR': '❌',
        'WARNING': '⚠️',
        'INFO': 'ℹ️',
        'SUCCESS': '✅',
    }
    emoji = level_emojis.get(level.upper(), '•')
    
    full_message = f"""
{emoji} *ALERT: {component_name}*

Level: {level}
Message: {message}
"""
    if details:
        full_message += f"\nDetails: {details}"
    
    full_message += f"\nTime: {format_timestamp()}"
    
    return send_to_admin(full_message)

def send_system_startup(components: List[Dict[str, str]]) -> bool:
    """Send system-wide startup notification"""
    header = """
🚀 *Financial Orchestrator Starting*
━━━━━━━━━━━━━━━━━━━━
"""
    
    component_lines = []
    for comp in components:
        name = comp.get('name', 'Unknown')
        status = comp.get('status', 'unknown')
        emoji = get_status_emoji(status)
        component_lines.append(f"{emoji} {name}")
    
    footer = f"""
━━━━━━━━━━━━━━━━━━━━
Time: {format_timestamp()}
"""
    
    message = header + "\n".join(component_lines) + footer
    return send_to_admin(message)

def send_system_shutdown(components: List[str]) -> bool:
    """Send system-wide shutdown notification"""
    header = """
🛑 *Financial Orchestrator Shutting Down*
━━━━━━━━━━━━━━━━━━━━
"""
    
    component_lines = [f"🔴 {comp}" for comp in components]
    
    footer = f"""
━━━━━━━━━━━━━━━━━━━━
Time: {format_timestamp()}
"""
    
    message = header + "\n".join(component_lines) + footer
    return send_to_admin(message)

def send_health_report(component_name: str, metrics: Dict[str, Any]) -> bool:
    """Send periodic health report"""
    uptime = metrics.get('uptime', 'N/A')
    memory = metrics.get('memory_usage', 'N/A')
    cpu = metrics.get('cpu_usage', 'N/A')
    status = metrics.get('status', 'unknown')
    
    emoji = get_status_emoji(status)
    
    message = f"""
📊 *Health Report: {component_name}*
━━━━━━━━━━━━━━━━━━━━
{emoji} Status: {status.upper()}
⏱️  Uptime: {uptime}
💾 Memory: {memory}
🖥️  CPU: {cpu}
━━━━━━━━━━━━━━━━━━━━
Time: {format_timestamp()}
"""
    return send_to_admin(message)

def send_workflow_update(workflow_name: str, phase: str, progress: int, status: str) -> bool:
    """Send workflow progress update"""
    emoji = get_status_emoji(status)
    
    progress_bar = '█' * (progress // 10) + '░' * (10 - progress // 10)
    
    message = f"""
{emoji} *Workflow Update*

Workflow: {workflow_name}
Phase: {phase}
Progress: [{progress_bar}] {progress}%
Status: {status.upper()}
"""
    return send_to_admin(message)

def send_validation_result(schema_name: str, is_valid: bool, errors: List[str] = None) -> bool:
    """Send validation result"""
    if is_valid:
        emoji = '✅'
        status = "PASSED"
        message = f"""
{emoji} *Validation Passed*

Schema: {schema_name}
"""
    else:
        emoji = '❌'
        status = "FAILED"
        error_list = "\n".join([f"  • {e}" for e in (errors or ['Unknown error'])])
        message = f"""
{emoji} *Validation Failed*

Schema: {schema_name}
Errors:
{error_list}
"""
    return send_to_admin(message)

def send_risk_alert(risk_score: float, risk_level: str, message: str) -> bool:
    """Send risk alert"""
    level_emojis = {
        'low': '🟢',
        'medium': '🟡',
        'high': '🟠',
        'critical': '🔴',
    }
    emoji = level_emojis.get(risk_level.lower(), '•')
    
    message_text = f"""
{emoji} *Risk Alert*

Score: {risk_score:.2f}
Level: {risk_level.upper()}
Message: {message}
Time: {format_timestamp()}
"""
    return send_to_admin(message_text)

if __name__ == "__main__":
    print("Telegram Notifier - Testing notifications...")
    
    print("\n1. Testing startup notification...")
    result = send_startup_notification("Test Component")
    print(f"   Result: {'Success' if result else 'Failed'}")
    
    print("\n2. Testing alert notification...")
    result = send_alert("Test Component", "INFO", "This is a test message")
    print(f"   Result: {'Success' if result else 'Failed'}")
    
    print("\n3. Testing health report...")
    result = send_health_report("Test", {
        'uptime': '1h 30m',
        'memory_usage': '45%',
        'cpu_usage': '12%',
        'status': 'running'
    })
    print(f"   Result: {'Success' if result else 'Failed'}")
    
    print("\nTest complete!")
