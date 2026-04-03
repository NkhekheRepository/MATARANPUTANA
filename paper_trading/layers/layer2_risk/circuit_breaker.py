"""
Layer 2: Circuit Breaker
Pause trading when异常 conditions detected.
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
from loguru import logger


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for trading pauses."""
    
    def __init__(self, config: Dict[str, Any]):
        self.failure_threshold = config.get('failure_threshold', 5)
        self.success_threshold = config.get('success_threshold', 2)
        self.timeout_duration = config.get('timeout_duration', 60)
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.opened_at: Optional[float] = None
    
    def record_failure(self):
        """Record a failure event."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self._trip_circuit()
        
        logger.warning(f"Circuit breaker: Failure recorded ({self.failure_count}/{self.failure_threshold})")
    
    def record_success(self):
        """Record a success event."""
        self.success_count += 1
        
        if self.state == CircuitState.HALF_OPEN:
            if self.success_count >= self.success_threshold:
                self._reset_circuit()
        
        logger.info(f"Circuit breaker: Success recorded ({self.success_count}/{self.success_threshold})")
    
    def can_execute(self) -> bool:
        """Check if trading can proceed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self._attempt_reset()
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            return True
        
        return False
    
    def _trip_circuit(self):
        """Trip the circuit breaker open."""
        self.state = CircuitState.OPEN
        self.opened_at = time.time()
        logger.critical(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if not self.opened_at:
            return False
        
        return (time.time() - self.opened_at) >= self.timeout_duration
    
    def _attempt_reset(self):
        """Attempt to reset to half-open state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        logger.info("Circuit breaker: Attempting reset (HALF_OPEN)")
    
    def _reset_circuit(self):
        """Reset the circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.opened_at = None
        logger.info("Circuit breaker: RESET (CLOSED)")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'opened_at': self.opened_at,
            'can_execute': self.can_execute()
        }
    
    def force_open(self):
        """Manually open the circuit breaker."""
        self._trip_circuit()
    
    def force_close(self):
        """Manually close the circuit breaker."""
        self._reset_circuit()


class TradingCircuitBreaker:
    """Specialized circuit breaker for trading operations."""
    
    def __init__(self):
        self.order_circuit = CircuitBreaker({'failure_threshold': 5, 'timeout_duration': 60})  # Increased from 3,30
        self.data_circuit = CircuitBreaker({'failure_threshold': 10, 'timeout_duration': 120})  # Increased from 5,60
        self.strategy_circuit = CircuitBreaker({'failure_threshold': 10, 'timeout_duration': 180})  # Increased from 5,120
    
    def check_order_allowed(self) -> bool:
        """Check if orders can be placed."""
        return self.order_circuit.can_execute()
    
    def check_data_allowed(self) -> bool:
        """Check if data operations allowed."""
        return self.data_circuit.can_execute()
    
    def check_strategy_allowed(self) -> bool:
        """Check if strategy can run."""
        return self.strategy_circuit.can_execute()
    
    def record_order_failure(self):
        """Record order failure."""
        self.order_circuit.record_failure()
    
    def record_order_success(self):
        """Record order success."""
        self.order_circuit.record_success()
    
    def record_data_failure(self):
        """Record data failure."""
        self.data_circuit.record_failure()
    
    def record_data_success(self):
        """Record data success."""
        self.data_circuit.record_success()
    
    def get_status(self) -> Dict[str, Any]:
        """Get all circuit breaker statuses."""
        return {
            'order': self.order_circuit.get_state(),
            'data': self.data_circuit.get_state(),
            'strategy': self.strategy_circuit.get_state()
        }

    def force_close(self):
        """Manually close (reset) all circuit breakers."""
        self.order_circuit.force_close()
        self.data_circuit.force_close()
        self.strategy_circuit.force_close()

    def force_open(self):
        """Manually open all circuit breakers."""
        self.order_circuit.force_open()
        self.data_circuit.force_open()
        self.strategy_circuit.force_open()


circuit_breaker = TradingCircuitBreaker()
