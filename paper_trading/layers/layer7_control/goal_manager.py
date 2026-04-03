"""
Layer 7: Goal Manager
Defines and tracks performance targets for the autonomous trading system.
Monitors progress toward goals and triggers appropriate actions.
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from loguru import logger

from ..event_bus import get_event_bus, EventType, publish_health_alert


class GoalStatus(Enum):
    """Status of a performance goal."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    ACHIEVED = "achieved"
    MISSED = "missed"
    DEGRADED = "degraded"


@dataclass
class PerformanceGoal:
    """Represents a single performance goal."""
    name: str
    target_value: float
    threshold_warning: float
    threshold_critical: float
    current_value: float = 0.0
    status: GoalStatus = GoalStatus.NOT_STARTED
    last_updated: float = field(default_factory=time.time)
    history: List[float] = field(default_factory=list)
    
    def update(self, value: float) -> GoalStatus:
        """Update goal with new value and return new status."""
        self.current_value = value
        self.last_updated = time.time()
        self.history.append(value)
        
        # Keep only last 100 values
        if len(self.history) > 100:
            self.history = self.history[-100:]
        
        # Determine status based on thresholds
        if value >= self.target_value:
            self.status = GoalStatus.ACHIEVED
        elif value >= self.threshold_warning:
            self.status = GoalStatus.IN_PROGRESS
        elif value >= self.threshold_critical:
            self.status = GoalStatus.DEGRADED
        else:
            self.status = GoalStatus.MISSED
        
        return self.status
    
    def get_progress(self) -> float:
        """Get progress as percentage (0-100)."""
        if self.target_value == 0:
            return 0.0
        return min(100.0, (self.current_value / self.target_value) * 100)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'target': self.target_value,
            'current': self.current_value,
            'status': self.status.value,
            'progress_pct': round(self.get_progress(), 1),
            'threshold_warning': self.threshold_warning,
            'threshold_critical': self.threshold_critical,
            'last_updated': self.last_updated,
            'history_length': len(self.history)
        }


class GoalManager:
    """
    Manages performance goals for the autonomous trading system.
    
    Goals tracked:
    1. Sharpe Ratio - Risk-adjusted returns
    2. Maximum Drawdown - Worst peak-to-trough decline
    3. Daily Return - Daily profit/loss percentage
    4. Win Rate - Percentage of winning trades
    5. Model Accuracy - ML prediction accuracy
    6. Calmar Ratio - Annual return / max drawdown
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        
        # Initialize performance goals from config
        goals_config = self.config.get('goals', {})
        self.goals: Dict[str, PerformanceGoal] = self._initialize_goals(goals_config)
        
        # Metrics buffer for computing goals
        self._returns_history: List[float] = []
        self._peak_capital: float = 0.0
        self._trade_results: List[float] = []
        self._capital_history: List[float] = []
        
        # Event bus
        self.event_bus = get_event_bus()
        
        logger.info(f"GoalManager initialized with {len(self.goals)} goals")
    
    def _initialize_goals(self, goals_config: Dict[str, Any]) -> Dict[str, PerformanceGoal]:
        """Initialize goals from configuration."""
        default_goals = {
            'sharpe_ratio': PerformanceGoal(
                name='sharpe_ratio',
                target_value=goals_config.get('sharpe_target', 1.5),
                threshold_warning=goals_config.get('sharpe_warning', 1.0),
                threshold_critical=goals_config.get('sharpe_critical', 0.5)
            ),
            'max_drawdown': PerformanceGoal(
                name='max_drawdown',
                target_value=goals_config.get('drawdown_target', -5.0),  # Negative is good
                threshold_warning=goals_config.get('drawdown_warning', -10.0),
                threshold_critical=goals_config.get('drawdown_critical', -20.0)
            ),
            'daily_return': PerformanceGoal(
                name='daily_return',
                target_value=goals_config.get('daily_return_target', 1.0),
                threshold_warning=goals_config.get('daily_return_warning', 0.5),
                threshold_critical=goals_config.get('daily_return_critical', 0.0)
            ),
            'win_rate': PerformanceGoal(
                name='win_rate',
                target_value=goals_config.get('win_rate_target', 55.0),
                threshold_warning=goals_config.get('win_rate_warning', 50.0),
                threshold_critical=goals_config.get('win_rate_critical', 45.0)
            ),
            'model_accuracy': PerformanceGoal(
                name='model_accuracy',
                target_value=goals_config.get('model_accuracy_target', 60.0),
                threshold_warning=goals_config.get('model_accuracy_warning', 55.0),
                threshold_critical=goals_config.get('model_accuracy_critical', 50.0)
            ),
            'calmar_ratio': PerformanceGoal(
                name='calmar_ratio',
                target_value=goals_config.get('calmar_target', 2.0),
                threshold_warning=goals_config.get('calmar_warning', 1.0),
                threshold_critical=goals_config.get('calmar_critical', 0.5)
            )
        }
        return default_goals
    
    def update_trade_result(self, pnl: float, capital: float):
        """Update goals with new trade result."""
        self._trade_results.append(pnl)
        self._capital_history.append(capital)
        
        # Keep history manageable
        if len(self._trade_results) > 1000:
            self._trade_results = self._trade_results[-500:]
        if len(self._capital_history) > 1000:
            self._capital_history = self._capital_history[-500:]
        
        # Update peak capital
        if capital > self._peak_capital:
            self._peak_capital = capital
        
        # Update win rate goal
        if len(self._trade_results) >= 10:
            self._update_win_rate()
        
        # Update daily return goal
        if len(self._capital_history) >= 2:
            self._update_daily_return()
    
    def update_model_accuracy(self, accuracy: float):
        """Update model accuracy goal."""
        if 'model_accuracy' in self.goals:
            status = self.goals['model_accuracy'].update(accuracy)
            
            if status in [GoalStatus.MISSED, GoalStatus.DEGRADED]:
                publish_health_alert(
                    component="model_accuracy",
                    status=f"Goal {status.value}: {accuracy:.1f}% (target: {self.goals['model_accuracy'].target_value}%)",
                    failure_count=1,
                    critical=(status == GoalStatus.MISSED)
                )
    
    def update_returns(self, returns: List[float]):
        """Update returns for Sharpe ratio calculation."""
        self._returns_history.extend(returns)
        if len(self._returns_history) > 500:
            self._returns_history = self._returns_history[-250:]
        
        if len(self._returns_history) >= 20:
            self._update_sharpe_ratio()
    
    def _update_win_rate(self):
        """Calculate and update win rate goal."""
        if not self._trade_results:
            return
        
        wins = sum(1 for r in self._trade_results if r > 0)
        win_rate = (wins / len(self._trade_results)) * 100
        
        self.goals['win_rate'].update(win_rate)
    
    def _update_daily_return(self):
        """Calculate and update daily return goal."""
        if len(self._capital_history) < 2:
            return
        
        daily_return = ((self._capital_history[-1] / self._capital_history[0]) - 1) * 100
        self.goals['daily_return'].update(daily_return)
    
    def _update_sharpe_ratio(self):
        """Calculate and update Sharpe ratio goal."""
        if len(self._returns_history) < 20:
            return
        
        import numpy as np
        
        returns = np.array(self._returns_history)
        excess_returns = returns - 0.02 / 252  # Assuming 2% annual risk-free rate
        
        if np.std(excess_returns) == 0:
            sharpe = 0.0
        else:
            sharpe = (np.mean(excess_returns) / np.std(excess_returns)) * np.sqrt(252)
        
        self.goals['sharpe_ratio'].update(sharpe)
    
    def update_max_drawdown(self, current_capital: float):
        """Update maximum drawdown goal."""
        if current_capital > self._peak_capital:
            self._peak_capital = current_capital
        
        if self._peak_capital > 0:
            drawdown = ((current_capital - self._peak_capital) / self._peak_capital) * 100
            self.goals['max_drawdown'].update(drawdown)
    
    def update_calmar_ratio(self, annual_return: float):
        """Update Calmar ratio goal."""
        if 'max_drawdown' in self.goals:
            max_dd = abs(self.goals['max_drawdown'].current_value)
            if max_dd > 0:
                calmar = annual_return / max_dd
                self.goals['calmar_ratio'].update(calmar)
    
    def get_goal_status(self, goal_name: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific goal."""
        if goal_name in self.goals:
            return self.goals[goal_name].to_dict()
        return None
    
    def get_all_goals_status(self) -> Dict[str, Any]:
        """Get status of all goals."""
        return {
            name: goal.to_dict() for name, goal in self.goals.items()
        }
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall goal health summary."""
        if not self.enabled:
            return {'enabled': False}
        
        status_counts = {
            GoalStatus.ACHIEVED: 0,
            GoalStatus.IN_PROGRESS: 0,
            GoalStatus.DEGRADED: 0,
            GoalStatus.MISSED: 0,
            GoalStatus.NOT_STARTED: 0
        }
        
        for goal in self.goals.values():
            status_counts[goal.status] += 1
        
        total_goals = len(self.goals)
        achieved_pct = (status_counts[GoalStatus.ACHIEVED] / total_goals * 100) if total_goals > 0 else 0
        
        # Determine overall health
        if status_counts[GoalStatus.MISSED] > total_goals / 2:
            overall = "critical"
        elif status_counts[GoalStatus.DEGRADED] + status_counts[GoalStatus.MISSED] > total_goals / 3:
            overall = "warning"
        elif achieved_pct > 50:
            overall = "healthy"
        else:
            overall = "neutral"
        
        return {
            'enabled': self.enabled,
            'overall_health': overall,
            'achieved_pct': round(achieved_pct, 1),
            'status_counts': {s.value: c for s, c in status_counts.items()},
            'goals': self.get_all_goals_status()
        }
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive goal report."""
        return {
            'enabled': self.enabled,
            'total_goals': len(self.goals),
            'goals': self.get_all_goals_status(),
            'metrics': {
                'total_trades': len(self._trade_results),
                'winning_trades': sum(1 for r in self._trade_results if r > 0),
                'losing_trades': sum(1 for r in self._trade_results if r < 0),
                'returns_history_length': len(self._returns_history),
                'capital_history_length': len(self._capital_history),
                'peak_capital': self._peak_capital
            },
            'health': self.get_overall_health()
        }


# Singleton instance
_goal_manager: Optional[GoalManager] = None


def get_goal_manager(config: Dict[str, Any] = None) -> GoalManager:
    """Get singleton goal manager instance."""
    global _goal_manager
    if _goal_manager is None:
        _goal_manager = GoalManager(config)
    return _goal_manager


def reset_goal_manager():
    """Reset the goal manager instance."""
    global _goal_manager
    _goal_manager = None
