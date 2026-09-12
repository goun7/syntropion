"""
Tests for $10 Stake Escrow Gate, status transitions, and automated refunds.
"""

import pytest
from syntropion_core.database import db
from syntropion_core.stake_gate import stake_gate


@pytest.fixture(autouse=True)
def setup_seed():
    db._ensure_schema()
    db.seed_deep_vertical_pilots()


def test_stake_hold_and_refund():
    expert_id = "exp-pilot-001-radiologist"
    idea_id = "idea-test-stake-001"

    db.execute(
        """
        INSERT OR IGNORE INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, created_at, updated_at
        ) VALUES (?, ?, 'Test Idea', 'Problem Statement', 'Target', 10.00, 'PENDING', 'SUBMITTED', '2026-01-01', '2026-01-01')
        """,
        (idea_id, expert_id)
    )

    # 1. Hold
    res_hold = stake_gate.hold_stake_in_escrow(idea_id, expert_id, 10.00)
    assert res_hold["status"] == "HELD_IN_ESCROW"
    assert res_hold["amount_usd"] == 10.00

    status = stake_gate.get_status(idea_id)
    assert status["status"] == "HELD_IN_ESCROW"

    # 2. Refund
    res_refund = stake_gate.process_automated_refund(idea_id, reason="Low depth test")
    assert res_refund["status"] == "REFUNDED"
    assert res_refund["amount_refunded_usd"] == 10.00

    # Idempotent refund check
    res_re_refund = stake_gate.process_automated_refund(idea_id)
    assert res_re_refund["status"] == "ALREADY_REFUNDED"


def test_stake_capture_to_equity():
    expert_id = "exp-pilot-002-lawyer"
    idea_id = "idea-test-stake-002"

    db.execute(
        """
        INSERT OR IGNORE INTO domain_ideas (
            idea_id, expert_id, title, problem_statement, target_audience,
            stake_amount_usd, stake_payment_status, status, created_at, updated_at
        ) VALUES (?, ?, 'Law Idea', 'Problem', 'Audience', 10.00, 'HELD_IN_ESCROW', 'IN_INTERVIEW', '2026-01-01', '2026-01-01')
        """,
        (idea_id, expert_id)
    )

    res_cap = stake_gate.capture_stake_to_venture(idea_id)
    status = stake_gate.get_status(idea_id)
    assert status["status"] == "CAPTURED_TO_EQUITY"

    # Nonexistent idea returns None on get_status
    assert stake_gate.get_status("non-existent-idea-404") is None

    # Nonexistent idea raises ValueError on refund
    with pytest.raises(ValueError, match="Idea not found"):
        stake_gate.process_automated_refund("non-existent-idea-404")
