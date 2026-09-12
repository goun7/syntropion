"""
Unit and integration tests for SYNTROPION OS Circuit Breaker & Emergency Kill Switch.
Tests sliding window, automatic tripping, half-open recovery, manual kill-switch, and thread-safety.
"""

import time
import pytest
from syntropion_core.circuit_breaker import CircuitBreaker


def test_circuit_breaker_initial_state():
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=10, cooldown_seconds=0.1)
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.is_operational() is True
    status = cb.get_status()
    assert status["state"] == "CLOSED"
    assert status["is_operational"] is True
    assert status["kill_switch_active"] is False
    assert status["window_calls_count"] == 0


def test_circuit_breaker_successful_calls():
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=10, cooldown_seconds=0.1)
    for _ in range(8):
        cb.record_call(success=True)
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.is_operational() is True
    status = cb.get_status()
    assert status["recent_failure_rate_pct"] == 0.0
    assert status["window_calls_count"] == 8


def test_circuit_breaker_automatic_trip_on_high_failure_rate():
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=10, cooldown_seconds=0.2)
    # 2 successes, 3 failures -> 3/5 = 60% failure rate (threshold is 30%)
    cb.record_call(success=True)
    cb.record_call(success=True)
    cb.record_call(success=False, error_msg="LLM Timeout")
    cb.record_call(success=False, error_msg="Stripe Rate Limit")
    cb.record_call(success=False, error_msg="IPC Buffer Full")

    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.is_operational() is False
    status = cb.get_status()
    assert status["state"] == "OPEN"
    assert status["is_operational"] is False
    assert status["recent_failure_rate_pct"] == 60.0


def test_circuit_breaker_cooldown_and_half_open_recovery():
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=10, cooldown_seconds=0.05)
    # Trip it
    for _ in range(5):
        cb.record_call(success=False, error_msg="Error")
    assert cb.state == CircuitBreaker.STATE_OPEN

    # Wait for cooldown
    time.sleep(0.08)
    # Checking operational status triggers transition to HALF_OPEN
    assert cb.is_operational() is True
    assert cb.state == CircuitBreaker.STATE_HALF_OPEN

    # Two successful trial calls should fully recover it to CLOSED
    cb.record_call(success=True)
    cb.record_call(success=True)
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.is_operational() is True


def test_circuit_breaker_half_open_failure_re_trips():
    cb = CircuitBreaker(failure_threshold_pct=30.0, window_size=10, cooldown_seconds=0.05)
    for _ in range(5):
        cb.record_call(success=False, error_msg="Error")
    assert cb.state == CircuitBreaker.STATE_OPEN

    time.sleep(0.08)
    assert cb.is_operational() is True
    assert cb.state == CircuitBreaker.STATE_HALF_OPEN

    # Trial call fails -> trips back immediately to OPEN
    cb.record_call(success=False, error_msg="Probe failed")
    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.is_operational() is False


def test_circuit_breaker_manual_kill_switch_lifecycle():
    cb = CircuitBreaker()
    assert cb.is_operational() is True

    # Operator engages emergency stop
    cb.activate_kill_switch(operator="sec-ops@syntropion.org", reason="Regulatory Audit Freeze")
    assert cb.kill_switch_active is True
    assert cb.kill_switch_reason == "Regulatory Audit Freeze"
    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.is_operational() is False

    # Recording successful calls does not unlock manual kill-switch
    cb.record_call(success=True)
    assert cb.state == CircuitBreaker.STATE_OPEN
    assert cb.is_operational() is False

    # Operator deactivates
    cb.deactivate_kill_switch(operator="sec-ops@syntropion.org")
    assert cb.kill_switch_active is False
    assert cb.kill_switch_reason is None
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.is_operational() is True


def test_circuit_breaker_reset():
    cb = CircuitBreaker()
    cb.activate_kill_switch(operator="admin", reason="Test")
    assert cb.state == CircuitBreaker.STATE_OPEN
    cb.reset()
    assert cb.state == CircuitBreaker.STATE_CLOSED
    assert cb.kill_switch_active is False
    assert len(cb.recent_calls) == 0
