"""
Shared State Layer
================
Redis + Filesystem integration for real-time state sharing
between VN.PY engine and Financial Orchestrator.
"""

import os
import json
import pickle
import time
import threading
import redis
from typing import Any, Dict, Optional
from pathlib import Path
from loguru import logger

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
RECONNECT_INTERVAL = 10
BACKUP_INTERVAL = 60

# Use configurable base path, fallback to user home if /vnpy is not writable
_VNPY_BASE = os.getenv("VNPY_BASE_PATH", "/home/ubuntu/vnpy")
_base_path = Path(_VNPY_BASE)

MEMORY_DIR = _base_path / "memory"
LOGS_DIR = _base_path / "logs"
MODELS_DIR = _base_path / "models"
STATE_BACKUP_DIR = MEMORY_DIR / "state_backups"

MEMORY_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)
STATE_BACKUP_DIR.mkdir(parents=True, exist_ok=True)


class SharedState:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._local_cache: Dict[str, Any] = {}
        self._reconnect_thread: Optional[threading.Thread] = None
        self._backup_thread: Optional[threading.Thread] = None
        self._running = False
        self._connect_redis()
        self._load_state_backup()
        self._start_reconnect_thread()
        self._start_backup_thread()
        
    def _connect_redis(self) -> bool:
        try:
            self.redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True
            )
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
            self._restore_from_redis()
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Using memory-only mode.")
            self.redis_client = None
            return False
    
    def _start_reconnect_thread(self):
        self._running = True
        self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
        self._reconnect_thread.start()
    
    def _reconnect_loop(self):
        while self._running:
            if not self.redis_client:
                logger.info("Attempting Redis reconnection...")
                if self._connect_redis():
                    logger.info("Redis reconnected successfully")
            time.sleep(RECONNECT_INTERVAL)
    
    def _start_backup_thread(self):
        self._backup_thread = threading.Thread(target=self._backup_loop, daemon=True)
        self._backup_thread.start()
    
    def _backup_loop(self):
        while self._running:
            time.sleep(BACKUP_INTERVAL)
            self._save_state_backup()
    
    def _save_state_backup(self):
        if not self._local_cache:
            return
        try:
            backup_file = STATE_BACKUP_DIR / f"state_backup_{int(time.time())}.json"
            with open(backup_file, 'w') as f:
                json.dump(self._local_cache, f)
            
            for old_backup in STATE_BACKUP_DIR.glob("state_backup_*.json"):
                if old_backup.name != backup_file.name:
                    try:
                        old_backup.unlink()
                    except Exception:
                        pass
            logger.debug(f"State backup saved: {backup_file.name}")
        except Exception as e:
            logger.error(f"Failed to save state backup: {e}")
    
    def _load_state_backup(self):
        try:
            backups = sorted(STATE_BACKUP_DIR.glob("state_backup_*.json"), reverse=True)
            if backups:
                latest = backups[0]
                with open(latest, 'r') as f:
                    self._local_cache = json.load(f)
                logger.info(f"State backup loaded from {latest.name}")
        except Exception as e:
            logger.warning(f"Failed to load state backup: {e}")
            self._local_cache = {}
    
    def _restore_from_redis(self):
        if not self.redis_client:
            return
        try:
            for key in self.redis_client.keys("state:*"):
                value = self.redis_client.get(key)
                if value:
                    try:
                        self._local_cache[key] = json.loads(value)
                    except json.JSONDecodeError:
                        self._local_cache[key] = value
            logger.info(f"Restored {len(self._local_cache)} states from Redis")
        except Exception as e:
            logger.error(f"Failed to restore from Redis: {e}")
    
    def set_position(self, symbol: str, position: Dict[str, Any]):
        key = f"position:{symbol}"
        self._redis_set(key, position)
        logger.debug(f"Position updated: {symbol} = {position}")
    
    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = f"position:{symbol}"
        return self._redis_get(key)
    
    def get_all_positions(self) -> Dict[str, Dict[str, Any]]:
        positions = {}
        if not self.redis_client:
            return positions
        for key in self.redis_client.keys("position:*"):
            symbol = key.replace("position:", "")
            positions[symbol] = self._redis_get(key)
        return positions
    
    def set_order(self, order_id: str, order_data: Dict[str, Any]):
        key = f"order:{order_id}"
        self._redis_set(key, order_data)
    
    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        key = f"order:{order_id}"
        return self._redis_get(key)
    
    def set_pnl(self, session_id: str, pnl_data: Dict[str, Any]):
        key = f"pnl:{session_id}"
        self._redis_set(key, pnl_data)
    
    def get_pnl(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = f"pnl:{session_id}"
        return self._redis_get(key)
    
    def set_signal(self, symbol: str, signal: Dict[str, Any]):
        key = f"signal:{symbol}"
        self._redis_set(key, signal)
        logger.info(f"Signal set: {symbol} = {signal}")
    
    def get_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        key = f"signal:{symbol}"
        return self._redis_get(key)
    
    def set_risk_limits(self, limits: Dict[str, Any]):
        key = "risk:limits"
        self._redis_set(key, limits)
    
    def get_risk_limits(self) -> Dict[str, Any]:
        return self._redis_get("risk:limits") or {}
    
    def log_rl_decision(self, decision: Dict[str, Any]):
        key = f"rl:decision:{decision.get('timestamp', 0)}"
        self._redis_set(key, decision)
        logger.info(f"RL Decision logged: {decision.get('action')}")
    
    def set_system_status(self, component: str, status: Dict[str, Any]):
        key = f"status:{component}"
        self._redis_set(key, status)
    
    def get_system_status(self, component: str) -> Dict[str, Any]:
        return self._redis_get(f"status:{component}") or {"status": "unknown"}
    
    def publish_event(self, channel: str, message: Dict[str, Any]):
        if self.redis_client:
            self.redis_client.publish(channel, json.dumps(message))
    
    def subscribe(self, channel: str):
        if self.redis_client:
            return self.redis_client.pubsub()
        return None
    
    def save_checkpoint(self, name: str, data: Any) -> bool:
        filepath = MEMORY_DIR / f"{name}.pkl"
        try:
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            logger.info(f"Checkpoint saved: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to save checkpoint {name}: {e}")
            return False
    
    def load_checkpoint(self, name: str) -> Optional[Any]:
        filepath = MEMORY_DIR / f"{name}.pkl"
        if not filepath.exists():
            logger.warning(f"Checkpoint not found: {filepath}")
            return None
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            logger.info(f"Checkpoint loaded: {filepath}")
            return data
        except Exception as e:
            logger.error(f"Failed to load checkpoint {name}: {e}")
            return None
    
    def append_log(self, filename: str, message: str):
        filepath = LOGS_DIR / filename
        try:
            with open(filepath, 'a') as f:
                f.write(f"{message}\n")
        except Exception as e:
            logger.error(f"Failed to write log: {e}")
    
    def _redis_set(self, key: str, value: Any):
        if self.redis_client:
            try:
                serialized = json.dumps(value) if isinstance(value, (dict, list)) else value
                self.redis_client.set(key, serialized)
            except Exception as e:
                logger.error(f"Redis set failed for {key}: {e}")
        
        self._local_cache[key] = value
    
    def _redis_get(self, key: str) -> Any:
        if key in self._local_cache:
            return self._local_cache[key]
        
        if not self.redis_client:
            return None
        try:
            value = self.redis_client.get(key)
            if value:
                try:
                    result = json.loads(value)
                    self._local_cache[key] = result
                    return result
                except json.JSONDecodeError:
                    self._local_cache[key] = value
                    return value
            return None
        except Exception as e:
            logger.error(f"Redis get failed for {key}: {e}")
            return None
    
    def health_check(self) -> bool:
        if self.redis_client:
            try:
                self.redis_client.ping()
                return True
            except:
                return False
        return False


shared_state = SharedState()
