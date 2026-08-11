import threading
import time

from hermes.observability.types import CircuitBreakerState


class CircuitBreaker:
    """Generic thread-safe circuit breaker state machine."""

    max_failures: int
    cooldown: float
    failures: int
    state: CircuitBreakerState
    last_state_change: float
    _lock: threading.Lock

    def __init__(self, max_failures: int = 3, cooldown: float = 30.0) -> None:
        self.max_failures = max_failures
        self.cooldown = cooldown
        self.failures = 0
        self.state = CircuitBreakerState.CLOSED
        self.last_state_change = 0.0
        self._lock = threading.Lock()

    def can_attempt(self) -> bool:
        """Determines if a request can be attempted based on circuit state."""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if time.time() - self.last_state_change >= self.cooldown:
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.last_state_change = time.time()
                    return True
                return False
            return True

    def record_success(self) -> None:
        """Records a successful operation and closes the circuit."""
        with self._lock:
            self.failures = 0
            self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        """Records a failed operation and opens the circuit if threshold is reached."""
        with self._lock:
            self.failures += 1
            if self.failures >= self.max_failures:
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = time.time()
