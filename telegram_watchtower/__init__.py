#!/usr/bin/env python3
"""
Telegram Watch Tower Package
Real-time monitoring bot for Financial Orchestrator
"""

from .bot_controller import TelegramWatchtower, BotStatus
from .event_monitor import EventMonitor, EventType
from .log_tailer import LogTailer
from .command_processor import CommandProcessor

__version__ = "1.0.0"
__all__ = [
    'TelegramWatchtower',
    'BotStatus',
    'EventMonitor',
    'EventType',
    'LogTailer',
    'CommandProcessor'
]
