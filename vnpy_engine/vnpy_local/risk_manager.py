"""
Risk Manager Module
===================
Position limits, drawdown protection, and risk controls.
"""

import os
import time
from typing import Dict, Any, Optional
from loguru import logger


class RiskManager:
    def __init__(self):
        self.max_position_size = int(os.getenv("MAX_POSITION_SIZE", "10"))
        self.max_daily_loss = float(os.getenv("MAX_DAILY_LOSS", "1000"))
        self.max_drawdown_pct = float(os.getenv("MAX_DRAWDOWN_PCT", "20"))
        
        self.daily_pnl = 0.0
        self.session_start = time.time()
        self.peak_equity = 0.0
        self.current_equity = 10000.0
        
    def check_position_limit(self, symbol: str, current_size: float, 
                            new_size: float) -> bool:
        if abs(new_size) > self.max_position_size:
            logger.warning(f"Position limit exceeded for {symbol}: {new_size}")
            return False
        return True
    
    def check_daily_loss(self, pnl: float) -> bool:
        self.daily_pnl += pnl
        
        if self.daily_pnl <= -self.max_daily_loss:
            logger.critical(f"Daily loss limit reached: {self.daily_pnl}")
            return False
        return True
    
    def check_drawdown(self) -> bool:
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
        
        if self.peak_equity > 0:
            drawdown_pct = (self.peak_equity - self.current_equity) / self.peak_equity * 100
            
            if drawdown_pct >= self.max_drawdown_pct:
                logger.critical(f"Max drawdown reached: {drawdown_pct:.2f}%")
                return False
        return True
    
    def update_equity(self, equity: float):
        self.current_equity = equity
        if self.current_equity > self.peak_equity:
            self.peak_equity = self.current_equity
    
    def validate_order(self, symbol: str, action: str, size: float,
                      current_positions: Dict[str, Any],
                      current_price: float = 0) -> Dict[str, Any]:
        current_size = current_positions.get(symbol, {}).get("size", 0)
        
        if action == "buy":
            new_size = current_size + size
        elif action == "sell":
            new_size = current_size - size
        else:
            new_size = current_size
        
        if not self.check_position_limit(symbol, current_size, new_size):
            return {"allowed": False, "reason": "position_limit_exceeded"}
        
        adverse_move_pct = 0.01
        if current_price > 0:
            adverse_move_pct = min(0.02, max(0.005, 0.001))
        
        estimated_pnl = -size * current_price * adverse_move_pct if current_price > 0 else -size * 100
        if not self.check_daily_loss(estimated_pnl):
            return {"allowed": False, "reason": "daily_loss_limit"}
        
        if not self.check_drawdown():
            return {"allowed": False, "reason": "max_drawdown_reached"}
        
        return {"allowed": True}
    
    def reset_daily(self):
        self.daily_pnl = 0.0
        self.session_start = time.time()
    
    def get_risk_status(self) -> Dict[str, Any]:
        return {
            "max_position_size": self.max_position_size,
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown_pct": self.max_drawdown_pct,
            "daily_pnl": self.daily_pnl,
            "current_equity": self.current_equity,
            "peak_equity": self.peak_equity,
            "session_duration": time.time() - self.session_start
        }


risk_manager = RiskManager()
