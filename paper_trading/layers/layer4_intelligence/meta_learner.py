"""
Layer 4: Meta-Learner
Optimizes learning parameters based on market regime.
Provides regime-adaptive hyperparameters for ML models.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger

from ..event_bus import get_event_bus, EventType, publish_regime_detected


class MarketRegime(Enum):
    """Market regime types."""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"


@dataclass
class RegimeParams:
    """Learning parameters optimized for a specific regime."""
    regime: str
    learning_rate: float
    exploration_rate: float
    batch_size: int
    retrain_interval: int  # seconds
    min_samples: int
    confidence_threshold: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'regime': self.regime,
            'learning_rate': self.learning_rate,
            'exploration_rate': self.exploration_rate,
            'batch_size': self.batch_size,
            'retrain_interval': self.retrain_interval,
            'min_samples': self.min_samples,
            'confidence_threshold': self.confidence_threshold
        }


@dataclass
class RegimePerformance:
    """Performance metrics for a regime."""
    regime: str
    total_periods: int = 0
    profitable_periods: int = 0
    total_return: float = 0.0
    avg_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float = 0.0
    
    def update(self, period_return: float):
        """Update performance with a new period return."""
        self.total_periods += 1
        self.total_return += period_return
        if period_return > 0:
            self.profitable_periods += 1
        self.avg_return = self.total_return / self.total_periods
        self.win_rate = (self.profitable_periods / self.total_periods) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'regime': self.regime,
            'total_periods': self.total_periods,
            'profitable_periods': self.profitable_periods,
            'total_return': round(self.total_return, 4),
            'avg_return': round(self.avg_return, 4),
            'max_drawdown': round(self.max_drawdown, 4),
            'win_rate': round(self.win_rate, 1),
            'sharpe_ratio': round(self.sharpe_ratio, 2)
        }


class MetaLearner:
    """
    Meta-learning system that adapts learning parameters based on market regime.
    
    Features:
    - Maintains optimal parameters for each regime
    - Learns from regime-specific performance
    - Adjusts exploration/exploitation balance
    - Optimizes retraining frequency
    """
    
    # Default parameters per regime
    DEFAULT_PARAMS = {
        MarketRegime.BULL.value: RegimeParams(
            regime="bull",
            learning_rate=0.001,
            exploration_rate=0.15,
            batch_size=32,
            retrain_interval=300,  # 5 min
            min_samples=20,
            confidence_threshold=0.6
        ),
        MarketRegime.BEAR.value: RegimeParams(
            regime="bear",
            learning_rate=0.0005,  # Slower learning in bear markets
            exploration_rate=0.05,  # Less exploration
            batch_size=64,
            retrain_interval=600,  # 10 min
            min_samples=50,  # More samples needed
            confidence_threshold=0.7  # Higher confidence required
        ),
        MarketRegime.SIDEWAYS.value: RegimeParams(
            regime="sideways",
            learning_rate=0.0008,
            exploration_rate=0.2,  # More exploration in sideways
            batch_size=32,
            retrain_interval=450,  # 7.5 min
            min_samples=30,
            confidence_threshold=0.55
        ),
        MarketRegime.VOLATILE.value: RegimeParams(
            regime="volatile",
            learning_rate=0.002,  # Faster learning in volatile
            exploration_rate=0.3,  # High exploration
            batch_size=16,  # Smaller batches
            retrain_interval=180,  # 3 min
            min_samples=15,
            confidence_threshold=0.5
        )
    }
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        
        # Current parameters
        self.current_regime: str = MarketRegime.UNKNOWN.value
        self.current_params: RegimeParams = self.DEFAULT_PARAMS[MarketRegime.SIDEWAYS.value]
        
        # Regime performance tracking
        self.regime_performance: Dict[str, RegimePerformance] = {
            regime: RegimePerformance(regime=regime)
            for regime in MarketRegime
        }
        
        # Parameter adaptation history
        self.param_history: List[Dict[str, Any]] = []
        self.max_param_history = 100
        
        # Learning from regime transitions
        self.regime_transitions: List[Tuple[str, str, float]] = []  # (from, to, timestamp)
        
        # Black Swan Phase 3: Meta-Learning Stability
        self.model_update_frozen = False
        self.freeze_reason: Optional[str] = None
        self.performance_degradation_count = 0
        self.last_model_state: Optional[Dict[str, Any]] = None
        self.volatility_gate = 0.0
        
        # Subscribe to regime events
        self.event_bus = get_event_bus()
        self.event_bus.subscribe(
            [EventType.REGIME_DETECTED],
            self._on_regime_change
        )
        
        logger.info("MetaLearner initialized")
    
    def _on_regime_change(self, event):
        """Handle regime change events."""
        new_regime = getattr(event, 'regime', None)
        confidence = getattr(event, 'confidence', 0.5)
        
        if new_regime and new_regime != self.current_regime:
            old_regime = self.current_regime
            self.transition_to_regime(new_regime, confidence)
            
            # Record transition
            self.regime_transitions.append((old_regime, new_regime, time.time()))
            
            # Keep history manageable
            if len(self.regime_transitions) > 100:
                self.regime_transitions = self.regime_transitions[-50:]
    
    def transition_to_regime(self, regime: str, confidence: float = 0.5):
        """Transition to a new market regime."""
        old_regime = self.current_regime
        self.current_regime = regime
        
        # Record transition (only if actually changing regimes)
        if old_regime != regime:
            self.regime_transitions.append((old_regime, regime, time.time()))
            if len(self.regime_transitions) > 100:
                self.regime_transitions = self.regime_transitions[-50:]
        
        # Get optimal parameters for new regime
        if regime in [r.value for r in MarketRegime]:
            self.current_params = self._get_optimized_params(regime)
        else:
            logger.warning(f"Unknown regime: {regime}, using default")
            self.current_params = self.DEFAULT_PARAMS[MarketRegime.SIDEWAYS.value]
        
        # Record parameter change
        self.param_history.append({
            'timestamp': time.time(),
            'old_regime': old_regime,
            'new_regime': regime,
            'confidence': confidence,
            'params': self.current_params.to_dict()
        })
        
        if len(self.param_history) > self.max_param_history:
            self.param_history = self.param_history[-(self.max_param_history // 2):]
        
        logger.info(f"MetaLearner: Regime transition {old_regime} -> {regime} "
                   f"(confidence: {confidence:.2f})")
    
    def _get_optimized_params(self, regime: str) -> RegimeParams:
        """Get optimized parameters for a regime based on historical performance."""
        # Start with defaults
        base_params = self.DEFAULT_PARAMS.get(regime)
        if not base_params:
            base_params = self.DEFAULT_PARAMS[MarketRegime.SIDEWAYS.value]
        
        # Check if we have performance data to optimize
        perf_key = MarketRegime(regime) if regime in [r.value for r in MarketRegime] else MarketRegime.UNKNOWN
        perf = self.regime_performance.get(perf_key)
        
        if perf and perf.total_periods >= 10:
            # Adjust parameters based on performance
            return self._adapt_params(base_params, perf)
        
        return base_params
    
    def _adapt_params(self, base: RegimeParams, perf: RegimePerformance) -> RegimeParams:
        """Adapt parameters based on regime performance."""
        # If win rate is low, increase exploration
        exploration_rate = base.exploration_rate
        if perf.win_rate < 40:
            exploration_rate = min(0.4, exploration_rate * 1.2)
        elif perf.win_rate > 60:
            exploration_rate = max(0.05, exploration_rate * 0.8)
        
        # If returns are negative, reduce learning rate
        learning_rate = base.learning_rate
        if perf.avg_return < -0.01:
            learning_rate = learning_rate * 0.8
        elif perf.avg_return > 0.02:
            learning_rate = min(0.01, learning_rate * 1.1)
        
        return RegimeParams(
            regime=base.regime,
            learning_rate=learning_rate,
            exploration_rate=exploration_rate,
            batch_size=base.batch_size,
            retrain_interval=base.retrain_interval,
            min_samples=base.min_samples,
            confidence_threshold=base.confidence_threshold
        )
    
    def update_performance(self, period_return: float):
        """Update performance for current regime."""
        if self.current_regime in [r.value for r in MarketRegime]:
            regime_enum = MarketRegime(self.current_regime)
            self.regime_performance[regime_enum].update(period_return)
    
    def get_current_params(self) -> Dict[str, Any]:
        """Get current learning parameters."""
        return self.current_params.to_dict()
    
    def get_regime_performance(self) -> Dict[str, Any]:
        """Get performance metrics for all regimes."""
        return {
            regime.value: perf.to_dict()
            for regime, perf in self.regime_performance.items()
            if regime != MarketRegime.UNKNOWN
        }
    
    def get_regime_history(self) -> List[Dict[str, Any]]:
        """Get regime transition history."""
        return [
            {
                'from_regime': t[0],
                'to_regime': t[1],
                'timestamp': t[2]
            }
            for t in self.regime_transitions[-20:]
        ]
    
    def get_recommended_retrain_interval(self) -> int:
        """Get recommended retraining interval for current regime."""
        return self.current_params.retrain_interval
    
    def get_recommended_min_samples(self) -> int:
        """Get recommended minimum samples for current regime."""
        return self.current_params.min_samples
    
    def get_confidence_threshold(self) -> float:
        """Get confidence threshold for current regime."""
        return self.current_params.confidence_threshold
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive meta-learner status."""
        return {
            'enabled': self.enabled,
            'current_regime': self.current_regime,
            'current_params': self.current_params.to_dict(),
            'regime_performance': self.get_regime_performance(),
            'regime_history': self.get_regime_history(),
            'total_transitions': len(self.regime_transitions),
            'param_history_length': len(self.param_history)
        }
    
    def get_report(self) -> Dict[str, Any]:
        """Get comprehensive meta-learning report."""
        # Calculate best performing regime
        best_regime = None
        best_performance = -float('inf')
        
        for regime, perf in self.regime_performance.items():
            if regime == MarketRegime.UNKNOWN:
                continue
            if perf.total_periods >= 5 and perf.avg_return > best_performance:
                best_performance = perf.avg_return
                best_regime = regime.value
        
        return {
            'enabled': self.enabled,
            'current_regime': self.current_regime,
            'current_params': self.current_params.to_dict(),
            'best_performing_regime': best_regime,
            'best_regime_avg_return': round(best_performance, 4) if best_regime else None,
            'total_regime_transitions': len(self.regime_transitions),
            'regime_counts': self._count_regime_periods(),
            'param_adaptation_history': self.param_history[-10:]  # Last 10 adaptations
        }
    
    def _count_regime_periods(self) -> Dict[str, int]:
        """Count periods spent in each regime."""
        counts = defaultdict(int)
        for perf in self.regime_performance.values():
            counts[perf.regime] = perf.total_periods
        return dict(counts)
    
    # =========================================================================
    # BLACK SWAN RESISTANT LAYER - PHASE 3 (Feature 11: Meta-Learning Stability)
    # =========================================================================
    
    def check_update_stability(self, current_volatility: float, 
                                recent_performance: float) -> Dict[str, Any]:
        """
        Feature 11: Meta-Learning Stability Control
        Disable updates during volatility spikes.
        Freeze model under poor performance.
        Rollback to previous stable model if degradation detected.
        """
        if not self.enabled:
            return {
                'allowed': True,
                'frozen': self.model_update_frozen,
                'reason': 'Meta-learner disabled'
            }
        
        # Check volatility gate
        volatility_threshold = 0.03  # 3% threshold
        
        if current_volatility > volatility_threshold and not self.model_update_frozen:
            self.model_update_frozen = True
            self.freeze_reason = f'High volatility: {current_volatility:.4f} > {volatility_threshold}'
            logger.critical(f"MODEL UPDATES FROZEN: {self.freeze_reason}")
            
            return {
                'allowed': False,
                'frozen': True,
                'reason': self.freeze_reason,
                'action': 'freeze_updates'
            }
        
        # Check performance degradation
        if recent_performance < -0.05:  # 5% loss
            self.performance_degradation_count += 1
            
            if self.performance_degradation_count >= 3 and not self.model_update_frozen:
                self.model_update_frozen = True
                self.freeze_reason = f'Performance degradation: {recent_performance:.4f} for {self.performance_degradation_count} periods'
                logger.critical(f"MODEL UPDATES FROZEN: {self.freeze_reason}")
                
                return {
                    'allowed': False,
                    'frozen': True,
                    'reason': self.freeze_reason,
                    'action': 'freeze_and_rollback'
                }
        else:
            self.performance_degradation_count = 0
        
        # Normal conditions
        if current_volatility < volatility_threshold * 0.5 and self.model_update_frozen:
            self.model_update_frozen = False
            self.freeze_reason = None
            logger.info("MODEL UPDATES UNFROZEN: Volatility normalized")
            
            return {
                'allowed': True,
                'frozen': False,
                'reason': 'Volatility normalized, updates resumed',
                'action': 'resume_updates'
            }
        
        return {
            'allowed': True,
            'frozen': self.model_update_frozen,
            'reason': 'Stability OK'
        }
    
    def get_rollback_state(self) -> Optional[Dict[str, Any]]:
        """Get previous stable model state for rollback."""
        return self.last_model_state
    
    def save_stable_state(self, model_state: Dict[str, Any]):
        """Save current model state as stable checkpoint."""
        self.last_model_state = model_state.copy()
        logger.info("Stable model state saved")
    
    def get_stability_status(self) -> Dict[str, Any]:
        """Get meta-learning stability status."""
        return {
            'frozen': self.model_update_frozen,
            'freeze_reason': self.freeze_reason,
            'performance_degradation_count': self.performance_degradation_count,
            'volatility_gate': self.volatility_gate,
            'has_rollback_state': self.last_model_state is not None
        }


# Singleton instance
_meta_learner: Optional[MetaLearner] = None


def get_meta_learner(config: Dict[str, Any] = None) -> MetaLearner:
    """Get singleton meta-learner instance."""
    global _meta_learner
    if _meta_learner is None:
        _meta_learner = MetaLearner(config)
    return _meta_learner


def reset_meta_learner():
    """Reset the meta-learner instance."""
    global _meta_learner
    _meta_learner = None
