"""
SYNTROPION OS — Circuit Breaker & Emergency Kill-Switch (Zero-Panic Safe Mode)
Protects the autonomous venture factory from cascading failures, runaway token drains, and API storms.
Complies with Rule 5: Safe Shutdown / Kill Switch standard.
"""

import time
import logging
import threading
from typing import Dict, Any, Optional
from syntropion_core.database import db, get_current_iso_time

logger = logging.getLogger("syntropion.circuit_breaker")


class CircuitBreaker:
    """Adaptive circuit breaker with automatic tripping and manual kill-switch capability."""

    STATE_CLOSED = "CLOSED"        # Normal operational state
    STATE_OPEN = "OPEN"            # Tripped / Safe shutdown mode
    STATE_HALF_OPEN = "HALF_OPEN"  # Testing recovery

    def __init__(
        self,
        failure_threshold_pct: float = 30.0,
        window_size: int = 20,
        cooldown_seconds: float = 30.0
    ):
        self.failure_threshold_pct = failure_threshold_pct
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds

        self.state = self.STATE_CLOSED
        self.recent_calls = []  # List of (timestamp, success_bool)
        self.last_tripped_at: Optional[float] = None
        self.kill_switch_active = False
        self.kill_switch_reason: Optional[str] = None
        self._lock = threading.Lock()

    def record_call(self, success: bool, error_msg: Optional[str] = None) -> None:
        """Records outcome of an external LLM/Stripe/IPC call."""
        with self._lock:
            now = time.time()
            self.recent_calls.append((now, success))
            # Keep only within window_size
            if len(self.recent_calls) > self.window_size:
                self.recent_calls.pop(0)

            if not success and error_msg:
                logger.warning(f"Circuit call failure: {error_msg}")

            self._evaluate_state_locked()

    def _evaluate_state_locked(self) -> None:
        """Evaluates failure percentage across sliding window under lock."""
        if self.kill_switch_active:
            self.state = self.STATE_OPEN
            return

        now = time.time()
        if self.state == self.STATE_OPEN:
            if self.last_tripped_at and (now - self.last_tripped_at) >= self.cooldown_seconds:
                self.state = self.STATE_HALF_OPEN
                self.recent_calls.clear()
                logger.info("CircuitBreaker transitioning to HALF_OPEN trial state.")
            return

        if self.state == self.STATE_HALF_OPEN:
            # If the latest trial call failed, trip back to OPEN immediately
            if self.recent_calls and not self.recent_calls[-1][1]:
                self._trip_breaker_locked(reason="Failure occurred during HALF_OPEN trial probe.")
                return
            # If we have at least 2 consecutive successes in HALF_OPEN, fully recover to CLOSED
            recent_outcomes = [succ for _, succ in self.recent_calls[-2:]]
            if len(recent_outcomes) >= 2 and all(recent_outcomes):
                self.state = self.STATE_CLOSED
                self.recent_calls.clear()
                logger.info("CircuitBreaker recovered: transitioning back to CLOSED state.")
            return

        if len(self.recent_calls) >= 5:
            failures = sum(1 for _, succ in self.recent_calls if not succ)
            fail_rate = (failures / len(self.recent_calls)) * 100.0

            if fail_rate >= self.failure_threshold_pct:
                self._trip_breaker_locked(reason=f"Failure rate spiked to {fail_rate:.1f}% (Threshold: {self.failure_threshold_pct}%)")

    def _trip_breaker_locked(self, reason: str) -> None:
        """Trips breaker into OPEN safe mode."""
        self.state = self.STATE_OPEN
        self.last_tripped_at = time.time()
        logger.error(f"🚨 CIRCUIT BREAKER TRIPPED! Reason: {reason}")
        db.log_audit_event(
            event_type="CIRCUIT_BREAKER_TRIPPED",
            actor="SYSTEM_HEALTH_MONITOR",
            payload={"reason": reason, "timestamp": get_current_iso_time()}
        )

    def activate_kill_switch(self, operator: str, reason: str) -> None:
        """Manually forces immediate full Safe Shutdown / Emergency Stop."""
        with self._lock:
            self.kill_switch_active = True
            self.kill_switch_reason = reason
            self.state = self.STATE_OPEN
            self.last_tripped_at = time.time()
            logger.critical(f"🛑 EMERGENCY KILL-SWITCH ACTIVATED by {operator}: {reason}")
            db.log_audit_event(
                event_type="EMERGENCY_KILL_SWITCH_ACTIVATED",
                actor=operator,
                payload={"reason": reason, "timestamp": get_current_iso_time()}
            )

    def deactivate_kill_switch(self, operator: str) -> None:
        """Resets manual kill-switch back to normal operation."""
        with self._lock:
            self.kill_switch_active = False
            self.kill_switch_reason = None
            self.state = self.STATE_CLOSED
            self.recent_calls.clear()
            logger.info(f"🟢 KILL-SWITCH DEACTIVATED by {operator}. System restored to CLOSED.")
            db.log_audit_event(
                event_type="EMERGENCY_KILL_SWITCH_DEACTIVATED",
                actor=operator,
                payload={"timestamp": get_current_iso_time()}
            )

    def is_operational(self) -> bool:
        """Returns True if requests are allowed to proceed."""
        with self._lock:
            self._evaluate_state_locked()
            return self.state in (self.STATE_CLOSED, self.STATE_HALF_OPEN)

    def get_status(self) -> Dict[str, Any]:
        """Returns current telemetry status of circuit breaker."""
        with self._lock:
            self._evaluate_state_locked()
            failures = sum(1 for _, succ in self.recent_calls if not succ) if self.recent_calls else 0
            total = len(self.recent_calls)
            rate = (failures / total * 100.0) if total > 0 else 0.0

            return {
                "state": self.state,
                "is_operational": self.state in (self.STATE_CLOSED, self.STATE_HALF_OPEN),
                "kill_switch_active": self.kill_switch_active,
                "kill_switch_reason": self.kill_switch_reason,
                "recent_failure_rate_pct": round(rate, 2),
                "window_calls_count": total
            }

    def reset(self) -> None:
        """Resets the circuit breaker to its initial pristine closed state."""
        with self._lock:
            self.state = self.STATE_CLOSED
            self.recent_calls.clear()
            self.last_tripped_at = None
            self.kill_switch_active = False
            self.kill_switch_reason = None


circuit_breaker = CircuitBreaker()
