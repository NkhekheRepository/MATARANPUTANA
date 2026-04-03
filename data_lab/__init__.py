#!/usr/bin/env python3
"""
Data Lab - Phase 1 Quant Lab Foundation
Data ingestion, storage, feature extraction, and monitoring
"""

__version__ = "1.0.0"

from .redis_stream_manager import (
    RedisStreamManager,
    get_stream_manager,
    StreamEvent,
    EventPriority,
    StreamName
)

__all__ = [
    'RedisStreamManager',
    'get_stream_manager',
    'StreamEvent',
    'EventPriority',
    'StreamName'
]
