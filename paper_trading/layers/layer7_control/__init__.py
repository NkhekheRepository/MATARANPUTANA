"""
Layer 7: Command & Control
==========================
Self-aware command and control with health monitoring and auto-healing.
"""

from .self_awareness import (
    SelfAwarenessEngine,
    SystemStatus,
    HealingAction,
    LayerHealth,
    HealingActionRecord,
    get_self_awareness_engine,
    reset_self_awareness_engine
)

__all__ = [
    'SelfAwarenessEngine',
    'SystemStatus',
    'HealingAction',
    'LayerHealth',
    'HealingActionRecord',
    'get_self_awareness_engine',
    'reset_self_awareness_engine'
]