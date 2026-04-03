"""
Layer 4: Adaptive Learning
Regime-based strategy switching.
"""

from typing import Dict, Any, List, Optional
from loguru import logger


class AdaptiveLearning:
    """Adaptive learning for regime-based strategy switching."""
    
    def __init__(self, config: Dict[str, Any]):
        self.enabled = config.get('enabled', True)
        
        self.regime_strategy_map = config.get('regime_strategy_map', {
            'bull': 'MomentumCtaStrategy',
            'bear': 'MeanReversionCtaStrategy',
            'volatile': 'BreakoutCtaStrategy',
            'sideways': 'RlEnhancedCtaStrategy'
        })
        
        self.performance_tracker: Dict[str, Dict[str, Any]] = {}
        
        self.current_strategy: Optional[str] = None
        self.current_regime: str = 'sideways'
        
        self.strategy_switch_count = 0
    
    def select_strategy(self, regime: str, market_data: Dict[str, Any]) -> str:
        """Select best strategy for current regime."""
        if not self.enabled:
            return self.current_strategy or 'RlEnhancedCtaStrategy'
        
        base_strategy = self.regime_strategy_map.get(regime, 'RlEnhancedCtaStrategy')
        
        regime_performance = self.performance_tracker.get(regime, {})
        
        if regime_performance.get('win_rate', 0) > 0.6:
            self.current_strategy = base_strategy
        else:
            self.current_strategy = 'RlEnhancedCtaStrategy'
        
        if self.current_strategy != base_strategy:
            logger.info(f"Adaptive override: {base_strategy} -> {self.current_strategy} (regime: {regime})")
        
        self.current_regime = regime
        
        return self.current_strategy
    
    def record_trade(self, regime: str, strategy: str, pnl: float, 
                    was_winning: bool):
        """Record trade result for performance tracking."""
        if regime not in self.performance_tracker:
            self.performance_tracker[regime] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0,
                'avg_pnl': 0
            }
        
        tracker = self.performance_tracker[regime]
        
        tracker['trades'] += 1
        if was_winning:
            tracker['wins'] += 1
        tracker['total_pnl'] += pnl
        tracker['win_rate'] = tracker['wins'] / tracker['trades']
        tracker['avg_pnl'] = tracker['total_pnl'] / tracker['trades']
    
    def get_strategy_for_regime(self, regime: str) -> str:
        """Get strategy for a specific regime."""
        return self.regime_strategy_map.get(regime, 'RlEnhancedCtaStrategy')
    
    def get_current_strategy(self) -> Optional[str]:
        """Get currently selected strategy."""
        return self.current_strategy
    
    def get_current_regime(self) -> str:
        """Get current regime."""
        return self.current_regime
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report by regime."""
        return {
            'current_regime': self.current_regime,
            'current_strategy': self.current_strategy,
            'total_switches': self.strategy_switch_count,
            'regime_performance': self.performance_tracker.copy()
        }
    
    def reset_performance(self):
        """Reset performance tracking."""
        self.performance_tracker = {}
        self.strategy_switch_count = 0
        logger.info("Performance tracking reset")


class RegimeBasedTrader:
    """High-level regime-based trading controller."""
    
    def __init__(self, config: Dict[str, Any]):
        self.adaptive = AdaptiveLearning(config)
        
        self.regime_history: List[str] = []
        self.strategy_history: List[str] = []
    
    def on_new_bar(self, regime: str, market_data: Dict[str, Any]) -> str:
        """Process new bar and return recommended strategy."""
        strategy = self.adaptive.select_strategy(regime, market_data)
        
        if self.adaptive.current_strategy != strategy:
            self.strategy_history.append(strategy)
            self.adaptive.strategy_switch_count += 1
        
        if regime != self.adaptive.current_regime:
            self.regime_history.append(regime)
        
        return strategy
    
    def on_trade_result(self, regime: str, pnl: float, was_winning: bool):
        """Record trade result."""
        strategy = self.adaptive.current_strategy or 'unknown'
        self.adaptive.record_trade(regime, strategy, pnl, was_winning)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        return {
            'adaptive': self.adaptive.get_performance_report(),
            'regime_history': self.regime_history[-10:],
            'strategy_history': self.strategy_history[-10:]
        }


adaptive_learning = AdaptiveLearning({'enabled': True})


def get_best_strategy_for_regime(regime: str) -> str:
    """Convenience function to get strategy for regime."""
    return adaptive_learning.get_strategy_for_regime(regime)
