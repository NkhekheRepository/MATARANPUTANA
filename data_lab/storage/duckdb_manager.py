#!/usr/bin/env python3
"""
DuckDB Storage Manager
Efficient storage for ticks and OHLCV data
"""

import os
import sys
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import contextmanager

sys.path.insert(0, '/home/ubuntu/financial_orchestrator')

logger = logging.getLogger('DuckDBManager')

try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False
    logger.warning("DuckDB not available")


@dataclass
class TickRecord:
    """Tick data record for storage"""
    symbol: str
    price: float
    volume: float
    bid: float
    ask: float
    timestamp: float
    source: str
    sequence: int


@dataclass
class KlineRecord:
    """OHLCV record for storage"""
    symbol: str
    interval: str
    open_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: int
    quote_volume: float
    trades: int
    source: str


class DuckDBManager:
    """
    Manages DuckDB database for market data storage.
    Stores ticks and OHLCV data efficiently.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
            
        if not DUCKDB_AVAILABLE:
            logger.error("DuckDB not available")
            self._initialized = False
            return
        
        self.db_path = db_path or "/home/ubuntu/financial_orchestrator/data_lab/market_data.duckdb"
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.conn = None
        self._write_lock = threading.Lock()
        self._batch_buffer: List[TickRecord] = []
        self._batch_size = 100
        self._batch_thread: Optional[threading.Thread] = None
        self._running = False
        
        self._initialize()
        self._initialized = True
    
    def _initialize(self):
        """Initialize database and create tables"""
        try:
            self.conn = duckdb.connect(self.db_path, read_only=False)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS ticks (
                    id INTEGER PRIMARY KEY,
                    symbol VARCHAR,
                    price DOUBLE,
                    volume DOUBLE,
                    bid DOUBLE,
                    ask DOUBLE,
                    timestamp DOUBLE,
                    source VARCHAR,
                    sequence INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticks_symbol ON ticks(symbol)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ticks_timestamp ON ticks(timestamp)
            """)
            
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS klines (
                    id INTEGER PRIMARY KEY,
                    symbol VARCHAR,
                    interval VARCHAR,
                    open_time BIGINT,
                    open DOUBLE,
                    high DOUBLE,
                    low DOUBLE,
                    close DOUBLE,
                    volume DOUBLE,
                    close_time BIGINT,
                    quote_volume DOUBLE,
                    trades INTEGER,
                    source VARCHAR,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, interval, open_time)
                )
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_klines_symbol ON klines(symbol)
            """)
            
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_klines_time ON klines(open_time)
            """)
            
            logger.info(f"DuckDB initialized: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize DuckDB: {e}")
            raise
    
    @contextmanager
    def _transaction(self):
        """Context manager for transactions"""
        with self._write_lock:
            yield self.conn
    
    def insert_tick(self, tick: TickRecord):
        """Insert a single tick"""
        try:
            with self._transaction():
                self.conn.execute("""
                    INSERT INTO ticks (symbol, price, volume, bid, ask, timestamp, source, sequence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    tick.symbol, tick.price, tick.volume, tick.bid, tick.ask,
                    tick.timestamp, tick.source, tick.sequence
                ])
        except Exception as e:
            logger.error(f"Failed to insert tick: {e}")
    
    def insert_tick_batch(self, ticks: List[TickRecord]):
        """Insert multiple ticks in batch"""
        if not ticks:
            return
            
        try:
            with self._transaction():
                data = [
                    (t.symbol, t.price, t.volume, t.bid, t.ask, t.timestamp, t.source, t.sequence)
                    for t in ticks
                ]
                self.conn.executemany("""
                    INSERT INTO ticks (symbol, price, volume, bid, ask, timestamp, source, sequence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, data)
                
        except Exception as e:
            logger.error(f"Failed to insert tick batch: {e}")
    
    def insert_kline(self, kline: KlineRecord):
        """Insert a kline (OHLCV)"""
        try:
            with self._transaction():
                self.conn.execute("""
                    INSERT OR REPLACE INTO klines 
                    (symbol, interval, open_time, open, high, low, close, volume, close_time, quote_volume, trades, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    kline.symbol, kline.interval, kline.open_time, kline.open,
                    kline.high, kline.low, kline.close, kline.volume, kline.close_time,
                    kline.quote_volume, kline.trades, kline.source
                ])
        except Exception as e:
            logger.error(f"Failed to insert kline: {e}")
    
    def get_recent_ticks(
        self,
        symbol: str,
        limit: int = 100,
        since: Optional[float] = None
    ) -> List[Dict]:
        """Get recent ticks for a symbol"""
        try:
            if since:
                result = self.conn.execute("""
                    SELECT symbol, price, volume, bid, ask, timestamp, source, sequence
                    FROM ticks
                    WHERE symbol = ? AND timestamp > ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, [symbol.upper(), since, limit]).fetchall()
            else:
                result = self.conn.execute("""
                    SELECT symbol, price, volume, bid, ask, timestamp, source, sequence
                    FROM ticks
                    WHERE symbol = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, [symbol.upper(), limit]).fetchall()
            
            return [
                {
                    'symbol': r[0],
                    'price': r[1],
                    'volume': r[2],
                    'bid': r[3],
                    'ask': r[4],
                    'timestamp': r[5],
                    'source': r[6],
                    'sequence': r[7]
                }
                for r in result
            ]
            
        except Exception as e:
            logger.error(f"Failed to get ticks: {e}")
            return []
    
    def get_klines(
        self,
        symbol: str,
        interval: str = "1m",
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get klines for a symbol"""
        try:
            if start_time and end_time:
                result = self.conn.execute("""
                    SELECT symbol, interval, open_time, open, high, low, close, volume, close_time, quote_volume, trades, source
                    FROM klines
                    WHERE symbol = ? AND interval = ? AND open_time >= ? AND open_time <= ?
                    ORDER BY open_time DESC
                    LIMIT ?
                """, [symbol.upper(), interval, start_time, end_time, limit]).fetchall()
            else:
                result = self.conn.execute("""
                    SELECT symbol, interval, open_time, open, high, low, close, volume, close_time, quote_volume, trades, source
                    FROM klines
                    WHERE symbol = ? AND interval = ?
                    ORDER BY open_time DESC
                    LIMIT ?
                """, [symbol.upper(), interval, limit]).fetchall()
            
            return [
                {
                    'symbol': r[0],
                    'interval': r[1],
                    'open_time': r[2],
                    'open': r[3],
                    'high': r[4],
                    'low': r[5],
                    'close': r[6],
                    'volume': r[7],
                    'close_time': r[8],
                    'quote_volume': r[9],
                    'trades': r[10],
                    'source': r[11]
                }
                for r in result
            ]
            
        except Exception as e:
            logger.error(f"Failed to get klines: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            tick_count = self.conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
            kline_count = self.conn.execute("SELECT COUNT(*) FROM klines").fetchone()[0]
            
            symbols = self.conn.execute("SELECT DISTINCT symbol FROM ticks").fetchall()
            
            return {
                'tick_count': tick_count,
                'kline_count': kline_count,
                'tracked_symbols': [s[0] for s in symbols],
                'db_path': self.db_path,
                'file_size_mb': os.path.getsize(self.db_path) / 1024 / 1024 if os.path.exists(self.db_path) else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def cleanup_old_data(self, retention_days: int = 30):
        """Delete old data beyond retention period"""
        try:
            cutoff = datetime.now() - timedelta(days=retention_days)
            cutoff_timestamp = cutoff.timestamp()
            
            with self._transaction():
                deleted_ticks = self.conn.execute("""
                    DELETE FROM ticks WHERE timestamp < ?
                """, [cutoff_timestamp]).rowcount
                
                deleted_klines = self.conn.execute("""
                    DELETE FROM klines WHERE open_time < ?
                """, [int(cutoff_timestamp * 1000)]).rowcount
                
            logger.info(f"Cleaned up {deleted_ticks} ticks and {deleted_klines} klines")
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("DuckDB connection closed")


def get_duckdb_manager(db_path: str = None) -> DuckDBManager:
    """Get singleton instance"""
    return DuckDBManager(db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    db = DuckDBManager("/tmp/test_market_data.duckdb")
    
    print(f"Stats: {db.get_stats()}")
    
    db.close()
