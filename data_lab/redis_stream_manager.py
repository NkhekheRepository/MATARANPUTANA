#!/usr/bin/env python3
"""
Redis Stream Manager with Backpressure Control
Phase 1: Event-driven communication with queue management
"""

import os
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from collections import deque

import yaml

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available, using in-memory fallback")

logger = logging.getLogger('RedisStreamManager')


class EventPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class StreamName(Enum):
    MARKET_DATA = "market_data"
    SYSTEM_ALERTS = "system_alerts"
    FEATURE_OUTPUT = "feature_output"


@dataclass
class StreamConfig:
    name: str
    max_length: int
    warning_threshold: int
    critical_threshold: int
    block_timeout_ms: int = 1000
    consumer_group: str = "data_lab"
    priority_levels: List[str] = field(default_factory=lambda: ["critical", "high", "normal", "low"])


@dataclass
class StreamEvent:
    id: str
    stream: str
    priority: EventPriority
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BackpressureController:
    """Controls queue overflow and alerts"""
    
    def __init__(self, config_path: str = "/home/ubuntu/financial_orchestrator/configs/backpressure_config.yaml"):
        self.config = self._load_config(config_path)
        self.bp_config = self.config.get('backpressure', {})
        self.enabled = self.bp_config.get('enabled', True)
        self.warning_threshold = self.bp_config.get('warning_threshold', 0.8)
        self.critical_threshold = self.bp_config.get('critical_threshold', 0.95)
        self.drop_policy = self.bp_config.get('drop_policy', 'low_priority_first')
        self.alert_on_overflow = self.bp_config.get('alert_on_overflow', True)
        
        self.stream_configs: Dict[str, StreamConfig] = {}
        self.alert_callbacks: List[Callable] = []
        self._lock = threading.Lock()
        
    def _load_config(self, config_path: str) -> Dict:
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load backpressure config: {e}")
            return self._default_config()
            
    def _default_config(self) -> Dict:
        return {
            'backpressure': {
                'enabled': True,
                'warning_threshold': 0.8,
                'critical_threshold': 0.95,
                'drop_policy': 'low_priority_first',
                'alert_on_overflow': True
            }
        }
    
    def register_stream(self, stream_name: str, max_length: int):
        """Register a stream with its configuration"""
        bp_streams = self.bp_config.get('streams', {}).get(stream_name, {})
        
        config = StreamConfig(
            name=stream_name,
            max_length=max_length,
            warning_threshold=bp_streams.get('warning_threshold', int(max_length * 0.8)),
            critical_threshold=bp_streams.get('critical_threshold', int(max_length * 0.95)),
            priority_levels=bp_streams.get('priority_levels', ['critical', 'high', 'normal', 'low'])
        )
        
        with self._lock:
            self.stream_configs[stream_name] = config
            
    def register_alert_callback(self, callback: Callable):
        """Register callback for backpressure alerts"""
        self.alert_callbacks.append(callback)
    
    def check_backpressure(self, stream_name: str, current_length: int) -> Dict[str, Any]:
        """Check if backpressure needs to be applied"""
        with self._lock:
            config = self.stream_configs.get(stream_name)
            if not config:
                return {'status': 'ok', 'action': 'none'}
            
            if current_length >= config.critical_threshold:
                status = 'critical'
                action = 'drop_oldest'
            elif current_length >= config.warning_threshold:
                status = 'warning'
                action = 'slow_down'
            else:
                return {'status': 'ok', 'action': 'none'}
            
            percent = (current_length / config.max_length) * 100
            
            result = {
                'status': status,
                'action': action,
                'current_length': current_length,
                'max_length': config.max_length,
                'percent': percent,
                'stream': stream_name
            }
            
            if status == 'critical' and self.alert_on_overflow:
                for callback in self.alert_callbacks:
                    try:
                        callback(result)
                    except Exception as e:
                        logger.error(f"Alert callback failed: {e}")
                        
            return result
    
    def get_drop_priority(self, stream_name: str) -> List[EventPriority]:
        """Get priority order for dropping events"""
        config = self.stream_configs.get(stream_name)
        if not config:
            return [EventPriority.LOW, EventPriority.NORMAL, EventPriority.HIGH]
            
        priority_map = {
            'critical': EventPriority.CRITICAL,
            'high': EventPriority.HIGH,
            'normal': EventPriority.NORMAL,
            'low': EventPriority.LOW
        }
        
        levels = config.priority_levels
        return [priority_map.get(p, EventPriority.NORMAL) for p in levels]


class RedisStreamManager:
    """
    Manages Redis Streams with backpressure control.
    Handles event routing for market data, system alerts, and feature outputs.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, config_path: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: str = None):
        if self._initialized:
            return
            
        self.config_path = config_path or "/home/ubuntu/financial_orchestrator/configs/data_lab_config.yaml"
        self.config = self._load_config()
        
        self.redis_config = self.config.get('data_lab', {}).get('redis', {})
        self.streams_config = self.config.get('data_lab', {}).get('streams', {})
        
        self.redis_client = None
        self.connected = False
        
        self.backpressure = BackpressureController()
        self._event_counters: Dict[str, int] = {}
        self._last_alert_time: Dict[str, float] = {}
        self._alert_cooldown = 60
        
        self._in_memory_fallback: Dict[str, deque] = {}
        self._use_fallback = False
        
        self._initialize()
        self._initialized = True
        
    def _load_config(self) -> Dict:
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}")
            return {'data_lab': {'redis': {}, 'streams': {}}}
    
    def _initialize(self):
        """Initialize Redis connection and streams"""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, using in-memory fallback")
            self._use_fallback = True
            self._init_fallback_streams()
            return
            
        try:
            self.redis_client = redis.Redis(
                host=self.redis_config.get('host', 'localhost'),
                port=self.redis_config.get('port', 6379),
                db=self.redis_config.get('db', 0),
                decode_responses=True,
                socket_timeout=self.redis_config.get('socket_timeout', 5),
                socket_connect_timeout=self.redis_config.get('socket_connect_timeout', 5),
                max_connections=self.redis_config.get('max_connections', 50)
            )
            
            self.redis_client.ping()
            self.connected = True
            logger.info(f"Redis connected at {self.redis_config.get('host')}:{self.redis_config.get('port')}")
            
            self._init_streams()
            
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using in-memory fallback")
            self._use_fallback = True
            self._init_fallback_streams()
    
    def _init_streams(self):
        """Initialize Redis streams"""
        for stream_name, stream_config in self.streams_config.items():
            try:
                max_length = stream_config.get('max_length', 10000)
                self.backpressure.register_stream(stream_name, max_length)
                
                consumer_group = stream_config.get('consumer_group', 'data_lab')
                
                try:
                    self.redis_client.xgroup_create(
                        stream_name, consumer_group, id='0', mkstream=True
                    )
                except redis.exceptions.ResponseError as e:
                    if "BUSYGROUP" not in str(e):
                        raise
                        
                logger.info(f"Stream initialized: {stream_name}")
                
            except Exception as e:
                logger.error(f"Failed to init stream {stream_name}: {e}")
    
    def _init_fallback_streams(self):
        """Initialize in-memory fallback streams"""
        for stream_name, stream_config in self.streams_config.items():
            max_length = stream_config.get('max_length', 10000)
            self.backpressure.register_stream(stream_name, max_length)
            self._in_memory_fallback[stream_name] = deque(maxlen=max_length)
            
        logger.info("In-memory fallback streams initialized")
    
    def _get_priority(self, priority_str: str) -> EventPriority:
        priority_map = {
            'critical': EventPriority.CRITICAL,
            'high': EventPriority.HIGH,
            'normal': EventPriority.NORMAL,
            'low': EventPriority.LOW
        }
        return priority_map.get(priority_str.lower(), EventPriority.NORMAL)
    
    def publish_event(
        self,
        stream_name: str,
        data: Dict[str, Any],
        priority: str = "normal",
        source: str = "unknown",
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """Publish an event to a stream with backpressure control"""
        
        event_id = None
        
        priority_enum = self._get_priority(priority)
        
        event_data = {
            'data': json.dumps(data),
            'priority': priority,
            'source': source,
            'timestamp': time.time(),
            'metadata': json.dumps(metadata or {}),
            'priority_value': priority_enum.value
        }
        
        if self._use_fallback:
            event_id = self._publish_fallback(stream_name, event_data)
        else:
            try:
                if self.connected:
                    event_id = self.redis_client.xadd(
                        stream_name,
                        event_data,
                        maxlen=self.streams_config.get(stream_name, {}).get('max_length', 10000),
                        approximate=True
                    )
                    
                    stream_length = self.redis_client.xlen(stream_name)
                    bp_result = self.backpressure.check_backpressure(stream_name, stream_length)
                    
                    if bp_result['status'] != 'ok':
                        self._handle_backpressure(bp_result)
                        
                else:
                    event_id = self._publish_fallback(stream_name, event_data)
                    
            except Exception as e:
                logger.error(f"Failed to publish to Redis: {e}")
                self.connected = False
                event_id = self._publish_fallback(stream_name, event_data)
        
        self._event_counters[stream_name] = self._event_counters.get(stream_name, 0) + 1
        
        return event_id
    
    def _publish_fallback(self, stream_name: str, event_data: Dict) -> str:
        """Publish to in-memory fallback"""
        queue = self._in_memory_fallback.get(stream_name)
        if queue:
            if len(queue) >= queue.maxlen:
                queue.popleft()
            event_id = f"fallback-{time.time()}-{len(queue)}"
            event_data['id'] = event_id
            queue.append(event_data)
        return event_id
    
    def _handle_backpressure(self, bp_result: Dict):
        """Handle backpressure situation"""
        stream_name = bp_result['stream']
        current_length = bp_result['current_length']
        status = bp_result['status']
        
        if status == 'critical':
            drop_count = min(100, current_length - bp_result['max_length'] + 500)
            self._drop_events(stream_name, drop_count)
            
            logger.warning(f"Backpressure CRITICAL: {stream_name} at {bp_result['percent']:.1f}%")
    
    def _drop_events(self, stream_name: str, count: int):
        """Drop oldest low-priority events"""
        if self._use_fallback:
            queue = self._in_memory_fallback.get(stream_name)
            if queue:
                dropped = 0
                to_remove = []
                for i, event in enumerate(queue):
                    if event.get('priority') == 'low' and dropped < count:
                        to_remove.append(i)
                        dropped += 1
                
                for i in reversed(to_remove):
                    queue.remove(queue[i])
                    
                logger.info(f"Dropped {dropped} low-priority events from {stream_name}")
        else:
            try:
                drop_count = 0
                while drop_count < count:
                    result = self.redis_client.xread(
                        {stream_name: '0-0'},
                        count=10,
                        block=100
                    )
                    if not result:
                        break
                        
                    for stream, messages in result:
                        for msg_id, msg in messages:
                            if msg.get('priority') == 'low':
                                self.redis_client.xdel(stream_name, msg_id)
                                drop_count += 1
                            if drop_count >= count:
                                break
                                
                logger.info(f"Dropped {drop_count} low-priority events from {stream_name}")
                
            except Exception as e:
                logger.error(f"Failed to drop events: {e}")
    
    def consume_events(
        self,
        stream_name: str,
        consumer_name: str,
        count: int = 10,
        block_ms: int = 1000
    ) -> List[StreamEvent]:
        """Consume events from a stream"""
        events = []
        
        if self._use_fallback:
            queue = self._in_memory_fallback.get(stream_name, deque())
            for event in list(queue)[:count]:
                events.append(self._parse_fallback_event(event))
            return events
        
        try:
            if not self.connected:
                return events
                
            consumer_group = self.streams_config.get(stream_name, {}).get('consumer_group', 'data_lab')
            
            results = self.redis_client.xreadgroup(
                consumer_group,
                consumer_name,
                {stream_name: '>'},
                count=count,
                block=block_ms
            )
            
            for stream, messages in results:
                for msg_id, msg in messages:
                    event = StreamEvent(
                        id=msg_id,
                        stream=stream,
                        priority=self._get_priority(msg.get('priority', 'normal')),
                        data=json.loads(msg.get('data', '{}')),
                        timestamp=float(msg.get('time', time.time())),
                        metadata=json.loads(msg.get('metadata', '{}'))
                    )
                    events.append(event)
                    
        except Exception as e:
            logger.error(f"Failed to consume events: {e}")
            
        return events
    
    def _parse_fallback_event(self, event_data: Dict) -> StreamEvent:
        """Parse fallback event"""
        return StreamEvent(
            id=event_data.get('id', 'unknown'),
            stream='unknown',
            priority=self._get_priority(event_data.get('priority', 'normal')),
            data=json.loads(event_data.get('data', '{}')),
            timestamp=event_data.get('timestamp', time.time()),
            metadata=json.loads(event_data.get('metadata', '{}'))
        )
    
    def acknowledge_event(self, stream_name: str, event_id: str) -> bool:
        """Acknowledge a processed event"""
        if self._use_fallback:
            return True
            
        try:
            consumer_group = self.streams_config.get(stream_name, {}).get('consumer_group', 'data_lab')
            self.redis_client.xack(stream_name, consumer_group, event_id)
            return True
        except Exception as e:
            logger.error(f"Failed to ack event: {e}")
            return False
    
    def get_stream_length(self, stream_name: str) -> int:
        """Get current stream length"""
        if self._use_fallback:
            return len(self._in_memory_fallback.get(stream_name, deque()))
            
        try:
            if self.connected:
                return self.redis_client.xlen(stream_name)
        except Exception as e:
            logger.error(f"Failed to get stream length: {e}")
            
        return 0
    
    def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Get stream information"""
        length = self.get_stream_length(stream_name)
        config = self.streams_config.get(stream_name, {})
        max_length = config.get('max_length', 10000)
        
        return {
            'stream': stream_name,
            'length': length,
            'max_length': max_length,
            'utilization_percent': (length / max_length * 100) if max_length > 0 else 0,
            'connected': self.connected,
            'events_published': self._event_counters.get(stream_name, 0)
        }
    
    def get_all_stream_info(self) -> Dict[str, Dict]:
        """Get info for all streams"""
        return {
            stream_name: self.get_stream_info(stream_name)
            for stream_name in self.streams_config.keys()
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Check health of the stream manager"""
        return {
            'connected': self.connected,
            'using_fallback': self._use_fallback,
            'streams': self.get_all_stream_info(),
            'backpressure_enabled': self.backpressure.enabled
        }


def get_stream_manager(config_path: str = None) -> RedisStreamManager:
    """Get singleton instance of stream manager"""
    return RedisStreamManager(config_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = RedisStreamManager()
    
    print("Testing stream manager...")
    
    manager.publish_event(
        stream_name="market_data",
        data={"symbol": "BTCUSDT", "price": 45000.0, "volume": 100.5},
        priority="high",
        source="binance"
    )
    
    print(f"Health: {manager.health_check()}")
    print(f"Stream info: {manager.get_all_stream_info()}")
