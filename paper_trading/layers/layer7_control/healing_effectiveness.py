"""
Layer 7: Healing Effectiveness Tracker
Tracks and learns from healing action outcomes.
Provides stateful healing that adapts based on historical effectiveness.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from loguru import logger

from ..event_bus import get_event_bus, EventType


class HealingOutcome(Enum):
    """Outcome of a healing action."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    UNKNOWN = "unknown"


@dataclass
class HealingRecord:
    """Record of a single healing action."""
    component: str
    action: str
    timestamp: float
    outcome: HealingOutcome
    recovery_time_ms: float
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'component': self.component,
            'action': self.action,
            'timestamp': self.timestamp,
            'outcome': self.outcome.value,
            'recovery_time_ms': self.recovery_time_ms,
            'context': self.context
        }


@dataclass
class ComponentHealingStats:
    """Aggregated healing statistics for a component."""
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    total_recovery_time_ms: float = 0.0
    action_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    action_success_rates: Dict[str, float] = field(default_factory=dict)
    last_action_time: float = 0.0
    consecutive_failures: int = 0
    
    def record_action(self, action: str, outcome: HealingOutcome, recovery_time_ms: float):
        """Record a healing action."""
        self.total_actions += 1
        self.action_counts[action] += 1
        self.last_action_time = time.time()
        
        if outcome == HealingOutcome.SUCCESS:
            self.successful_actions += 1
            self.consecutive_failures = 0
            self.total_recovery_time_ms += recovery_time_ms
        elif outcome == HealingOutcome.FAILURE:
            self.failed_actions += 1
            self.consecutive_failures += 1
        
        # Update action-specific success rate
        self._update_action_success_rate(action, outcome)
    
    def _update_action_success_rate(self, action: str, outcome: HealingOutcome):
        """Update success rate for a specific action."""
        # This is a simplified calculation - in production would track per-action
        if self.total_actions > 0:
            self.action_success_rates[action] = self.successful_actions / self.total_actions
    
    def get_success_rate(self) -> float:
        """Get overall success rate."""
        if self.total_actions == 0:
            return 0.0
        return (self.successful_actions / self.total_actions) * 100
    
    def get_avg_recovery_time(self) -> float:
        """Get average recovery time in milliseconds."""
        if self.successful_actions == 0:
            return 0.0
        return self.total_recovery_time_ms / self.successful_actions
    
    def get_best_action(self) -> Optional[str]:
        """Get the most successful action type."""
        if not self.action_success_rates:
            return None
        return max(self.action_success_rates.items(), key=lambda x: x[1])[0]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_actions': self.total_actions,
            'successful_actions': self.successful_actions,
            'failed_actions': self.failed_actions,
            'success_rate': round(self.get_success_rate(), 1),
            'avg_recovery_time_ms': round(self.get_avg_recovery_time(), 1),
            'consecutive_failures': self.consecutive_failures,
            'action_counts': dict(self.action_counts),
            'best_action': self.get_best_action(),
            'last_action_time': self.last_action_time
        }


class HealingEffectivenessTracker:
    """
    Tracks healing action effectiveness and learns optimal healing strategies.
    
    Features:
    - Tracks success rates per component and action type
    - Identifies most effective healing actions
    - Learns from failures to improve healing strategies
    - Provides recommendations for healing actions
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
        
        # Component stats: component_name -> ComponentHealingStats
        self.component_stats: Dict[str, ComponentHealingStats] = defaultdict(ComponentHealingStats)
        
        # Healing history
        self.healing_history: List[HealingRecord] = []
        self.max_history = self.config.get('max_history', 1000)
        
        # Learning parameters
        self.min_samples_for_learning = self.config.get('min_samples', 5)
        self.success_threshold = self.config.get('success_threshold', 70.0)
        
        # Subscribe to healing events
        self.event_bus = get_event_bus()
        self.event_bus.subscribe(
            [EventType.HEALING_ACTION_TRIGGERED, EventType.HEALING_ACTION_COMPLETED],
            self._on_healing_event
        )
        
        logger.info("HealingEffectivenessTracker initialized")
    
    def _on_healing_event(self, event):
        """Handle healing events from event bus."""
        event_type = getattr(event, 'event_type', None)
        
        if event_type == EventType.HEALING_ACTION_COMPLETED:
            action = getattr(event, 'action', 'unknown')
            component = getattr(event, 'layer_id', 'unknown')
            success = getattr(event, 'success', False)
            duration_ms = getattr(event, 'duration_ms', 0.0)
            
            outcome = HealingOutcome.SUCCESS if success else HealingOutcome.FAILURE
            self.record_healing_action(
                component=component,
                action=action,
                outcome=outcome,
                recovery_time_ms=duration_ms
            )
    
    def record_healing_action(self, component: str, action: str,
                              outcome: HealingOutcome, recovery_time_ms: float,
                              context: Dict[str, Any] = None):
        """Record a healing action and its outcome."""
        if not self.enabled:
            return
        
        record = HealingRecord(
            component=component,
            action=action,
            timestamp=time.time(),
            outcome=outcome,
            recovery_time_ms=recovery_time_ms,
            context=context or {}
        )
        
        self.healing_history.append(record)
        self.component_stats[component].record_action(action, outcome, recovery_time_ms)
        
        # Trim history if needed
        if len(self.healing_history) > self.max_history:
            self.healing_history = self.healing_history[-(self.max_history // 2):]
        
        logger.debug(f"Recorded healing: {component}/{action} = {outcome.value} "
                    f"({recovery_time_ms:.1f}ms)")
    
    def get_recommended_action(self, component: str, failure_count: int) -> Optional[str]:
        """Get recommended healing action based on historical effectiveness."""
        stats = self.component_stats.get(component)
        
        if not stats or stats.total_actions < self.min_samples_for_learning:
            # Not enough data - use default heuristic
            return self._default_action_heuristic(failure_count)
        
        best_action = stats.get_best_action()
        if best_action and stats.get_success_rate() >= self.success_threshold:
            return best_action
        
        # Fall back to heuristic if effectiveness is low
        return self._default_action_heuristic(failure_count)
    
    def _default_action_heuristic(self, failure_count: int) -> str:
        """Default action selection heuristic."""
        if failure_count <= 1:
            return 'restart'
        elif failure_count <= 3:
            return 'restart_with_reset'
        else:
            return 'escalate'
    
    def get_component_stats(self, component: str) -> Optional[Dict[str, Any]]:
        """Get healing statistics for a specific component."""
        if component in self.component_stats:
            return self.component_stats[component].to_dict()
        return None
    
    def get_all_stats(self) -> Dict[str, Any]:
        """Get healing statistics for all components."""
        return {
            name: stats.to_dict() for name, stats in self.component_stats.items()
        }
    
    def get_effectiveness_report(self) -> Dict[str, Any]:
        """Get comprehensive effectiveness report."""
        total_actions = sum(s.total_actions for s in self.component_stats.values())
        total_success = sum(s.successful_actions for s in self.component_stats.values())
        total_failures = sum(s.failed_actions for s in self.component_stats.values())
        
        overall_success_rate = (total_success / max(total_actions, 1)) * 100
        
        # Identify problematic components
        problematic = []
        for name, stats in self.component_stats.items():
            if stats.consecutive_failures >= 3:
                problematic.append({
                    'component': name,
                    'consecutive_failures': stats.consecutive_failures,
                    'success_rate': round(stats.get_success_rate(), 1)
                })
        
        # Recent healing trend
        recent_history = self.healing_history[-20:] if len(self.healing_history) >= 20 else self.healing_history
        recent_success = sum(1 for r in recent_history if r.outcome == HealingOutcome.SUCCESS)
        recent_success_rate = (recent_success / max(len(recent_history), 1)) * 100
        
        return {
            'enabled': self.enabled,
            'total_actions': total_actions,
            'total_success': total_success,
            'total_failures': total_failures,
            'overall_success_rate': round(overall_success_rate, 1),
            'recent_success_rate': round(recent_success_rate, 1),
            'components': self.get_all_stats(),
            'problematic_components': problematic,
            'history_length': len(self.healing_history)
        }
    
    def get_failure_pattern(self, component: str) -> Dict[str, Any]:
        """Analyze failure patterns for a component."""
        component_records = [r for r in self.healing_history if r.component == component]
        
        if not component_records:
            return {'error': 'No records found'}
        
        failures = [r for r in component_records if r.outcome == HealingOutcome.FAILURE]
        successes = [r for r in component_records if r.outcome == HealingOutcome.SUCCESS]
        
        # Analyze action effectiveness
        action_stats = defaultdict(lambda: {'total': 0, 'success': 0})
        for record in component_records:
            action_stats[record.action]['total'] += 1
            if record.outcome == HealingOutcome.SUCCESS:
                action_stats[record.action]['success'] += 1
        
        action_effectiveness = {}
        for action, stats in action_stats.items():
            action_effectiveness[action] = {
                'total': stats['total'],
                'success': stats['success'],
                'success_rate': round((stats['success'] / max(stats['total'], 1)) * 100, 1)
            }
        
        return {
            'component': component,
            'total_records': len(component_records),
            'total_failures': len(failures),
            'total_successes': len(successes),
            'action_effectiveness': action_effectiveness,
            'recommended_action': self.get_recommended_action(component, len(failures))
        }
    
    def learn_from_failures(self) -> List[Dict[str, Any]]:
        """Analyze failures and generate learnings."""
        learnings = []
        
        for component, stats in self.component_stats.items():
            if stats.total_actions < self.min_samples_for_learning:
                continue
            
            # Check if any action type has low success rate
            for action, count in stats.action_counts.items():
                if count >= 3:  # Minimum samples per action
                    success_rate = stats.action_success_rates.get(action, 0)
                    if success_rate < 50:
                        learnings.append({
                            'component': component,
                            'action': action,
                            'issue': 'low_success_rate',
                            'success_rate': round(success_rate, 1),
                            'recommendation': f'Consider alternative healing for {action}'
                        })
        
        return learnings


# Singleton instance
_effectiveness_tracker: Optional[HealingEffectivenessTracker] = None


def get_effectiveness_tracker(config: Dict[str, Any] = None) -> HealingEffectivenessTracker:
    """Get singleton healing effectiveness tracker."""
    global _effectiveness_tracker
    if _effectiveness_tracker is None:
        _effectiveness_tracker = HealingEffectivenessTracker(config)
    return _effectiveness_tracker


def reset_effectiveness_tracker():
    """Reset the effectiveness tracker instance."""
    global _effectiveness_tracker
    _effectiveness_tracker = None
