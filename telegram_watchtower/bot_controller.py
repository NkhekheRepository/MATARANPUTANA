#!/usr/bin/env python3
"""
Telegram Watch Tower Bot Controller
Main controller for the real-time monitoring bot
"""

import yaml
import logging
import threading
import time
import json
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TelegramWatchtower')

class BotStatus(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"

class TelegramWatchtower:
    def __init__(self, config_path='/home/ubuntu/MATARANPUTANA/telegram_watchtower/config.yaml'):
        self.config_path = config_path
        self.config = self.load_config()
        self.status = BotStatus.STOPPED
        self.bot_token = self.config.get('telegram', {}).get('bot_token', '')
        self.allowed_chat_ids = set(self.config.get('telegram', {}).get('allowed_chat_ids', []))
        self.admin_chat_ids = set(self.config.get('telegram', {}).get('admin_chat_ids', []))
        
        self.event_monitor = None
        self.log_tailer = None
        self.command_processor = None
        self.trading_integration = None
        
        self.message_queue = []
        self.alerts = []
        self.start_time = None
        
        self.alert_throttle_seconds = 60
        self.last_alert_times: Dict[str, float] = {}
        
        self.health_check_interval = 3600
        self.last_health_report = 0
        self.health_thread = None
        
        self.resource_limits = self.config.get('watchtower', {}).get('resource_limits', {})
        
    def load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
            return self.get_default_config()
    
    def get_default_config(self) -> Dict:
        """Return default configuration"""
        return {
            'telegram': {'enabled': True, 'bot_token': '', 'allowed_chat_ids': []},
            'watchtower': {
                'name': 'Financial Orchestrator Watch Tower',
                'version': '1.0.0',
                'events': {'system_health': True, 'workflow_events': True, 'agent_events': True, 'risk_alerts': True, 'security_events': True},
                'polling': {'interval_seconds': 5, 'long_polling_timeout': 60},
                'resource_limits': {'memory_threshold_percent': 85, 'cpu_threshold_percent': 90, 'disk_threshold_percent': 90},
                'memory': {'max_log_buffer_mb': 10, 'cleanup_interval_seconds': 300}
            }
        }
    
    def initialize_components(self):
        """Initialize all components"""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            
            from telegram_watchtower.event_monitor import EventMonitor
            from telegram_watchtower.log_tailer import LogTailer
            from telegram_watchtower.command_processor import CommandProcessor
            from telegram_watchtower.bot_menu import BotMenu
            from telegram_watchtower.trading_integration import TradingBotIntegration
            from telegram_watchtower.quant_commands import QuantCommandProcessor
            
            self.event_monitor = EventMonitor(self.config)
            self.log_tailer = LogTailer(self.config)
            self.command_processor = CommandProcessor(self.config)
            self.bot_menu = BotMenu(self.config)
            
            # Initialize Quant Command Processor for advanced analytics
            self.quant_processor = QuantCommandProcessor(self.config)
            
            self.trading_integration = TradingBotIntegration()
            if self.trading_integration.initialize():
                self.trading_integration.set_alert_callback(self._on_trade_alert)
                self.command_processor.set_trading_engine(self.trading_integration)
                logger.info("Trading integration initialized")
            else:
                logger.warning("Trading integration failed to initialize")
            
            logger.info("All components initialized successfully")
            return True
        except ImportError as e:
            logger.error(f"Failed to import components: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize components: {e}")
            return False
    
    def start(self) -> bool:
        """Start the watch tower bot"""
        if self.status == BotStatus.RUNNING:
            logger.warning("Watch tower is already running")
            return False
        
        self.status = BotStatus.STARTING
        logger.info("Starting Telegram Watch Tower...")
        
        if not self.initialize_components():
            self.status = BotStatus.ERROR
            return False
        
        self.start_time = datetime.now()
        self.status = BotStatus.RUNNING
        
        logger.info(f"Watch Tower started: {self.config['watchtower']['name']} v{self.config['watchtower']['version']}")
        
        if self.log_tailer:
            self.log_tailer.register_callback(self.on_log_alert)
            self.log_tailer.start()
            logger.info("Log monitoring started")
        
        self.health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self.health_thread.start()
        logger.info("Health check thread started")
        
        return True
    
    def _on_trade_alert(self, message: str):
        """Handle trade alerts from trading engine"""
        logger.info(f"Trade alert received: {message[:50]}...")
        self.broadcast_to_admins(message)
    
    def stop(self):
        """Stop the watch tower bot"""
        if self.status == BotStatus.STOPPED:
            return
        
        self.status = BotStatus.STOPPING
        logger.info("Stopping Telegram Watch Tower...")
        
        if self.log_tailer:
            self.log_tailer.stop()
        if self.event_monitor:
            self.event_monitor.stop()
        
        self.status = BotStatus.STOPPED
        logger.info("Watch Tower stopped")
    
    def send_message(self, chat_id: int, text: str, parse_mode: str = 'Markdown', reply_markup: str = None) -> bool:
        """Send a message to a chat"""
        if not self.bot_token or self.bot_token == 'YOUR_BOT_TOKEN_HERE':
            logger.debug(f"Would send message to {chat_id}: {text[:50]}...")
            return True
        
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            safe_text = text.encode('utf-8', errors='replace').decode('utf-8')
            data = {'chat_id': chat_id, 'text': safe_text, 'parse_mode': parse_mode}
            if reply_markup:
                data['reply_markup'] = reply_markup
            response = requests.post(url, data=data, timeout=10)
            if response.status_code != 200:
                logger.error(f"Failed to send: {response.text}")
            else:
                logger.info(f"Message sent to {chat_id}")
            return response.status_code == 200
        except ImportError:
            logger.debug(f"Requests not available. Would send to {chat_id}: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def send_keyboard(self, chat_id: int, text: str, keyboard: List[List[Dict]], parse_mode: str = 'Markdown') -> bool:
        """Send a message with inline keyboard"""
        import json
        reply_markup = json.dumps({'inline_keyboard': keyboard})
        return self.send_message(chat_id, text, parse_mode, reply_markup)
    
    def answer_callback_query(self, callback_query_id: str, text: str = None) -> bool:
        """Answer a callback query"""
        if not self.bot_token or self.bot_token == 'YOUR_BOT_TOKEN_HERE':
            return True
        
        try:
            import requests
            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
            data = {'callback_query_id': callback_query_id}
            if text:
                data['text'] = text
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
            return False
    
    def broadcast_to_admins(self, message: str) -> int:
        """Broadcast message to all admin users"""
        sent_count = 0
        for admin_id in self.admin_chat_ids:
            if self.send_message(admin_id, message):
                sent_count += 1
        return sent_count
    
    def handle_update(self, update: Dict) -> Optional[str]:
        """Handle an incoming update from Telegram"""
        if 'callback_query' in update:
            return self.handle_callback_query(update['callback_query'])
        
        if 'message' not in update:
            return None
        
        message = update['message']
        chat_id = message.get('chat', {}).get('id')
        text = message.get('text', '')
        
        logger.info(f"Received message from chat_id={chat_id}: {text}")
        
        if chat_id not in self.admin_chat_ids:
            logger.warning(f"Unauthorized access attempt from chat_id={chat_id}")
            self.send_message(chat_id, "⛔ Access denied. This bot is private.")
            return None
        
        if self.command_processor:
            # First try quant processor for advanced commands
            command = text.strip().split()[0] if text.strip() else ''
            if hasattr(self, 'quant_processor') and self.quant_processor and command in self.quant_processor.commands:
                response = self.quant_processor.process(chat_id, text, self)
                if response and chat_id:
                    self.send_message(chat_id, response)
                return response
            
            # Fall back to legacy command processor
            response = self.command_processor.process(chat_id, text, self)
            if response and chat_id:
                text_lower = text.strip().lower()
                if text_lower in ['/start', '/hello', '/menu']:
                    msg, keyboard = self.bot_menu.format_main_menu() if self.bot_menu else (response, None)
                    self.send_keyboard(chat_id, msg, keyboard)
                elif text_lower in ['/hide', '/systemon', '/systemoff']:
                    self.send_message(chat_id, response)
                else:
                    keyboard = self.command_processor.get_main_menu_keyboard() if self.command_processor else None
                    if keyboard:
                        self.send_keyboard(chat_id, response, keyboard)
                    else:
                        self.send_message(chat_id, response)
            return response
        else:
            return "Bot initializing..."
    
    def handle_callback_query(self, callback_query: Dict) -> Optional[str]:
        """Handle callback query from inline keyboard"""
        callback_query_id = callback_query.get('id')
        chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
        data = callback_query.get('data', '')
        
        logger.info(f"Callback query from chat_id={chat_id}: {data}")
        
        if chat_id not in self.admin_chat_ids:
            self.answer_callback_query(callback_query_id, "⛔ Access denied")
            return None
        
        if self.bot_menu:
            response = self.bot_menu.handle_callback(data, chat_id, self)
            self.answer_callback_query(callback_query_id)
            
            if response:
                if data == 'hide':
                    self.send_message(chat_id, response)
                else:
                    msg, keyboard = self.bot_menu.format_main_menu()
                    self.send_keyboard(chat_id, response, keyboard)
            
            return response
        
        self.answer_callback_query(callback_query_id, "Menu not available")
        return None
    
    def get_status(self) -> Dict:
        """Get current watch tower status"""
        uptime = None
        if self.start_time:
            uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'status': self.status.value,
            'name': self.config['watchtower']['name'],
            'version': self.config['watchtower']['version'],
            'uptime_seconds': uptime,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'alerts_count': len(self.alerts),
            'queue_size': len(self.message_queue)
        }
    
    def get_system_metrics(self) -> Dict:
        """Get system resource metrics"""
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
            
            total = mem_info.get('MemTotal', 0) / 1024
            available = mem_info.get('MemAvailable', mem_info.get('MemFree', 0)) / 1024
            used = total - available
            
            return {
                'memory': {
                    'total_mb': total,
                    'used_mb': used,
                    'available_mb': available,
                    'usage_percent': (used / total * 100) if total > 0 else 0
                },
                'uptime': self.get_uptime_string()
            }
        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {'memory': {}, 'uptime': 'unknown'}
    
    def get_uptime_string(self) -> str:
        """Get system uptime as string"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
            
            days = int(uptime_seconds // 86400)
            hours = int((uptime_seconds % 86400) // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            parts = []
            if days > 0:
                parts.append(f"{days}d")
            if hours > 0:
                parts.append(f"{hours}h")
            parts.append(f"{minutes}m")
            
            return " ".join(parts)
        except Exception:
            return "unknown"
    
    def poll_updates(self):
        """Poll for updates from Telegram (simplified polling loop)"""
        offset = 0
        polling_config = self.config.get('watchtower', {}).get('polling', {})
        timeout = polling_config.get('long_polling_timeout', 5)
        
        logger.info(f"Polling started with timeout={timeout}")
        
        while self.status == BotStatus.RUNNING:
            try:
                if not self.bot_token or self.bot_token == 'YOUR_BOT_TOKEN_HERE':
                    time.sleep(5)
                    continue
                
                import requests
                url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
                params = {'timeout': timeout, 'offset': offset}
                
                logger.info(f"Polling for updates (offset={offset})...")
                response = requests.get(url, params=params, timeout=timeout + 15)
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('ok'):
                        updates = data.get('result', [])
                        logger.info(f"Got {len(updates)} updates")
                        for update in updates:
                            logger.info(f"Processing update: {update.get('update_id')}")
                            self.handle_update(update)
                            offset = update['update_id'] + 1
                
            except requests.exceptions.Timeout:
                logger.debug("Long polling timed out, continuing...")
                continue
            except Exception as e:
                logger.error(f"Polling error: {e}")
                time.sleep(5)
    
    def on_log_alert(self, log_entry: Dict):
        """Handle log alerts from the log tailer"""
        severity_keywords = ['CRITICAL', 'ERROR', 'FATAL', 'EXCEPTION']
        
        line = log_entry.get('line', '').upper()
        is_critical = any(kw in line for kw in severity_keywords)
        
        if not is_critical:
            return
        
        alert_key = f"{log_entry['source']}:{log_entry['pattern']}"
        current_time = time.time()
        
        if alert_key in self.last_alert_times:
            if current_time - self.last_alert_times[alert_key] < self.alert_throttle_seconds:
                return
        
        self.last_alert_times[alert_key] = current_time
        
        emoji_map = {
            'CRITICAL': '\u26a0\ufe0f',
            'ERROR': '\u274c',
            'FATAL': '\ud83d\udc94',
            'EXCEPTION': '\ud83d\udc94'
        }
        
        emoji = '\u274c'
        for kw, em in emoji_map.items():
            if kw in line:
                emoji = em
                break
        
        message = [
            f"{emoji} *ALERT: {log_entry['pattern']}*",
            f"\ud83d\udccc *Source:* {log_entry['source']}",
            f"\ud83d\udd52 *Time:* {log_entry['timestamp']}",
            f"\ud83d\udcdd *Message:*",
            f"`{log_entry['line'][:300]}`"
        ]
        
        alert_text = '\n'.join(message)
        self.alerts.append({'time': current_time, 'source': log_entry['source'], 'pattern': log_entry['pattern']})
        
        logger.warning(f"Alert triggered: {log_entry['pattern']} from {log_entry['source']}")
        self.broadcast_to_admins(alert_text)
    
    def _health_check_loop(self):
        """Background health check loop"""
        while self.status == BotStatus.RUNNING:
            time.sleep(60)
            
            try:
                self._check_resources()
                
                current_time = time.time()
                if current_time - self.last_health_report >= self.health_check_interval:
                    self._send_health_report()
                    self.last_health_report = current_time
                    
            except Exception as e:
                logger.error(f"Health check error: {e}")
    
    def _check_resources(self):
        """Check system resources and alert if thresholds exceeded"""
        try:
            metrics = self.get_system_metrics()
            mem_percent = metrics['memory'].get('usage_percent', 0)
            
            mem_threshold = self.resource_limits.get('memory_threshold_percent', 85)
            disk_threshold = self.resource_limits.get('disk_threshold_percent', 90)
            
            if mem_percent > mem_threshold:
                alert_key = f"memory:{mem_percent:.0f}%"
                current_time = time.time()
                
                if alert_key not in self.last_alert_times or \
                   current_time - self.last_alert_times[alert_key] > 300:
                    self.last_alert_times[alert_key] = current_time
                    
                    message = [
                        "\u26a0\ufe0f *RESOURCE WARNING*",
                        f"\ud83d\udcca *Memory Usage:* {mem_percent:.1f}%",
                        f"\u26a0 *Threshold:* {mem_threshold}%",
                        "\n_Consider freeing memory or scaling resources_"
                    ]
                    self.broadcast_to_admins('\n'.join(message))
                    logger.warning(f"Memory warning sent: {mem_percent:.1f}%")
            
            try:
                import psutil
                disk_percent = psutil.disk_usage('/').percent
                if disk_percent > disk_threshold:
                    alert_key = f"disk:{disk_percent:.0f}%"
                    current_time = time.time()
                    
                    if alert_key not in self.last_alert_times or \
                       current_time - self.last_alert_times[alert_key] > 300:
                        self.last_alert_times[alert_key] = current_time
                        
                        message = [
                            "\ud83d\udcbe *DISK WARNING*",
                            f"\ud83d\udcc5 *Disk Usage:* {disk_percent:.1f}%",
                            f"\u26a0 *Threshold:* {disk_threshold}%",
                            "\n_Disk space running low_"
                        ]
                        self.broadcast_to_admins('\n'.join(message))
                        logger.warning(f"Disk warning sent: {disk_percent:.1f}%")
            except ImportError:
                pass
                
        except Exception as e:
            logger.error(f"Resource check error: {e}")
    
    def _send_health_report(self):
        """Send periodic health report to admins"""
        try:
            metrics = self.get_system_metrics()
            status = self.get_status()
            
            uptime_str = self._format_uptime(status.get('uptime_seconds', 0))
            
            report = [
                "\ud83d\udfe2 *SYSTEM HEALTH REPORT*",
                f"\ud83d\udd52 *Time:* {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "",
                "\ud83d\udcc8 *System Uptime:* " + uptime_str,
                "",
                "\ud83d\udc8e *Memory:*",
                f"  Total: {metrics['memory'].get('total_mb', 0):.0f} MB",
                f"  Used: {metrics['memory'].get('used_mb', 0):.0f} MB ({metrics['memory'].get('usage_percent', 0):.1f}%)",
                f"  Available: {metrics['memory'].get('available_mb', 0):.0f} MB",
                "",
                f"\ud83d\udd14 *Alerts Today:* {len(self.alerts)}",
            ]
            
            if self.log_tailer:
                log_summary = self.log_tailer.get_log_summary()
                report.append(f"\ud83d\udcc4 *Logs Monitored:* {log_summary.get('total_entries', 0)}")
            
            self.broadcast_to_admins('\n'.join(report))
            logger.info("Health report sent")
            
        except Exception as e:
            logger.error(f"Health report error: {e}")
    
    def _format_uptime(self, seconds: float) -> str:
        """Format uptime seconds to human readable string"""
        if seconds is None:
            return "unknown"
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def run(self):
        """Run the watch tower bot (blocking)"""
        if not self.start():
            logger.error("Failed to start watch tower")
            return
        
        try:
            self.poll_updates()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

def main():
    """Main entry point"""
    bot = TelegramWatchtower()
    bot.run()

if __name__ == "__main__":
    main()
