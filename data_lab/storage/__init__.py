#!/usr/bin/env python3
"""
Data Storage
DuckDB-based storage for market data
"""

from .duckdb_manager import (
    DuckDBManager,
    get_duckdb_manager,
    TickRecord,
    KlineRecord
)

__all__ = [
    'DuckDBManager',
    'get_duckdb_manager',
    'TickRecord',
    'KlineRecord'
]
