from .cta_strategies import (
    MomentumCtaStrategy,
    MeanReversionCtaStrategy,
    BreakoutCtaStrategy,
    RlEnhancedCtaStrategy,
    RlCtaSignal,
)

CTA_STRATEGY_REGISTRY = {
    "MomentumCtaStrategy": MomentumCtaStrategy,
    "MeanReversionCtaStrategy": MeanReversionCtaStrategy,
    "BreakoutCtaStrategy": BreakoutCtaStrategy,
    "RlEnhancedCtaStrategy": RlEnhancedCtaStrategy,
}

__all__ = [
    "MomentumCtaStrategy",
    "MeanReversionCtaStrategy", 
    "BreakoutCtaStrategy",
    "RlEnhancedCtaStrategy",
    "RlCtaSignal",
    "CTA_STRATEGY_REGISTRY",
]
