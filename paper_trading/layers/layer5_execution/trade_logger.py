"""
Trade Logger
============
Redis-based trade logging for PnL tracking.
Real-time trade capture with async write-through to Redis.

Features:
- Position tracking (open positions with unrealized PnL)
- Trade history (closed trades with realized PnL)
- Daily PnL aggregation
- Cumulative PnL tracking
"""

import json
import time
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime, date
from loguru import logger

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class TradeLogger:
    """
    Centralized trade logging with Redis backend.
    Thread-safe for concurrent order processing.
    """
    
    PREFIX = "trade_logger"
    
    # Redis key patterns
    KEY_OPEN_POSITIONS = f"{PREFIX}:positions:open"
    KEY_TRADE_HISTORY = f"{PREFIX}:trades:history"
    KEY_DAILY_PNL = f"{PREFIX}:pnl:daily"
    KEY_CUMULATIVE_PNL = f"{PREFIX}:pnl:cumulative"
    KEY_DAILY_STATS = f"{PREFIX}:stats:daily"
    KEY_TRADE_COUNT = f"{PREFIX}:count:trades"
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379):
        self.redis_client: Optional[redis.Redis] = None
        self._local_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    decode_responses=True,
                    socket_connect_timeout=5,
                )
                self.redis_client.ping()
                logger.info("TradeLogger connected to Redis")
            except Exception as e:
                logger.warning(f"TradeLogger Redis connection failed: {e}, using in-memory mode")
                self.redis_client = None
        else:
            logger.warning("Redis not available, TradeLogger using in-memory mode")
            self.redis_client = None
        
        self._init_counters()
    
    def _init_counters(self):
        """Initialize counters from Redis or use defaults"""
        if self.redis_client:
            try:
                if not self.redis_client.exists(self.KEY_TRADE_COUNT):
                    self.redis_client.set(self.KEY_TRADE_COUNT, 0)
                if not self.redis_client.exists(self.KEY_CUMULATIVE_PNL):
                    self.redis_client.set(self.KEY_CUMULATIVE_PNL, "0.0")
            except Exception as e:
                logger.warning(f"Failed to initialize counters: {e}")
    
    def _get_date_key(self, dt: Optional[date] = None) -> str:
        """Get date string for daily keys"""
        dt = dt or date.today()
        return dt.strftime("%Y-%m-%d")
    
    # ─── Position Tracking ───────────────────────────────────────────────
    
    def log_open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        order_id: str,
        strategy: str = "unknown",
        leverage: int = 1,
    ) -> bool:
        """
        Log an opening position (long or short).
        Returns True on success.
        """
        try:
            position_data = {
                "symbol": symbol.upper(),
                "side": side.lower(),
                "quantity": quantity,
                "entry_price": entry_price,
                "order_id": order_id,
                "strategy": strategy,
                "leverage": leverage,
                "opened_at": datetime.now().isoformat(),
                "unrealized_pnl": 0.0,
            }
            
            with self._lock:
                if self.redis_client:
                    self.redis_client.hset(
                        self.KEY_OPEN_POSITIONS,
                        symbol.upper(),
                        json.dumps(position_data)
                    )
                else:
                    self._local_cache[f"position_{symbol.upper()}"] = position_data
            
            logger.info(
                f"Position opened: {side.upper()} {symbol} {quantity} @ {entry_price} "
                f"(order_id={order_id})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to log open position: {e}")
            return False
    
    def log_close_position(
        self,
        symbol: str,
        exit_price: float,
        quantity: float,
        side: str,
        pnl: float,
        fees: float = 0.0,
        order_id: str = "",
        strategy: str = "unknown",
    ) -> bool:
        """
        Log a closing trade with realized PnL.
        Returns True on success.
        """
        try:
            with self._lock:
                # Get opening position data
                entry_data = self._get_open_position(symbol)
                entry_price = entry_data.get("entry_price", 0) if entry_data else 0
                
                trade_data = {
                    "symbol": symbol.upper(),
                    "side": side.lower(),
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "fees": fees,
                    "order_id": order_id,
                    "strategy": strategy,
                    "opened_at": entry_data.get("opened_at", ""),
                    "closed_at": datetime.now().isoformat(),
                }
                
                # Store in trade history
                if self.redis_client:
                    trade_key = f"{self.KEY_TRADE_HISTORY}:{symbol.upper()}"
                    self.redis_client.rpush(trade_key, json.dumps(trade_data))
                    
                    # Update daily PnL
                    self._update_daily_pnl(pnl)
                    
                    # Update cumulative PnL
                    current = float(self.redis_client.get(self.KEY_CUMULATIVE_PNL) or 0)
                    self.redis_client.set(self.KEY_CUMULATIVE_PNL, str(current + pnl))
                    
                    # Update trade count
                    self.redis_client.incr(self.KEY_TRADE_COUNT)
                    
                    # Update daily stats
                    self._update_daily_stats(pnl)
                    
                    # Remove open position
                    self.redis_client.hdel(self.KEY_OPEN_POSITIONS, symbol.upper())
                else:
                    self._local_cache[f"trade_{symbol.upper()}_{int(time.time())}"] = trade_data
                    self._local_cache.pop(f"position_{symbol.upper()}", None)
            
            pnl_str = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
            logger.info(
                f"Position closed: {side.upper()} {symbol} {quantity} @ {exit_price} "
                f"PnL: {pnl_str} (order_id={order_id})"
            )
            return True
            
        except Exception as e:
            logger.error(f"Failed to log close position: {e}")
            return False
    
    def update_unrealized_pnl(self, symbol: str, current_price: float) -> float:
        """
        Update unrealized PnL for an open position.
        Returns the unrealized PnL value.
        """
        try:
            with self._lock:
                position = self._get_open_position(symbol)
                if not position:
                    return 0.0
                
                entry_price = float(position.get("entry_price", 0))
                quantity = float(position.get("quantity", 0))
                side = position.get("side", "long")
                leverage = float(position.get("leverage", 1))
                
                if side == "long":
                    pnl = (current_price - entry_price) * quantity * leverage
                else:
                    pnl = (entry_price - current_price) * quantity * leverage
                
                position["unrealized_pnl"] = pnl
                position["current_price"] = current_price
                
                if self.redis_client:
                    self.redis_client.hset(
                        self.KEY_OPEN_POSITIONS,
                        symbol.upper(),
                        json.dumps(position)
                    )
                else:
                    self._local_cache[f"position_{symbol.upper()}"] = position
                
                return pnl
                
        except Exception as e:
            logger.error(f"Failed to update unrealized PnL: {e}")
            return 0.0
    
    def _get_open_position(self, symbol: str) -> Optional[Dict]:
        """Get open position data for a symbol"""
        if self.redis_client:
            data = self.redis_client.hget(self.KEY_OPEN_POSITIONS, symbol.upper())
            if data:
                return json.loads(data)
        else:
            return self._local_cache.get(f"position_{symbol.upper()}")
        return None
    
    # ─── PnL Queries ───────────────────────────────────────────────────────
    
    def get_open_positions(self) -> List[Dict]:
        """Get all open positions with unrealized PnL"""
        positions = []
        
        if self.redis_client:
            all_positions = self.redis_client.hgetall(self.KEY_OPEN_POSITIONS)
            for symbol, data in all_positions.items():
                positions.append(json.loads(data))
        else:
            for key, data in self._local_cache.items():
                if key.startswith("position_"):
                    positions.append(data)
        
        return positions
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized PnL across all open positions"""
        total = 0.0
        for pos in self.get_open_positions():
            total += float(pos.get("unrealized_pnl", 0))
        return total
    
    def get_cumulative_pnl(self) -> float:
        """Get cumulative realized PnL"""
        if self.redis_client:
            return float(self.redis_client.get(self.KEY_CUMULATIVE_PNL) or 0)
        return 0.0
    
    def get_daily_pnl(self, target_date: Optional[date] = None) -> Dict:
        """Get daily PnL and stats"""
        target_date = target_date or date.today()
        date_key = self._get_date_key(target_date)
        
        stats_key = f"{self.KEY_DAILY_STATS}:{date_key}"
        
        if self.redis_client:
            data = self.redis_client.get(stats_key)
            if data:
                return json.loads(data)
        
        return {
            "date": date_key,
            "total_pnl": 0.0,
            "trade_count": 0,
            "win_count": 0,
            "loss_count": 0,
            "win_rate": 0.0,
        }
    
    def _update_daily_pnl(self, pnl: float):
        """Update daily PnL in Redis"""
        date_key = self._get_date_key()
        pnl_key = f"{self.KEY_DAILY_PNL}:{date_key}"
        
        current = float(self.redis_client.get(pnl_key) or 0)
        self.redis_client.set(pnl_key, str(current + pnl))
    
    def _update_daily_stats(self, pnl: float):
        """Update daily trading statistics"""
        date_key = self._get_date_key()
        stats_key = f"{self.KEY_DAILY_STATS}:{date_key}"
        
        if self.redis_client.exists(stats_key):
            stats = json.loads(self.redis_client.get(stats_key))
        else:
            stats = {
                "date": date_key,
                "total_pnl": 0.0,
                "trade_count": 0,
                "win_count": 0,
                "loss_count": 0,
            }
        
        stats["total_pnl"] += pnl
        stats["trade_count"] += 1
        if pnl > 0:
            stats["win_count"] += 1
        elif pnl < 0:
            stats["loss_count"] += 1
        
        if stats["trade_count"] > 0:
            stats["win_rate"] = stats["win_count"] / stats["trade_count"] * 100
        else:
            stats["win_rate"] = 0.0
        
        self.redis_client.set(stats_key, json.dumps(stats))
    
    # ─── Trade History ──────────────────────────────────────────────────────
    
    def get_recent_trades(self, limit: int = 50, symbol: str = None) -> List[Dict]:
        """Get recent closed trades"""
        trades = []
        
        if symbol:
            trade_key = f"{self.KEY_TRADE_HISTORY}:{symbol.upper()}"
        else:
            trade_key = f"{self.KEY_TRADE_HISTORY}"
        
        if self.redis_client:
            if symbol:
                trade_data = self.redis_client.lrange(trade_key, -limit, -1)
            else:
                # Get from all symbols
                all_keys = self.redis_client.keys(f"{self.KEY_TRADE_HISTORY}:*")
                for key in all_keys:
                    trade_data = self.redis_client.lrange(key, -limit, -1)
                    for t in trade_data:
                        trades.append(json.loads(t))
                return trades
        
        for data in (trade_data or []):
            trades.append(json.loads(data))
        
        return trades[-limit:]
    
    def get_trade_count(self) -> int:
        """Get total number of closed trades"""
        if self.redis_client:
            return int(self.redis_client.get(self.KEY_TRADE_COUNT) or 0)
        return 0
    
    # ─── Summary ───────────────────────────────────────────────────────────
    
    def get_pnl_summary(self) -> Dict:
        """Get complete PnL summary"""
        return {
            "daily": self.get_daily_pnl(),
            "cumulative": self.get_cumulative_pnl(),
            "unrealized": self.get_unrealized_pnl(),
            "open_positions": self.get_open_positions(),
            "trade_count": self.get_trade_count(),
            "metrics": self.get_risk_metrics(),
        }
    
    # ─── Risk Metrics ─────────────────────────────────────────────────────
    
    def get_risk_metrics(self) -> Dict[str, Any]:
        """Calculate comprehensive risk metrics"""
        trades = self.get_recent_trades(limit=500)
        
        if not trades or len(trades) < 2:
            return self._default_metrics()
        
        returns = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) != 0]
        
        if not returns:
            return self._default_metrics()
        
        cumulative_pnl = self.get_cumulative_pnl()
        
        returns_arr = returns
        avg_return = sum(returns_arr) / len(returns_arr)
        
        variance = sum((r - avg_return) ** 2 for r in returns_arr) / len(returns_arr)
        std_dev = variance ** 0.5
        
        downside_returns = [r for r in returns_arr if r < 0]
        downside_dev = 0
        if downside_returns:
            downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_dev = downside_var ** 0.5
        
        sharpe_ratio = (avg_return / std_dev * (252 ** 0.5)) if std_dev > 0 else 0
        sortino_ratio = (avg_return / downside_dev * (252 ** 0.5)) if downside_dev > 0 else 0
        
        max_dd = self._calculate_max_drawdown(returns_arr)
        
        gross_profit = sum(r for r in returns_arr if r > 0)
        gross_loss = abs(sum(r for r in returns_arr if r < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        calmar_ratio = (cumulative_pnl / abs(max_dd)) if max_dd != 0 else 0
        
        win_count = sum(1 for r in returns_arr if r > 0)
        loss_count = sum(1 for r in returns_arr if r < 0)
        win_rate = (win_count / len(returns_arr) * 100) if returns_arr else 0
        
        return {
            "sharpe_ratio": round(sharpe_ratio, 2),
            "sortino_ratio": round(sortino_ratio, 2),
            "max_drawdown": round(max_dd, 2),
            "profit_factor": round(profit_factor, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "win_rate": round(win_rate, 2),
            "total_trades": len(returns_arr),
            "winning_trades": win_count,
            "losing_trades": loss_count,
            "avg_win": round(gross_profit / win_count, 2) if win_count > 0 else 0,
            "avg_loss": round(gross_loss / loss_count, 2) if loss_count > 0 else 0,
            "avg_pnl_per_trade": round(avg_return, 2),
            "volatility": round(std_dev, 2),
        }
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """Calculate maximum drawdown"""
        if not returns:
            return 0.0
        
        running_pnl = 0.0
        peak = 0.0
        max_dd = 0.0
        
        for r in returns:
            running_pnl += r
            if running_pnl > peak:
                peak = running_pnl
            dd = peak - running_pnl
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _default_metrics(self) -> Dict[str, Any]:
        """Return default metrics when insufficient data"""
        return {
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "calmar_ratio": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "avg_pnl_per_trade": 0.0,
            "volatility": 0.0,
        }
    
    # ─── Maintenance ───────────────────────────────────────────────────────
    
    def clear_positions(self):
        """Clear all positions (for testing)"""
        with self._lock:
            if self.redis_client:
                self.redis_client.delete(self.KEY_OPEN_POSITIONS)
            self._local_cache = {}


# Singleton instance
_trade_logger: Optional[TradeLogger] = None


def get_trade_logger() -> TradeLogger:
    """Get singleton TradeLogger instance"""
    global _trade_logger
    if _trade_logger is None:
        _trade_logger = TradeLogger()
    return _trade_logger
